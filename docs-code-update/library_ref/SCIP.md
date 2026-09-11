Assumption: by **`scip`**, you mean the **SCIP Optimization Suite solver** installed from `conda-forge::scip`, not `scipy`. I’m following the same “advanced technical doc plan / feature-category catalog” structure as your Cyclopts reference. 

# SCIP advanced technical doc plan — Pyomo-focused capability catalog

## Baseline findings

The current conda-forge `scip` package is **SCIP 10.0.2** and is described as a “Constraint Integer Programming and Branch-and-Cut-and-Price Framework”; installation is via `conda install conda-forge::scip` or the micromamba equivalent. ([Anaconda][1])

SCIP itself is a solver/framework for **constraint integer programs, MIPs, MINLPs, and branch-cut-and-price**. It includes a MIP solver, an LP-based MINLP solver, and, since version 10, optional numerically exact MILP solving/certification features. ([SCIP][2])

For **Pyomo**, the main built-in path is the external executable interface registered as `SolverFactory("scip")`, using Pyomo’s `.nl` problem format and SCIP’s AMPL/NL reader. Pyomo’s SCIP plugin declares support for linear, integer, quadratic objective, quadratic constraint, SOS1, and SOS2 capabilities, but this is Pyomo-interface capability, not the full native SCIP plugin universe. ([Pyomo Documentation][3])

PySCIPOpt is a separate Python interface to SCIP; installing `conda-forge::pyscipopt` installs SCIP automatically, but PySCIPOpt is not the same as Pyomo’s `SolverFactory("scip")` path. ([Anaconda][4])

---

## 0) Scope, versioning, and mental model

* Distinguish **SCIP solver**, **SCIP Optimization Suite**, **PySCIPOpt**, and **Pyomo’s SCIP interface**.
* What “installed with conda/micromamba” means: executable availability, solver version, channel pinning, platform support.
* SCIP’s mental model: CIP framework + MIP/MINLP solver + branch-cut-and-price plugin architecture.
* Pyomo mental model: symbolic model → `.nl` writer → external `scip` executable → `.sol` result parsing.
* Version-sensitive notes: SCIP 8+ uses the integrated AMPL reader; Pyomo detects `scip` first and falls back to `scipampl` for older versions. ([Pyomo Documentation][3])

---

## 1) Installation, environment setup, and deployment

* Conda/micromamba install recipes:

  * `micromamba install -c conda-forge scip pyomo`
  * optional: `micromamba install -c conda-forge pyscipopt`
* Environment verification:

  * `which scip` / `where scip`
  * `scip --version`
  * Pyomo availability check:

    ```python
    from pyomo.environ import SolverFactory
    opt = SolverFactory("scip")
    print(opt.available())
    print(opt.executable())
    ```
* Reproducible environment files:

  * `environment.yml`
  * explicit conda lock/pin strategy
  * channel priority and avoiding base environment pollution.
* Platform notes: conda-forge `scip` supports Linux, Windows, macOS Intel, macOS ARM, and Linux ARM builds. ([Anaconda][1])
* Licensing notes: conda package metadata lists a multi-license bundle because SCIP pulls in suite/dependency components; official SCIP releases from 8.0.3 onward are Apache 2.0, but document license at the environment/package level for deployment. ([Anaconda][1])

---

## 2) SCIP capability overview

* Problem classes:

  * MILP / MIP
  * MIQP / MIQCP-style quadratic models
  * MINLP
  * CIP / constraint programming flavored optimization
  * pseudo-Boolean optimization
* Solver architecture:

  * presolve
  * propagation
  * LP relaxation
  * cutting planes
  * branching
  * primal heuristics
  * conflict analysis
  * Benders’ decomposition
  * branch-cut-and-price
* SCIP as a standalone program vs callable C library vs Python interface.
* Exact solving mode in SCIP 10:

  * rational MILP solving
  * proof/certificate concepts
  * when exact mode matters and when normal floating-point solving is appropriate. ([SCIP][2])

---

## 3) Pyomo integration map

* Main interface:

  ```python
  opt = SolverFactory("scip")
  results = opt.solve(model, tee=True)
  ```
* Solver I/O:

  ```python
  opt = SolverFactory("scip", solver_io="nl")
  ```
* What Pyomo writes:

  * `.nl` problem file
  * `.row` / `.col` naming files when available
  * `.sol` solution file
* What SCIP receives:

  * command shape similar to:

    ```bash
    scip model -AMPL
    ```

  Pyomo’s SCIP plugin constructs command lines using the problem file and `-AMPL`. ([Pyomo Documentation][3])
* Declared Pyomo SCIP capabilities:

  * linear
  * integer
  * quadratic objective
  * quadratic constraints
  * SOS1/SOS2. ([Pyomo Documentation][3])
* Important limitation section:

  * Pyomo’s interface is file-based, not persistent.
  * Pyomo APPSI is designed for efficient repeated solves with small model changes, but current APPSI solver exports do not include SCIP in Pyomo’s solver list. ([Pyomo Documentation][5])

---

## 4) Model classes in Pyomo that map well to SCIP

* MILP:

  * binary/integer variables
  * linear constraints
  * linear objectives
* MIQP / quadratic:

  * quadratic objectives
  * quadratic constraints
  * convex vs nonconvex implications
* MINLP:

  * nonlinear expressions with integer/binary variables
  * when SCIP is appropriate vs IPOPT, BONMIN, Couenne, HiGHS, Gurobi, CPLEX
* SOS:

  * Pyomo SOS1/SOS2 construction
  * how Pyomo declares SCIP support
* Indicator/logical constraints:

  * Pyomo transformations vs solver-native support
  * when to linearize manually
* Piecewise-linear models:

  * Pyomo `Piecewise`
  * SOS2 vs big-M vs convex-combination formulations.

---

## 5) Core Pyomo solve syntax

* Minimal solve:

  ```python
  from pyomo.environ import *

  m = ConcreteModel()
  # define vars, objective, constraints

  opt = SolverFactory("scip")
  res = opt.solve(m, tee=True)
  ```
* Loading results:

  ```python
  if res.solver.termination_condition == TerminationCondition.optimal:
      m.solutions.load_from(res)
  ```
* Keeping files:

  ```python
  res = opt.solve(m, tee=True, keepfiles=True, symbolic_solver_labels=True)
  ```
* Logging:

  ```python
  res = opt.solve(m, tee=True, logfile="scip.log")
  ```
* Time limits:

  ```python
  opt.options["limits/time"] = 300
  ```

  Pyomo also maps `timelimit` into `limits/time` if `limits/time` is not already provided. ([Pyomo Documentation][3])

---

## 6) SCIP parameter system and Pyomo option syntax

* Native SCIP parameter naming:

  * slash-separated keys like `limits/time`, `limits/gap`, `display/statistics`
* Generating a parameter file from SCIP:

  ```text
  SCIP> set save scip.set
  ```

  The official parameter page notes this as the way to export the current parameter list. ([SCIP][6])
* Pyomo option syntax:

  ```python
  opt = SolverFactory("scip")
  opt.options["limits/time"] = 600
  opt.options["limits/gap"] = 1e-4
  opt.options["display/verblevel"] = 4
  res = opt.solve(model, tee=True)
  ```
* How Pyomo passes options:

  * It writes SCIP options into a temporary `scip.set` file.
  * If a local `scip.set` exists, Pyomo warns that it will be ignored when Pyomo is generating its own option file. ([Pyomo Documentation][3])
* Parameter families to document:

  * `limits/*`
  * `display/*`
  * `presolving/*`
  * `separating/*`
  * `heuristics/*`
  * `branching/*`
  * `constraints/*`
  * `lp/*`
  * `numerics/*`
  * `parallel/*`, if available in the installed build.

---

## 7) Termination conditions, result interpretation, and diagnostics

* Pyomo result fields:

  * `results.solver.status`
  * `results.solver.termination_condition`
  * `results.solver.message`
  * gap, primal bound, dual bound where parsed.
* SCIP termination states mapped by Pyomo:

  * optimal
  * infeasible
  * unbounded
  * infeasible or unbounded
  * time limit
  * node limit
  * memory limit
  * gap limit
  * solution limit
  * user interrupt
  * unknown/unexpected message. ([Pyomo Documentation][3])
* Best-practice solve checks:

  ```python
  from pyomo.opt import TerminationCondition, SolverStatus

  tc = results.solver.termination_condition
  if tc == TerminationCondition.optimal:
      ...
  elif tc == TerminationCondition.maxTimeLimit:
      ...
  elif tc == TerminationCondition.infeasible:
      ...
  ```

---

## 8) Logging, statistics, and reproducibility

* `tee=True` vs log files.
* SCIP display verbosity.
* `display/statistics = TRUE` through AMPL/SCIP options.
* Reading solver logs for:

  * primal bound
  * dual bound
  * gap
  * nodes
  * presolve reductions
  * separators
  * heuristics
* Reproducibility checklist:

  * pin package versions
  * capture SCIP version
  * capture full parameter file
  * store `.nl`, `.sol`, `.log`, and generated `scip.set` for difficult cases
  * set deterministic/randomization parameters when needed.
* Pyomo’s SCIP plugin parses log fields including solving time, gap, primal bound, and dual bound when available. ([Pyomo Documentation][3])

---

## 9) Presolve, propagation, heuristics, cuts, and branching

* Presolving:

  * reductions, aggregation, probing, implied integrality
  * `SCIPsetPresolving` modes: default, fast, aggressive, off. ([SCIP][7])
* Heuristics:

  * finding feasible incumbents
  * `SCIPsetHeuristics` modes: default, fast, aggressive, off. ([SCIP][7])
* Separating / cutting planes:

  * `SCIPsetSeparating` modes
  * root vs tree separation
  * cut aggressiveness tradeoffs. ([SCIP][7])
* Branching:

  * reliability branching
  * pseudo-costs
  * strong branching
  * variable priority ideas.
* Practical Pyomo documentation target:

  * “safe parameter presets”
  * “faster feasible solution”
  * “prove optimality”
  * “debug infeasibility”
  * “reduce memory.”

---

## 10) Constraint handlers and native SCIP expressiveness

* Native SCIP plugin categories:

  * constraint handlers
  * variable pricers
  * domain propagators
  * separators
  * relaxators
  * Benders plugins
  * primal heuristics
  * node selectors
  * branching rules
  * presolvers
  * file readers
  * event handlers
  * display/dialog handlers. ([SCIP][8])
* Pyomo-facing implication:

  * Many native SCIP concepts are not directly exposed through `SolverFactory("scip")`.
  * Pyomo users usually access them indirectly via model formulation and parameter settings.
  * Direct plugin work belongs in C/C++ or PySCIPOpt, not normal Pyomo solve calls.

---

## 11) File formats and standalone SCIP usage

* Native SCIP can read many file formats and can be used standalone.
* SCIP supports input files for nonlinear problems and constraint programs, and the docs describe file formats as a major interface path. ([SCIP][9])
* Pyomo-generated path:

  * `.nl` via AMPL interface
* Standalone workflows:

  ```bash
  scip
  SCIP> read model.lp
  SCIP> optimize
  SCIP> display solution
  SCIP> set save scip.set
  ```
* Documentation topics:

  * using `scip.set`
  * exporting/translating Pyomo models
  * debugging with `keepfiles=True`
  * comparing Pyomo `.nl` vs hand-written `.lp`.

---

## 12) PySCIPOpt side path: when Pyomo is not enough

* What PySCIPOpt provides:

  * direct Python access to SCIP
  * model construction
  * parameter setting
  * callbacks/plugins
  * event handlers, branching rules, heuristics, separators, lazy constraints. ([pyscipopt.readthedocs.io][10])
* When to choose PySCIPOpt instead of Pyomo:

  * custom SCIP plugins
  * callbacks
  * advanced event handling
  * direct solution pool manipulation
  * fine-grained solve-process control
* When to stay in Pyomo:

  * algebraic modeling clarity
  * portability across solvers
  * transformations
  * data/model separation
  * existing Pyomo workflows.

---

## 13) Advanced SCIP 10 capabilities

* Numerically exact MILP mode:

  * rational arithmetic
  * exact LP relaxations
  * proof/certificate concepts
  * build-time dependency implications.
* New SCIP 10 improvements:

  * implied-integrality presolver
  * cut-based conflict analysis
  * flower inequalities
  * infeasibility explanation tooling
  * new nonlinear solver interface
  * symmetry, branching, and Benders improvements. ([Optimization Online][11])
* Pyomo-facing question for deep dive:

  * Which exact-solving features are accessible from conda binaries?
  * Which are accessible through Pyomo parameters?
  * Which require native SCIP/PySCIPOpt/C API usage?

---

## 14) Performance tuning playbook

* Tuning objectives:

  * fast feasible solution
  * strong proof of optimality
  * memory reduction
  * aggressive presolve
  * numerical stability
  * nonlinear robustness
* Parameter recipes:

  * time limit
  * gap limit
  * node limit
  * emphasis settings
  * presolve aggressiveness
  * heuristics aggressiveness
  * separating aggressiveness
* Model-side performance:

  * tighten bounds
  * scale coefficients
  * avoid weak big-M
  * use indicator/SOS/piecewise formulations carefully
  * exploit sparsity
  * reduce nonlinear expression complexity.
* Benchmark harness:

  * same model, same data, same parameters
  * capture wall time, nodes, gap, primal/dual bounds.

---

## 15) Numerical stability and modeling best practices

* Scaling:

  * variable units
  * objective scaling
  * constraint coefficient ranges
* Bounds:

  * finite bounds on variables
  * tight big-M values
  * bound tightening workflows
* Integrality:

  * binary vs integer vs continuous domains
  * fixing variables
  * warm-start-style initial values where supported.
* Nonlinear modeling:

  * avoid undefined expressions
  * guard divisions/logs/square roots
  * ensure domains are explicit.
* Pyomo transformations:

  * GDP-to-MIP
  * piecewise transformations
  * nonlinear expression handling.

---

## 16) Infeasibility analysis and debugging

* Pyomo-level tools:

  * `log_infeasible_constraints`
  * model display/pprint
  * constraint slack inspection
* SCIP-level tools:

  * conflict analysis
  * infeasibility messages
  * SCIP 10 infeasibility explanation tool.
* Workflow:

  * solve relaxed model
  * remove integrality
  * add constraints incrementally
  * inspect bounds and big-M values
  * compare with another solver when possible.
* Artifacts to preserve:

  * `.nl`
  * `.log`
  * `.sol`
  * generated `scip.set`
  * model data snapshot.

---

## 17) Deployment patterns

* Local notebooks.
* CLI scripts.
* Batch/HPC jobs.
* Containers.
* Streamlit/web apps.
* CI validation.
* Recommended deployment structure:

  ```text
  env/
  src/
  models/
  data/
  runs/
    run_id/
      model.nl
      scip.log
      scip.set
      results.json
  ```
* Conda/micromamba best practices:

  * use named envs
  * pin solver versions for production
  * do not rely on globally installed solvers
  * check executable on startup.

---

## 18) Testing and QA for Pyomo + SCIP

* Smoke tests:

  * solver availability
  * tiny MILP solve
  * tiny MINLP solve if needed
* Regression tests:

  * objective value
  * termination condition
  * solution feasibility
  * solver gap
* Option tests:

  * verify `limits/time`
  * verify `limits/gap`
  * verify log capture
* Failure tests:

  * infeasible model
  * unbounded model
  * missing executable
  * invalid SCIP parameter.
* Golden artifacts:

  * known `.log` signatures
  * expected termination mapping
  * expected model outputs.

---

## 19) Comparative framing

* SCIP vs HiGHS:

  * HiGHS for LP/MIP speed and simplicity; SCIP for broader MIP/MINLP/CIP capabilities.
* SCIP vs IPOPT:

  * IPOPT is continuous NLP; SCIP handles integrality and global MIP/MINLP workflows.
* SCIP vs Couenne/BONMIN:

  * MINLP alternatives; compare robustness, installability, license, model support.
* SCIP vs commercial solvers:

  * Gurobi/CPLEX/Xpress for industrial MILP performance; SCIP for open-source, MINLP/CIP flexibility, and plugin architecture.
* Pyomo vs PySCIPOpt:

  * modeling portability vs solver-native control.

---

## 20) Documentation deliverable plan

I would organize the final SCIP documentation into three layers:

**Layer A — Pyomo user guide**

* install
* solve syntax
* options
* result interpretation
* common model patterns
* troubleshooting

**Layer B — SCIP capability reference**

* problem classes
* parameters
* presolve/cuts/heuristics/branching
* exact solving
* logs/statistics
* infeasibility tools

**Layer C — advanced extension guide**

* PySCIPOpt
* native SCIP plugin architecture
* custom callbacks/plugins
* decomposition/branch-price workflows
* performance benchmarking and deployment hardening

The best next deep dive is probably **Section 3 + Section 6 together: “Pyomo SCIP integration and option syntax,”** because that gives you the exact implementation bridge you will use every day.

[1]: https://anaconda.org/conda-forge/scip "scip - conda-forge | Anaconda.org"
[2]: https://www.scipopt.org/doc/html/ "SCIP Doxygen Documentation: Overview"
[3]: https://pyomo.readthedocs.io/en/6.8.2/_modules/pyomo/solvers/plugins/solvers/SCIPAMPL.html "pyomo.solvers.plugins.solvers.SCIPAMPL — Pyomo 6.8.2 documentation"
[4]: https://anaconda.org/conda-forge/pyscipopt "pyscipopt - conda-forge | Anaconda.org"
[5]: https://pyomo.readthedocs.io/en/stable/reference/topical/appsi/appsi.html "APPSI — Pyomo 6.10.0 documentation"
[6]: https://www.scipopt.org/doc/html/PARAMETERS.php "SCIP Doxygen Documentation: List of all SCIP parameters"
[7]: https://www.scipopt.org/doc/html/group__ParameterMethods.php "SCIP Doxygen Documentation: Parameter"
[8]: https://www.scipopt.org/ "SCIP"
[9]: https://scipopt.org/doc/html/INTERFACES.php "SCIP Doxygen Documentation: Interfaces"
[10]: https://pyscipopt.readthedocs.io/en/stable/install.html "Installation Guide — PySCIPOpt  documentation"
[11]: https://optimization-online.org/2025/11/the-scip-optimization-suite-10-0/ "The SCIP Optimization Suite 10.0 – Optimization Online"

# 0) SCIP scope, versioning, and mental model — agent-ready deep dive

Style target: dense technical reference, aligned with your advanced doc template. 

---

## 0.1 Terminology boundary: four similarly named things

| Name                        |                                                                              What it is |     Python import? |                                             Executable? | Primary use case                                        | Pyomo relevance                                             |
| --------------------------- | --------------------------------------------------------------------------------------: | -----------------: | ------------------------------------------------------: | ------------------------------------------------------- | ----------------------------------------------------------- |
| **SCIP**                    | Solver + C-callable optimization framework for CIPs, MIPs, MINLPs, branch-cut-and-price |                 No |                                          Usually `scip` | standalone solve; embedded C/C++; plugin framework      | target external solver                                      |
| **SCIP Optimization Suite** |                                Bundle around SCIP: SCIP, SoPlex, PaPILO, ZIMPL, UG, GCG |                 No |                                          multiple tools | full optimization toolchain                             | conda may install components/dependencies around this stack |
| **PySCIPOpt**               |                                                  Python interface/modeling API for SCIP | `import pyscipopt` |     no separate CLI requirement for the Python API path | direct Python SCIP modeling, callbacks, plugins, events | alternative to Pyomo, not Pyomo’s normal SCIP backend       |
| **Pyomo SCIP interface**    |                   Pyomo `SystemCallSolver` plugin registered as `SolverFactory("scip")` |    `pyomo.environ` | requires external `scip` or legacy `scipampl` on `PATH` | Pyomo model → `.nl` → SCIP executable → `.sol` parse    | main path for your planned deployment                       |

SCIP is both a standalone MIP/MINLP solver and a plugin-oriented framework for branching, cutting plane separation, propagation, pricing, Benders’ decomposition, constraint handlers, pricers, propagators, separators, relaxators, heuristics, branching rules, presolvers, file readers, event handlers, display handlers, and dialog handlers. ([SCIP][1])

The SCIP Optimization Suite is the larger toolbox: SCIP plus SoPlex, PaPILO, ZIMPL, UG, and GCG; SCIP may use SoPlex as its LP solver during the solution process. ([SCIP][1])

PySCIPOpt is a Python interface to SCIP; its install guide states that package-manager installations come with their own SCIP versions, and conda installs SCIP automatically when installing PySCIPOpt. ([PySCIPOpt Documentation][2])

Pyomo’s `scip` solver is not PySCIPOpt. Pyomo registers `SolverFactory("scip")` to class `SCIPAMPL`, a `SystemCallSolver` using the AMPL/NL interface; its valid problem format is `.nl` and valid result format is `.sol`. ([Pyomo Documentation][3])

---

## 0.2 Value case: why SCIP in a Pyomo deployment

### Use SCIP through Pyomo when

* algebraic model clarity > solver-native callback control;
* solver portability matters: same Pyomo model may be tested with HiGHS, CBC, IPOPT, Bonmin, Couenne, Gurobi, CPLEX, SCIP;
* model classes include MIP/MINLP/CIP-like structure;
* open-source/noncommercial solver stack preferred;
* `.nl` file-based solve latency is acceptable;
* batch solve / CLI solve / reproducible artifact solve is more important than persistent incremental edits.

### Use PySCIPOpt instead when

* you need native SCIP callbacks/plugins;
* you need event handlers, custom branching, separators, lazy constraints via constraint handlers, custom heuristics, cut selectors, node selectors;
* you need direct SCIP model inspection during search;
* you need solver-state persistence beyond Pyomo’s file-based external call path.

### Avoid SCIP-through-Pyomo when

* repeated small model edits require persistent in-memory solver state;
* every millisecond of solve orchestration overhead matters;
* you need Pyomo APPSI-style incremental update semantics;
* you need guaranteed exposure of every SCIP-native plugin feature through Python.

Pyomo’s SCIP plugin advertises linear, integer, quadratic objective, quadratic constraint, SOS1, and SOS2 capabilities, but those are Pyomo-plugin capability flags, not a full exposure of native SCIP’s plugin architecture. ([Pyomo Documentation][3])

---

## 0.3 Conda/micromamba installation semantics

### Current package facts

`conda-forge::scip` is currently published as SCIP **10.0.2**, summary “Constraint Integer Programming and Branch-and-Cut-and-Price Framework,” with install command `conda install conda-forge::scip`; supported platforms listed include `linux-64`, `linux-aarch64`, `win-64`, `macOS-64`, and `macOS-arm64`. ([Anaconda][4])

SCIP’s own site lists conda install commands for `pyscipopt`, `pygcgopt`, `gcg`, `papilo`, `scip`, `soplex`, and `zimpl`, i.e. conda packaging can install suite components independently rather than necessarily installing one monolithic “suite” package. ([SCIP][1])

Micromamba is a statically linked C++ package-manager executable, does not require a base environment, and is convenient for CI/Docker flows via `micromamba run`; it can create and run isolated environments with commands such as `micromamba create -p /tmp/env ...` and `micromamba run -p /tmp/env ...`. ([Mamba][5])

### Install commands

```bash
# Conda
conda create -n opt-scip -c conda-forge python=3.11 pyomo scip
conda activate opt-scip

# Micromamba: named env
micromamba create -n opt-scip -c conda-forge python=3.11 pyomo scip
micromamba activate opt-scip

# Micromamba: prefix env, CI/container-friendly
micromamba create -p /opt/env -c conda-forge python=3.11 pyomo scip
micromamba run -p /opt/env python -c "import pyomo.environ as pyo; print('ok')"

# Optional native Python SCIP API path
micromamba install -n opt-scip -c conda-forge pyscipopt
```

### What “installed” must mean for Pyomo

Minimum runtime contract:

```text
active environment contains:
  python
  pyomo
  scip executable visible on PATH
  dynamic libraries resolvable by OS loader
  compatible SCIP executable version, preferably >= 8
```

Agent probe:

```python
from pyomo.environ import SolverFactory

opt = SolverFactory("scip")
assert opt.available(exception_flag=True)
print("solver:", opt)
print("executable:", opt.executable())
print("version:", opt.version())
```

Shell probe:

```bash
which scip || where scip
scip --version
python - <<'PY'
from pyomo.environ import SolverFactory
opt = SolverFactory("scip")
print("available =", opt.available(False))
print("executable =", opt.executable())
print("version =", opt.version())
PY
```

Best-practice invariant: do not trust `conda list scip` alone. For Pyomo, executable discovery is the live contract: `SolverFactory("scip").available()` and `opt.executable()`.

---

## 0.4 Version pinning and reproducible environment contract

### Recommended `environment.yml`

```yaml
name: opt-scip
channels:
  - conda-forge
channel_priority: strict
dependencies:
  - python=3.11
  - pyomo
  - scip=10.0.2
  # optional native SCIP Python API:
  # - pyscipopt
```

Micromamba’s installation docs explicitly show conda-forge channel configuration and strict channel priority commands, which is the right default for avoiding mixed-channel ABI drift in solver stacks. ([Mamba][6])

```bash
micromamba config append channels conda-forge
micromamba config set channel_priority strict
```

### Agent-side version capture

```python
import json
import platform
import subprocess
from pyomo.environ import SolverFactory

def scip_env_fingerprint():
    opt = SolverFactory("scip")
    exe = opt.executable()
    scip_version_text = subprocess.run(
        [exe, "--version"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    ).stdout.strip()

    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "pyomo_scip_available": opt.available(False),
        "pyomo_scip_executable": exe,
        "pyomo_scip_version_tuple": tuple(opt.version()) if opt.available(False) else None,
        "scip_version_text": scip_version_text,
    }

print(json.dumps(scip_env_fingerprint(), indent=2))
```

Deployment rule: persist this fingerprint beside every important solve artifact. Minimum artifact set: model data hash, Pyomo version, SCIP version text, SCIP executable path, solver options, termination condition, objective, primal/dual bounds, gap, log file.

---

## 0.5 SCIP mental model: CIP + MIP/MINLP + branch-cut-and-price

### Core abstraction

```text
SCIP = solving framework
  problem representation:
    variables
    constraints
    objective
    bounds
    domains
  algorithmic loop:
    presolve
    solve relaxations
    propagate domains
    separate cuts
    branch
    price variables if applicable
    run primal heuristics
    analyze conflicts
    update primal/dual bounds
    terminate by proof/limit/status
```

SCIP’s documentation defines it as a framework for constraint integer programs and mixed-integer nonlinear programs, incorporating a MIP solver, an LP-based MINLP solver, and a framework for branch-and-cut-and-price. ([SCIP][7])

### Plugin vocabulary agents must preserve

| SCIP concept       | Meaning                                                     | Value case                                            | Pyomo exposure                                  |
| ------------------ | ----------------------------------------------------------- | ----------------------------------------------------- | ----------------------------------------------- |
| constraint handler | semantics + propagation + enforcement for constraint family | native nonlinear/logical/combinatorial modeling power | mostly indirect through `.nl`/model formulation |
| separator          | cut generation from relaxation                              | stronger dual bounds, smaller trees                   | parameter-tunable, not custom via Pyomo         |
| propagator         | domain tightening independent of constraint handler         | early infeasibility, bound tightening                 | indirect                                        |
| branching rule     | node split selection                                        | search efficiency                                     | parameter-tunable, not custom via Pyomo         |
| node selector      | tree navigation                                             | memory/time strategy                                  | parameter-tunable                               |
| primal heuristic   | incumbent discovery                                         | feasible solution speed                               | parameter-tunable                               |
| pricer             | dynamic variable generation                                 | branch-price/column generation                        | not via normal Pyomo solve                      |
| Benders plugin     | decomposition machinery                                     | structured large-scale MIP/MINLP                      | not normally via Pyomo                          |
| event handler      | solve-process event callbacks                               | monitoring/control                                    | PySCIPOpt/native path                           |

SCIP’s feature list explicitly includes plugin categories for constraint handlers, variable pricers, domain propagators, separators, relaxators, Benders’ decomposition plugins, primal heuristics, node selectors, branching rules, presolvers, file readers, event handlers, display handlers, dialog handlers, and conflict analysis. ([SCIP][1])

### Agent rule

```text
If task = “formulate and solve algebraic optimization model”:
    use Pyomo + SolverFactory("scip")
If task = “control SCIP search process / add callbacks / implement plugin”:
    use PySCIPOpt or native SCIP, not Pyomo external executable path
```

---

## 0.6 Pyomo mental model: symbolic model → NL file → external executable → solution parse

### Execution pipeline

```text
Pyomo ConcreteModel / AbstractModel
  ↓
Pyomo expression system + model transformations
  ↓
NL writer
  ↓
temporary *.nl problem file
  ↓
external process:
    scip <problem-without-.nl-for-SCIP>=8 -AMPL
  ↓
SCIP writes *.sol
  ↓
Pyomo result parser
  ↓
SolverResults + model variable values
```

Pyomo’s SCIP plugin sets valid problem formats to `[ProblemFormat.nl]`, valid result format for NL to `[ResultsFormat.sol]`, and default problem format to NL. ([Pyomo Documentation][3])

Pyomo’s SCIP command-line construction asserts NL input and SOL output, derives a `.sol` filename from the problem file, sets it as the results file, and constructs a command list `[executable, problem_file, "-AMPL"]`. ([Pyomo Documentation][3])

### Minimal syntax

```python
from pyomo.environ import *

m = ConcreteModel()
m.x = Var(domain=Binary)
m.y = Var(bounds=(0, None))
m.obj = Objective(expr=3*m.x + m.y, sense=maximize)
m.c = Constraint(expr=2*m.x + m.y <= 4)

opt = SolverFactory("scip")
results = opt.solve(m, tee=True)

print(results.solver.status)
print(results.solver.termination_condition)
print(value(m.x), value(m.y))
```

### Pyomo interface semantics

```python
opt = SolverFactory("scip")
```

means:

```text
not: import pyscipopt
not: direct in-process SCIP model
not: persistent solver state
yes: discover executable scip/scipampl
yes: write temporary .nl
yes: run external process
yes: parse .sol and log-derived fields
```

Pyomo’s SCIP plugin also reads SCIP log tails to populate solver time, gap, primal bound, and dual bound when the expected log labels are present. ([Pyomo Documentation][3])

---

## 0.7 Version-sensitive executable resolution: `scip` vs `scipampl`

### Pyomo detection logic

Pyomo’s SCIP plugin first looks for executable `scip`; if found, it runs `scip --version` and accepts it when the parsed version is `>= (8,)`. If that test fails, Pyomo falls back to legacy executable `scipampl`; if neither is found, it disables the solver and logs a warning. ([Pyomo Documentation][3])

```text
Pyomo SCIP executable selection:
  1. find "scip"
  2. parse "scip --version"
  3. if version >= 8: use scip
  4. else: find "scipampl"
  5. else: unavailable
```

### SCIP 8+ `.nl` filename rule

For executable version `>= 8.0.0`, Pyomo strips the `.nl` extension before passing the model path to SCIP; for older versions it passes the full `.nl` path. ([Pyomo Documentation][3])

```text
SCIP >= 8:
  cmd = ["scip", "/tmp/model", "-AMPL"]      # no .nl suffix

SCIP < 8 / legacy:
  cmd = ["scipampl", "/tmp/model.nl", "-AMPL"]
```

### Deployment implication

Modern conda-forge SCIP 10.0.2 should be reached as `scip`, not `scipampl`; legacy `scipampl` guidance usually applies to old SCIP 7-era installations or custom builds. The conda-forge package reports SCIP 10.0.2, while Pyomo’s executable resolver accepts `scip` for version 8 or newer. ([Anaconda][4])

---

## 0.8 Interface capability vs native solver capability

### Pyomo-declared SCIP plugin capabilities

```python
_capabilities.linear = True
_capabilities.integer = True
_capabilities.quadratic_objective = True
_capabilities.quadratic_constraint = True
_capabilities.sos1 = True
_capabilities.sos2 = True
```

These flags are in Pyomo’s `SCIPAMPL` constructor. ([Pyomo Documentation][3])

### Agent interpretation

```text
Pyomo capability flag = writer/interface promises a class of model expressions can be sent.
SCIP native capability = solver/framework can support broader behavior/plugins.
Do not infer PySCIPOpt/native callback availability from Pyomo capability flags.
Do not infer all SCIP file readers/formats are usable through Pyomo; Pyomo SCIP path is NL → SOL.
```

---

## 0.9 Deployment advisory: solver discovery invariants

### Correct startup check

```python
from pyomo.environ import SolverFactory

def require_scip():
    opt = SolverFactory("scip")
    if not opt.available(False):
        raise RuntimeError(
            "SCIP unavailable to Pyomo. Activate the conda/micromamba env "
            "containing conda-forge::scip and ensure 'scip' is on PATH."
        )
    version = opt.version()
    if version and tuple(version) < (8, 0, 0):
        raise RuntimeError(
            f"Detected old SCIP version {version}; Pyomo may require legacy scipampl. "
            "Prefer conda-forge::scip >= 8."
        )
    return opt
```

### Correct environment execution in CI/container

```bash
micromamba run -n opt-scip python solve.py
# or
micromamba run -p /opt/env python solve.py
```

Micromamba documentation explicitly calls `micromamba run` convenient for CI and Docker environments where shell activation hooks are complicated. ([Mamba][5])

### High-signal failure modes

| Symptom                                      | Likely cause                                                 | Probe                             | Fix                                                         |
| -------------------------------------------- | ------------------------------------------------------------ | --------------------------------- | ----------------------------------------------------------- |
| `SolverFactory("scip").available() == False` | `scip` not on active env `PATH`                              | `which scip`; `opt.executable()`  | activate env; use `micromamba run`; install `scip`          |
| Pyomo finds old solver                       | stale `scip` earlier on `PATH`                               | `which -a scip`; `scip --version` | sanitize `PATH`; call through env                           |
| works locally, fails in Docker/cloud         | solver executable not installed in image                     | run shell probe in image          | install `scip` in Dockerfile/env                            |
| `scipampl` advice confusion                  | old SCIP 7-era docs                                          | `scip --version`                  | use SCIP >= 8 `scip`                                        |
| options ignored unexpectedly                 | local `scip.set` conflict or Pyomo temp option file behavior | `keepfiles=True`, inspect log/cwd | pass options through `opt.options`, archive generated files |

When Pyomo writes options, it creates a temporary `scip.set`; if a `scip.set` exists in the current working directory, Pyomo warns that the current-directory file will be ignored while Pyomo uses its separate options file. ([Pyomo Documentation][3])

---

## 0.10 Minimal reproducible Pyomo+SCIP harness

```python
from pyomo.environ import *
from pyomo.opt import SolverStatus, TerminationCondition

def build_model():
    m = ConcreteModel()
    m.x = Var(domain=Binary)
    m.y = Var(domain=NonNegativeReals)
    m.obj = Objective(expr=5*m.x + m.y, sense=maximize)
    m.cap = Constraint(expr=3*m.x + m.y <= 4)
    return m

def solve_with_scip(m, *, tee=True, time_limit=60):
    opt = SolverFactory("scip")
    if not opt.available(False):
        raise RuntimeError("SCIP executable unavailable to Pyomo")

    opt.options["limits/time"] = time_limit
    results = opt.solve(
        m,
        tee=tee,
        symbolic_solver_labels=True,
        keepfiles=False,
    )

    tc = results.solver.termination_condition
    status = results.solver.status

    if status == SolverStatus.ok and tc == TerminationCondition.optimal:
        return results

    if tc in {TerminationCondition.maxTimeLimit, TerminationCondition.feasible}:
        return results

    raise RuntimeError(f"Unexpected SCIP termination: status={status}, tc={tc}")

if __name__ == "__main__":
    m = build_model()
    res = solve_with_scip(m)
    print("x =", value(m.x))
    print("y =", value(m.y))
    print("obj =", value(m.obj))
```

Pyomo maps SCIP log/result messages into Pyomo termination conditions such as optimal, infeasible, unbounded, infeasible-or-unbounded, user interrupt, and unknown/unexpected solver message categories. ([Pyomo Documentation][3])

---

## 0.11 Agent decision procedure

```text
Input: user asks “install/use scip with pyomo”

1. Interpret "scip" as solver executable unless context says PySCIPOpt.
2. Recommend conda-forge install:
     micromamba create -n ENV -c conda-forge python pyomo scip
3. Verify:
     scip --version
     SolverFactory("scip").available()
4. Use Pyomo:
     opt = SolverFactory("scip")
     opt.options["limits/time"] = ...
     opt.solve(model, tee=True)
5. Explain runtime chain:
     Pyomo model -> .nl -> scip -AMPL -> .sol -> SolverResults
6. Warn:
     Pyomo path is file-based/external; not PySCIPOpt; not persistent; not native plugin API.
7. If user asks callbacks/custom branching/lazy constraints:
     redirect to PySCIPOpt/native SCIP path.
8. If user sees scipampl references:
     explain SCIP >= 8 integrated path; Pyomo falls back to scipampl only for older versions.
```

---

## 0.12 Compact mental model for downstream sections

```text
SCIP:
  solver/framework; native plugin-rich branch-cut-and-price architecture.

SCIP Optimization Suite:
  SCIP-centered toolchain: SCIP + SoPlex + PaPILO + ZIMPL + UG + GCG.

conda-forge::scip:
  environment package; installs executable/library artifacts for active platform.

PySCIPOpt:
  direct Python API to SCIP; use for native SCIP control.

Pyomo SolverFactory("scip"):
  external executable adapter; writes .nl; invokes scip -AMPL; parses .sol/log.

SCIP >= 8:
  Pyomo uses integrated scip executable.

SCIP < 8:
  Pyomo attempts legacy scipampl fallback.
```

[1]: https://www.scipopt.org/ "SCIP"
[2]: https://pyscipopt.readthedocs.io/en/stable/install.html "Installation Guide — PySCIPOpt  documentation"
[3]: https://pyomo.readthedocs.io/en/6.8.2/_modules/pyomo/solvers/plugins/solvers/SCIPAMPL.html "pyomo.solvers.plugins.solvers.SCIPAMPL — Pyomo 6.8.2 documentation"
[4]: https://anaconda.org/conda-forge/scip "scip - conda-forge | Anaconda.org"
[5]: https://mamba.readthedocs.io/en/latest/user_guide/micromamba.html "Micromamba User Guide — documentation"
[6]: https://mamba.readthedocs.io/en/latest/installation/micromamba-installation.html "Micromamba Installation — documentation"
[7]: https://www.scipopt.org/doc-6.0.2/html/index.php "SCIP Doxygen Documentation: Overview"

# 1) SCIP installation, environment setup, and deployment — Pyomo-focused deep dive

Reference style follows the prior advanced technical doc pattern. 

---

## 1.0 Deployment contract

```text
Target runtime contract:
  package manager: conda / mamba / micromamba
  channel: conda-forge
  env isolation: named env or prefix env; never implicit base env
  required packages:
    python
    pyomo
    scip
  required executable:
    scip visible on PATH inside active env
  Pyomo solver object:
    SolverFactory("scip")
  Pyomo transport:
    .nl problem file -> external scip executable -> .sol parse
  optional direct native SCIP Python API:
    pyscipopt
```

`conda-forge::scip` currently publishes SCIP **10.0.2**, with package summary “Constraint Integer Programming and Branch-and-Cut-and-Price Framework,” install command `conda install conda-forge::scip`, and supported platforms `linux-aarch64`, `win-64`, `macOS-64`, `macOS-arm64`, and `linux-64`. ([Anaconda][1])

Pyomo’s SCIP solver interface is registered as `SolverFactory("scip")`; the implementation is `SCIPAMPL`, a `SystemCallSolver`, with valid problem format `ProblemFormat.nl` and result format `ResultsFormat.sol`. ([pyomo.readthedocs.io][2])

---

## 1.1 Conda/micromamba install recipes

### 1.1.1 Existing environment install

```bash
# conda
conda install -c conda-forge scip pyomo

# mamba
mamba install -c conda-forge scip pyomo

# micromamba
micromamba install -c conda-forge scip pyomo
```

SCIP’s official site lists conda-forge install commands for SCIP Optimization Suite components including `pyscipopt`, `gcg`, `papilo`, `scip`, `soplex`, and `zimpl`; use `scip` for the Pyomo external-solver path and `pyscipopt` only when direct Python SCIP API access is needed. ([SCIP Optimization Library][3])

### 1.1.2 Fresh named environment

```bash
micromamba create -n opt-scip -c conda-forge python=3.11 pyomo scip
micromamba activate opt-scip
```

### 1.1.3 Fresh prefix environment: CI/container/HPC preferred

```bash
micromamba create -p /opt/envs/opt-scip -c conda-forge python=3.11 pyomo scip
micromamba run -p /opt/envs/opt-scip python -c "import pyomo.environ as pyo; print('pyomo ok')"
```

Use prefix environments when agents must avoid shell activation state, shared base pollution, or ambiguous `PATH` resolution.

### 1.1.4 Optional PySCIPOpt install

```bash
micromamba install -n opt-scip -c conda-forge pyscipopt
```

`conda-forge::pyscipopt` is currently version **6.1.0**, is described as an “Interface from Python to the SCIP Optimization Suite,” and installs from conda-forge with `conda install conda-forge::pyscipopt`. ([Anaconda][4])

Do **not** install PySCIPOpt merely to make Pyomo’s `SolverFactory("scip")` work. Pyomo’s SCIP path requires the external `scip` executable; PySCIPOpt is for direct SCIP API work.

---

## 1.2 Channel configuration: conda-forge-only solver stack

### 1.2.1 Micromamba strict channel setup

```bash
micromamba config append channels conda-forge
micromamba config set channel_priority strict
```

Micromamba’s official installation guide notes that an exclusive conda-forge setup can be configured with `micromamba config append channels conda-forge` and `micromamba config set channel_priority strict`; it also states micromamba is a self-contained executable and does not ship with a preconfigured `.condarc`/`.mambarc`. ([mamba.readthedocs.io][5])

### 1.2.2 Deployment rule

```text
Allowed:
  channels:
    - conda-forge
  channel_priority: strict

Avoid:
  mixed defaults + conda-forge solver stacks
  installing into base
  pip-installing binary solver dependencies into conda envs
  relying on globally installed scip outside active env
```

Reason: SCIP/SoPlex/GMP/MPFR/C++ runtime libraries are binary artifacts. Mixed-channel solves increase ABI/library-resolution risk.

---

## 1.3 Reproducible `environment.yml`

### 1.3.1 Minimal Pyomo + SCIP environment

```yaml
name: opt-scip
channels:
  - conda-forge
channel_priority: strict
dependencies:
  - python=3.11
  - pyomo
  - scip=10.0.2
```

### 1.3.2 With PySCIPOpt side path

```yaml
name: opt-scip-dev
channels:
  - conda-forge
channel_priority: strict
dependencies:
  - python=3.11
  - pyomo
  - scip=10.0.2
  - pyscipopt=6.1.0
  - pytest
  - pandas
```

Use this profile when the codebase contains both:

```python
from pyomo.environ import SolverFactory       # Pyomo external solve path
from pyscipopt import Model                   # direct SCIP API path
```

### 1.3.3 Environment creation

```bash
micromamba create -f environment.yml
micromamba activate opt-scip
```

or CI-safe:

```bash
micromamba create -p /opt/env -f environment.yml
micromamba run -p /opt/env python scripts/verify_scip.py
```

---

## 1.4 Locking and pinning strategy

### 1.4.1 Pinning levels

| Level                 | Syntax                           | Repro strength | Use case                              |
| --------------------- | -------------------------------- | -------------: | ------------------------------------- |
| loose                 | `scip`                           |            low | local exploration                     |
| minor/major bound     | `scip>=10,<11`                   |         medium | research notebooks                    |
| exact package version | `scip=10.0.2`                    |           high | production model runs                 |
| lockfile with hashes  | `conda-lock.yml` / explicit lock |        highest | CI, Docker, regulated reproducibility |

`conda-lock` is designed to generate reproducible conda lock files by solving for target platforms; its docs state lock files avoid re-running the solver during install and support `environment.yml` as a source format. ([conda.github.io][6])

### 1.4.2 Multi-platform lock generation

```bash
# install conda-lock outside project runtime env
micromamba create -n locktools -c conda-forge conda-lock
micromamba run -n locktools conda-lock lock \
  -f environment.yml \
  -p linux-64 \
  -p linux-aarch64 \
  -p osx-64 \
  -p osx-arm64 \
  -p win-64
```

`conda-lock lock` writes a multi-platform lock file by default, supports `-p/--platform`, accepts `-f/--file`, and can use micromamba via its CLI options. ([conda.github.io][7])

### 1.4.3 Lock install

```bash
conda-lock install -n opt-scip conda-lock.yml
# or, if using mamba/micromamba-compatible lock flow:
micromamba create -n opt-scip -f conda-lock.yml
```

In Docker, lockfiles reduce solve time and avoid channel queries during environment creation; micromamba-docker docs state that when a lockfile is used, `micromamba create ...` does not query package channels or execute the solver. ([micromamba-docker.readthedocs.io][8])

### 1.4.4 Agent rule

```text
For exploratory local work:
  environment.yml with scip=major.minor.patch is acceptable.

For CI / paper artifacts / production optimization service:
  commit:
    environment.yml
    conda-lock.yml or platform-specific explicit locks
    scripts/verify_scip.py
    solver option manifest
```

---

## 1.5 Environment verification: shell-level

### 1.5.1 POSIX shell

```bash
command -v scip
which scip
scip --version
```

### 1.5.2 Windows PowerShell

```powershell
where.exe scip
scip --version
```

### 1.5.3 Full binary path audit

```bash
echo "$PATH" | tr ':' '\n'
which -a scip || true
python -c "import sys; print(sys.executable)"
```

Windows:

```powershell
$env:Path -split ';'
where.exe scip
python -c "import sys; print(sys.executable)"
```

### 1.5.4 Expected invariant

```text
python executable path and scip executable path must belong to same conda/micromamba env prefix.

Good:
  /opt/env/bin/python
  /opt/env/bin/scip

Bad:
  /opt/env/bin/python
  /usr/local/bin/scip
```

---

## 1.6 Environment verification: Pyomo-level

### 1.6.1 Minimal availability probe

```python
from pyomo.environ import SolverFactory

opt = SolverFactory("scip")
print("available:", opt.available())
print("executable:", opt.executable())
```

Pyomo documents `available()` as returning whether the solver is available and `executable()` as returning the executable used by the solver; `set_executable()` searches `PATH` for base filenames and validates executable files when `validate=True`. ([pyomo.readthedocs.io][9])

### 1.6.2 Strict probe: fail fast

```python
from pyomo.environ import SolverFactory

def require_scip():
    opt = SolverFactory("scip")
    if not opt.available(False):
        raise RuntimeError(
            "SCIP unavailable: activate env containing conda-forge::scip "
            "or run via `micromamba run -n <env> ...`."
        )
    exe = opt.executable()
    ver = opt.version()
    print(f"SCIP executable: {exe}")
    print(f"SCIP version tuple: {ver}")
    return opt

opt = require_scip()
```

Pyomo’s `SCIPAMPL.version()` returns a tuple describing the solver executable version. ([pyomo.readthedocs.io][9])

### 1.6.3 Executable override

```python
from pyomo.environ import SolverFactory

opt = SolverFactory("scip")
opt.set_executable("/opt/env/bin/scip", validate=True)
```

Use executable override only for controlled deployments. Prefer environment activation or `micromamba run` over hard-coded solver paths.

---

## 1.7 Pyomo SCIP interface verification: actual solve smoke test

```python
from pyomo.environ import *
from pyomo.opt import SolverStatus, TerminationCondition

def smoke_model():
    m = ConcreteModel()
    m.x = Var(domain=Binary)
    m.y = Var(bounds=(0, None))
    m.obj = Objective(expr=5*m.x + m.y, sense=maximize)
    m.c = Constraint(expr=3*m.x + m.y <= 4)
    return m

m = smoke_model()
opt = SolverFactory("scip")

assert opt.available(False), "SCIP executable unavailable to Pyomo"

res = opt.solve(m, tee=True)
print("status:", res.solver.status)
print("termination:", res.solver.termination_condition)
print("x:", value(m.x))
print("y:", value(m.y))
print("obj:", value(m.obj))

assert res.solver.status == SolverStatus.ok
assert res.solver.termination_condition in {
    TerminationCondition.optimal,
    TerminationCondition.feasible,
}
```

Pyomo’s SCIP plugin sets valid problem formats to `.nl`, result format to `.sol`, declares support for linear, integer, quadratic objective, quadratic constraints, SOS1, and SOS2, and registers itself under solver name `scip`. ([pyomo.readthedocs.io][2])

---

## 1.8 Deployment artifact capture

### 1.8.1 Runtime fingerprint script

```python
# scripts/scip_fingerprint.py
import json
import os
import platform
import subprocess
import sys
from pyomo.environ import SolverFactory

def run(cmd):
    return subprocess.run(
        cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    ).stdout.strip()

opt = SolverFactory("scip")

fingerprint = {
    "python_executable": sys.executable,
    "python_version": platform.python_version(),
    "platform": platform.platform(),
    "conda_prefix": os.environ.get("CONDA_PREFIX"),
    "mamba_root_prefix": os.environ.get("MAMBA_ROOT_PREFIX"),
    "pyomo_scip_available": opt.available(False),
    "pyomo_scip_executable": opt.executable() if opt.available(False) else None,
    "pyomo_scip_version": tuple(opt.version()) if opt.available(False) else None,
    "scip_version_stdout": run([opt.executable(), "--version"]) if opt.available(False) else None,
}

print(json.dumps(fingerprint, indent=2, sort_keys=True))
```

### 1.8.2 Run artifact manifest

```text
run/
  environment.yml
  conda-lock.yml
  scip_fingerprint.json
  model_input.json
  solver_options.json
  model.nl              # optional, keepfiles=True
  scip.log
  results.json
```

### 1.8.3 Solve call with artifacts

```python
res = opt.solve(
    model,
    tee=True,
    logfile="run/scip.log",
    keepfiles=True,
    symbolic_solver_labels=True,
)
```

Pyomo’s SCIP implementation generates a log file, derives a `.sol` file from the problem filename, and for SCIP 8+ reads log-derived fields such as solving time, gap, primal bound, and dual bound when available. ([pyomo.readthedocs.io][2])

---

## 1.9 Platform notes

### 1.9.1 Conda-forge `scip` target platforms

```text
linux-64       Linux x86_64
linux-aarch64  Linux ARM64
win-64         Windows x86_64
macOS-64       macOS Intel / osx-64
macOS-arm64    Apple Silicon / osx-arm64
```

The current conda-forge `scip` package page lists supported platforms `linux-aarch64`, `win-64`, `macOS-64`, `macOS-arm64`, and `linux-64`. ([Anaconda][1])

### 1.9.2 PySCIPOpt platform caveat

`conda-forge::pyscipopt` currently lists `macOS-arm64`, `macOS-64`, `win-64`, and `linux-64`; unlike `scip`, its displayed platform list does not include `linux-aarch64` on the package page. ([Anaconda][4])

### 1.9.3 Windows-specific commands

```powershell
micromamba create -n opt-scip -c conda-forge python=3.11 pyomo scip
micromamba activate opt-scip

where.exe scip
scip --version

python - <<'PY'
from pyomo.environ import SolverFactory
opt = SolverFactory("scip")
print(opt.available(False))
print(opt.executable())
print(opt.version())
PY
```

### 1.9.4 Linux container-specific commands

```dockerfile
FROM mambaorg/micromamba:2.6.0

COPY --chown=$MAMBA_USER:$MAMBA_USER environment.yml /tmp/environment.yml
RUN micromamba create -y -n opt-scip -f /tmp/environment.yml \
    && micromamba clean --all --yes

ENV ENV_NAME=opt-scip
```

Micromamba-docker documents Dockerfile install patterns using `micromamba install` / `micromamba create`, environment files, lockfiles, and `micromamba clean --all --yes` for image hygiene. ([micromamba-docker.readthedocs.io][8])

---

## 1.10 Licensing notes for deployment review

### 1.10.1 Package-level license metadata

The current conda-forge `scip` package metadata lists a combined license expression: `Apache-2.0 AND LGPL-3.0-or-later AND EPL-1.0 and MIT and Zlib and BSL-1.0 and HPND`. ([Anaconda][1])

### 1.10.2 Upstream SCIP license baseline

SCIP’s official site states that since version **8.0.3**, SCIP is licensed under Apache 2.0, while releases up to and including 8.0.2 remain under the ZIB Academic License; it also notes that third-party code and linkable dependencies can introduce additional licenses. ([SCIP Optimization Library][3])

### 1.10.3 Deployment advisory

```text
For internal research:
  record package version and conda license metadata.

For production/commercial deployment:
  record:
    scip package license expression
    exact package build artifacts from lockfile
    Pyomo license
    Python package dependency licenses
    whether PySCIPOpt is included
    whether suite components beyond scip are installed

Do not state “SCIP is only Apache-2.0” for a deployed conda environment.
State:
  upstream SCIP >=8.0.3 is Apache-2.0;
  conda package environment may include third-party components under additional licenses.
```

SCIP’s license page lists additional third-party/dependency licenses for SCIP Optimization Suite components, including AMPL MP, CppAD, symmetry libraries, TinyCThread, Bliss, Boost, CLP, GMP, HiGHS, IPOPT, MPFR, PaPILO, QSOpt/QSOpt_ex, Readline, SoPlex, ZIMPL, and Zlib. ([SCIP Optimization Library][3])

---

## 1.11 Failure-mode diagnostics

| Failure                                           | Probe                                                       | Likely cause                                      | Fix                                                            |
| ------------------------------------------------- | ----------------------------------------------------------- | ------------------------------------------------- | -------------------------------------------------------------- |
| `SolverFactory("scip").available(False) == False` | `which scip`; `opt.executable()`                            | active env lacks `scip` or `PATH` wrong           | `micromamba install -c conda-forge scip`; use `micromamba run` |
| `scip --version` works but Pyomo unavailable      | `python -c "import pyomo"`; `python -c ... opt.available()` | different Python/env from shell solver            | align `python` and `scip` paths                                |
| Pyomo picks stale system SCIP                     | `which -a scip`                                             | global solver precedes env solver                 | activate env; fix `PATH`; use prefix env                       |
| Windows cannot find solver                        | `where.exe scip`                                            | shell activation not applied                      | use Micromamba Prompt/PowerShell hook or `micromamba run`      |
| conda solve changes unexpectedly                  | `conda list --show-channel-urls`                            | mixed channels / no strict priority               | conda-forge-only strict channel priority                       |
| CI slow or nondeterministic                       | build logs show solving                                     | no lockfile                                       | generate `conda-lock.yml`; install from lock                   |
| licensing review mismatch                         | `conda list --json`; package metadata                       | upstream license confused with binary env license | document package-level license expression                      |

---

## 1.12 Agent-ready installation checklist

```text
1. Create isolated env:
   micromamba create -n opt-scip -c conda-forge python=3.11 pyomo scip

2. Verify shell executable:
   which scip        # POSIX
   where.exe scip    # Windows
   scip --version

3. Verify Pyomo solver:
   from pyomo.environ import SolverFactory
   opt = SolverFactory("scip")
   assert opt.available(False)
   print(opt.executable())
   print(opt.version())

4. Run smoke MILP.

5. Pin:
   scip=10.0.2
   channel_priority: strict
   channels: [conda-forge]

6. Lock:
   conda-lock lock -f environment.yml -p linux-64 -p osx-arm64 -p win-64

7. Deploy:
   micromamba run -n opt-scip python solve.py
   or
   micromamba run -p /opt/env python solve.py

8. Archive:
   environment.yml
   lockfile
   scip --version output
   Pyomo solver executable path
   solver options
   solver log
   result object summary

9. License note:
   upstream SCIP >=8.0.3 Apache-2.0;
   conda binary environment carries combined package/dependency license metadata.
```

[1]: https://anaconda.org/conda-forge/scip "scip - conda-forge | Anaconda.org"
[2]: https://pyomo.readthedocs.io/en/6.8.2/_modules/pyomo/solvers/plugins/solvers/SCIPAMPL.html "pyomo.solvers.plugins.solvers.SCIPAMPL — Pyomo 6.8.2 documentation"
[3]: https://www.scipopt.org/index.php "SCIP"
[4]: https://anaconda.org/conda-forge/pyscipopt "pyscipopt - conda-forge | Anaconda.org"
[5]: https://mamba.readthedocs.io/en/latest/installation/micromamba-installation.html "Micromamba Installation — documentation"
[6]: https://conda.github.io/conda-lock/ "conda-lock"
[7]: https://conda.github.io/conda-lock/cli/gen/ "CLI Reference - conda-lock"
[8]: https://micromamba-docker.readthedocs.io/en/latest/advanced_usage.html "Advanced Usages — micromamba-docker 2.6.0 documentation"
[9]: https://pyomo.readthedocs.io/en/latest/api/pyomo.solvers.plugins.solvers.SCIPAMPL.SCIPAMPL.html "SCIPAMPL — Pyomo 6.10.1.dev0 documentation"

# 2) SCIP capability overview — agent-ready deep dive

Format target: dense technical reference, same advanced-doc style as the uploaded template. 

---

## 2.0 Capability boundary

```text id="oz8e2l"
SCIP native capability:
  MIP / MILP
  MINLP
  MIQP / MIQCP-style quadratic models
  CIP / CP-flavored integer optimization
  pseudo-Boolean optimization via OPB/WBO/CNF-style standalone readers
  branch-cut-and-price framework
  Benders/decomposition framework
  plugin-extensible C/C++ solver architecture
  optional exact MILP mode in SCIP 10+

Pyomo + SCIP capability:
  Pyomo symbolic algebra model
  -> .nl writer
  -> external scip executable
  -> .sol/log parse
  exposed primarily through SolverFactory("scip")
  no direct SCIP callback/plugin surface
```

SCIP is documented as a framework for constraint integer programs and mixed-integer nonlinear programs; it incorporates a MIP solver, an LP-based MINLP solver, and a branch-cut-and-price framework. Since version 10, it can optionally be configured for numerically exact MILP solving with independently verifiable certificates. ([SCIP Optimization Library][1])

---

## 2.1 Problem-class taxonomy

### 2.1.1 MILP / MIP

Canonical mathematical form:

```text id="i3wbuo"
min/max cᵀx
s.t.    A x ≤ b
        l ≤ x ≤ u
        x_j ∈ Z for j ∈ I
        x_j ∈ {0,1} for j ∈ B
```

Native SCIP value case:

```text id="fh9gaa"
MILP/MIP = SCIP primary production path
  LP relaxations -> dual bounds
  branch-and-bound/tree search
  cutting planes -> stronger relaxations
  primal heuristics -> incumbents
  conflict analysis -> learned constraints
  presolve/propagation -> reduced search space
```

Pyomo syntax:

```python id="rma5ar"
from pyomo.environ import *

m = ConcreteModel()
m.I = RangeSet(3)
m.x = Var(m.I, domain=Binary)
m.y = Var(bounds=(0, None))

m.obj = Objective(expr=sum([2, 4, 7][i-1] * m.x[i] for i in m.I) + m.y)
m.cap = Constraint(expr=sum([1, 2, 5][i-1] * m.x[i] for i in m.I) + m.y <= 6)

opt = SolverFactory("scip")
res = opt.solve(m, tee=True)
```

Deployment advisory:

```text id="cpq45y"
Use SCIP for MILP when:
  open-source solver required
  model contains difficult combinatorics
  need strong presolve/cuts/heuristics/conflict analysis
  can tolerate external executable solve path from Pyomo

Use HiGHS/CBC first when:
  pure LP/MIP, simpler open-source stack, no MINLP/CIP features needed

Use commercial solvers when:
  highest industrial MILP throughput / support / concurrent optimization required
```

SCIP’s public feature list describes it as a fast standalone MIP/MINLP solver and as a framework for branching, cutting-plane separation, propagation, pricing, and Benders’ decomposition. ([SCIP Optimization Library][2])

---

### 2.1.2 MIQP / MIQCP-style quadratic models

Problem variants:

```text id="zqd1nu"
MIQP:
  quadratic objective
  linear constraints
  integer variables

MIQCP / MIQCQP-style:
  linear or quadratic objective
  quadratic constraints
  integer variables
```

Pyomo interface capability:

```text id="fkqsb6"
Pyomo SCIPAMPL capability flags:
  linear = True
  integer = True
  quadratic_objective = True
  quadratic_constraint = True
  sos1 = True
  sos2 = True
```

Pyomo’s SCIP plugin explicitly sets support flags for linear, integer, quadratic objective, quadratic constraint, SOS1, and SOS2 model features. ([Pyomo Documentation][3])

Pyomo MIQP sketch:

```python id="04m6sm"
from pyomo.environ import *

m = ConcreteModel()
m.x = Var(domain=Binary)
m.y = Var(bounds=(0, None))

m.obj = Objective(expr=(m.y - 3)**2 + 10*m.x)
m.c = Constraint(expr=m.y <= 5*m.x + 1)

res = SolverFactory("scip").solve(m, tee=True)
```

Pyomo quadratic-constraint sketch:

```python id="76wkp8"
m = ConcreteModel()
m.x = Var(bounds=(-10, 10))
m.y = Var(domain=Binary)

m.obj = Objective(expr=m.x)
m.qc = Constraint(expr=m.x**2 <= 4 + 10*m.y)

SolverFactory("scip").solve(m, tee=True)
```

Agent guardrail:

```text id="p3z1sg"
Quadratic accepted by interface ≠ all nonlinear modeling is safe/convex/easy.
Always classify:
  convex quadratic
  nonconvex quadratic
  binary-quadratic
  quadratic constraints with loose bounds
  scaling risk
```

SCIP Optimization Suite includes ZIMPL, which can generate linear, mixed-integer, and mixed-integer quadratically constrained programs that can be loaded into SCIP; SCIP may use SoPlex as the underlying LP solver during solution. ([SCIP Optimization Library][2])

---

### 2.1.3 MINLP

Canonical form:

```text id="t0he0s"
min/max f(x, y)
s.t.    g_i(x, y) ≤ 0
        x continuous
        y integer/binary
        nonlinear expressions allowed
```

Native SCIP mental model:

```text id="m73nlh"
MINLP in SCIP:
  nonlinear expression handling
  LP/NLP relaxations
  spatial branching / integer branching
  nonlinear constraint handlers
  domain propagation
  convex/underestimating relaxations where available
  primal heuristics
  conflict and infeasibility learning when applicable
```

Pyomo MINLP sketch:

```python id="sgym5o"
from pyomo.environ import *

m = ConcreteModel()
m.x = Var(bounds=(0.1, 10))
m.z = Var(domain=Binary)

m.obj = Objective(expr=(m.x - 2)**2 + 5*m.z)
m.c1 = Constraint(expr=log(m.x) + m.z >= 1)

opt = SolverFactory("scip")
res = opt.solve(m, tee=True)
```

Value case:

```text id="r2mx1r"
Use SCIP for Pyomo MINLP when:
  integrality + nonlinear expressions
  global/discrete search required
  open-source deployment preferred
  model has useful bounds and moderate nonlinear complexity

Avoid / reconsider when:
  continuous NLP only -> IPOPT likely better
  large convex QP/QCP only -> dedicated conic/QP solver may be better
  very hard global nonconvex MINLP -> compare Couenne/Baron/commercial tools
  missing finite bounds -> formulation likely weak/unstable
```

SCIP 10.0 paper reports SCIP 10.0 performance improvements on MINLP instances and notes new nonlinear-related enhancements, including a new nonlinear solver interface. ([Optimization Online][4])

---

### 2.1.4 CIP / constraint-programming flavored optimization

CIP mental model:

```text id="i8oqm6"
CIP = Constraint Integer Programming:
  integer programming search machinery
  + constraint-programming-style arbitrary constraint handlers
  + propagation
  + LP relaxations/cuts when useful
  + plugin-defined constraint semantics
```

Why CIP matters:

```text id="9sph92"
MILP solver view:
  constraints usually linearized into rows

CP solver view:
  constraints are semantic objects with domain propagation

SCIP CIP view:
  constraints may be semantic plugins
  branching recursively decomposes problem
  propagation tightens domains
  LP relaxations/cuts provide dual bounds
```

SCIP’s site contrasts integer programming and constraint programming: IP uses LP relaxations and cutting planes for strong dual bounds, while CP handles arbitrary nonlinear constraints and uses propagation to tighten domains; SCIP is built as a CIP framework for users needing control of the solution process. ([SCIP Optimization Library][2])

Pyomo implication:

```text id="z2kq5m"
Pyomo external SCIP path:
  sends algebraic NL representation
  does not expose arbitrary native SCIP constraint-handler authoring
  use PySCIPOpt/native C/C++ for custom constraint handlers
```

---

### 2.1.5 Pseudo-Boolean optimization

Problem pattern:

```text id="hbo5p2"
pseudo-Boolean:
  variables: x_i ∈ {0,1}
  objective/constraints: polynomial or linear Boolean functions
  common formats: OPB, WBO
  SAT-adjacent instances: CNF
```

Native SCIP value case:

```text id="q6czad"
Standalone SCIP can read pseudo-Boolean/SAT-adjacent formats:
  .opb
  .wbo
  .cnf
Use native reader path when:
  source instance already in OPB/WBO/CNF
  benchmark / competition format
  avoid Pyomo modeling overhead
```

SCIP’s standalone program can solve mixed-integer linear and nonlinear programs in formats including MPS, LP, FlatZinc, CNF, OPB, WBO, PIP, and others. ([SCIP Optimization Library][2])

Pyomo pseudo-Boolean sketch:

```python id="zmwo9r"
from pyomo.environ import *

m = ConcreteModel()
m.N = RangeSet(5)
m.x = Var(m.N, domain=Binary)

# Boolean-style cardinality constraint
m.atleast2 = Constraint(expr=sum(m.x[i] for i in m.N) >= 2)

# pseudo-Boolean weighted objective
m.obj = Objective(expr=sum(i * m.x[i] for i in m.N), sense=minimize)

SolverFactory("scip").solve(m, tee=True)
```

Agent distinction:

```text id="npjumt"
Native OPB/WBO/CNF support:
  standalone SCIP reader capability

Pyomo Binary algebra:
  Pyomo model -> NL file -> SCIP
  not OPB/WBO export by default
```

---

## 2.2 Solver architecture: solve-process components

### 2.2.1 High-level algorithm pipeline

```text id="g90zfq"
Input problem
  ↓
reader / model ingestion
  ↓
presolve
  ↓
root relaxation
  ↓
propagation
  ↓
separation / cuts
  ↓
primal heuristics
  ↓
branching
  ↓
node selection
  ↓
recursive node processing
  ↓
conflict analysis / learning
  ↓
incumbent + dual-bound updates
  ↓
termination by optimality / infeasibility / unboundedness / limits / interrupt
```

SCIP exposes plugin categories for presolvers, domain propagators, separators, relaxators, Benders plugins, primal heuristics, node selectors, branching rules, file readers, event handlers, display handlers, and conflict analysis. ([SCIP Optimization Library][2])

---

### 2.2.2 Presolve

Role:

```text id="0xdmps"
presolve:
  remove fixed variables
  tighten bounds
  aggregate/substitute variables
  upgrade constraints
  detect implied integrality
  simplify rows/constraints
  detect infeasibility early
  reduce search tree size
```

Value case:

```text id="0opbrt"
High value:
  big-M models
  redundant constraints
  weak initial bounds
  network-like constraints
  set packing/covering structures
  models generated by transformations

Risk:
  can obscure original variable/constraint mapping
  can make dual suffixes harder to interpret
  can consume time on already-small/easy models
```

Standalone shell syntax:

```text id="ptfhdm"
SCIP> set presolving emphasis aggressive
SCIP> set presolving emphasis fast
SCIP> set presolving emphasis off
SCIP> display presolvers
SCIP> display statistics
```

PySCIPOpt syntax:

```python id="yff7um"
from pyscipopt import Model, SCIP_PARAMSETTING

model = Model()
model.setPresolve(SCIP_PARAMSETTING.AGGRESSIVE)
# or
model.setPresolve(SCIP_PARAMSETTING.OFF)
```

Pyomo syntax:

```python id="kkbcqt"
opt = SolverFactory("scip")
# Prefer explicit SCIP parameter names discovered from `set save`.
opt.options["limits/time"] = 300
# For presolve-specific tuning, generate installed-version parameter list:
# SCIP> set save all_params.set
```

The SCIP shell supports saving/loading parameter files and navigating parameter groups including `presolving`; it also demonstrates setting and saving parameter values through the interactive shell. ([SCIP Optimization Library][5])

---

### 2.2.3 Propagation

Role:

```text id="hjcum3"
propagation:
  constraint-independent and constraint-specific domain tightening
  infer variable bounds/fixings
  detect local infeasibility
  generate implications
  reduce branching width
```

Architecture hook:

```text id="5ge63i"
SCIP plugin category:
  domain propagators
  constraint handlers with propagation callbacks
```

Value case:

```text id="rba6gp"
High value:
  binary logic
  scheduling
  CP-like combinatorics
  bound-heavy formulations
  pseudo-Boolean/cardinality constraints
```

SCIP documents domain propagators as plugins that apply constraint-independent propagation on variable domains. ([SCIP Optimization Library][2])

Pyomo implication:

```text id="feeu4r"
Strength depends on formulation:
  explicit finite bounds
  binary domains, not continuous [0,1] relaxations unless intentional
  tight big-M
  avoid hidden unbounded nonlinear domains
```

---

### 2.2.4 LP relaxation

Role:

```text id="d4zy50"
LP relaxation:
  solve continuous relaxation of current node
  produce dual bound
  provide fractional solution
  feed branching candidates
  feed separators
  feed LP-based primal heuristics
```

Value case:

```text id="8t47vf"
LP relaxation strength controls:
  root gap
  branch-and-bound tree size
  cut effectiveness
  proof speed
```

Architecture note:

```text id="zabokx"
SCIP may use SoPlex as underlying LP solver.
LP relaxation also feeds separators and some heuristics.
```

SCIP Optimization Suite includes SoPlex as a linear programming solver, and SCIP may use SoPlex as the underlying LP solver in the solution process. ([SCIP Optimization Library][2])

Modeling advisory:

```text id="7ojop2"
For Pyomo agents:
  prefer strong formulations
  avoid unnecessary big-M
  scale coefficients
  use tight variable bounds
  choose SOS2/piecewise formulation deliberately
```

---

### 2.2.5 Cutting planes / separation

Role:

```text id="4ov3jm"
separation:
  inspect relaxation solution
  find valid inequalities violated by current relaxation solution
  add cuts to LP
  improve dual bound
  reduce root/tree gap
```

SCIP plugin category:

```text id="0flbyz"
separator:
  LP-relaxation-based cutting plane generation
  dynamic cut pool management
```

SCIP documents separators for cutting planes based on the LP relaxation and dynamic cut-pool management. ([SCIP Optimization Library][2])

Standalone syntax:

```text id="9a5ou7"
SCIP> set separating emphasis aggressive
SCIP> set separating emphasis fast
SCIP> set separating emphasis off
SCIP> display separators
SCIP> display statistics
```

PySCIPOpt syntax:

```python id="tuormh"
from pyscipopt import Model, SCIP_PARAMSETTING

m = Model()
m.setSeparating(SCIP_PARAMSETTING.AGGRESSIVE)
```

Value case:

```text id="fev85x"
Increase separation when:
  root LP gap large
  proof slow but LP solves cheap
  cuts reduce nodes significantly

Decrease separation when:
  cuts expensive
  LP iterations explode
  memory pressure high
  incumbent already sufficient and proof not needed
```

---

### 2.2.6 Branching

Role:

```text id="tnqygo"
branching:
  choose variable/disjunction
  create child subproblems
  refine local domains
  drive search tree
```

SCIP architecture hook:

```text id="5nyvlp"
branching rules:
  plugin category
  can split into arbitrarily many children
  children can be arbitrarily defined
```

SCIP documents branching-rule plugins as mechanisms to split a problem into subproblems, with arbitrarily many children and arbitrary child definitions. ([SCIP Optimization Library][2])

Value case:

```text id="m0yj97"
Branching quality affects:
  number of nodes
  dual-bound progress
  incumbent discovery path
  memory pressure
```

Pyomo advisory:

```text id="4t85xz"
Pyomo does not expose custom branching callbacks through SolverFactory("scip").
Use:
  SCIP parameters -> tune built-in branching
  PySCIPOpt/native SCIP -> custom branching rule
```

---

### 2.2.7 Primal heuristics

Role:

```text id="r8ma3m"
primal heuristics:
  search for feasible solutions
  improve incumbent
  reduce primal bound
  enable pruning via incumbent cutoff
```

SCIP documents primal heuristics as plugins for searching feasible solutions, with support for probing and diving. ([SCIP Optimization Library][2])

Standalone syntax:

```text id="h6m2mp"
SCIP> set heuristics emphasis aggressive
SCIP> set heuristics emphasis fast
SCIP> set heuristics emphasis off
SCIP> display heuristics
SCIP> display statistics
```

SCIP’s shell tutorial shows `set heuristics emphasis`, with options `aggressive`, `default`, `fast`, and `off`, and demonstrates that the emphasis setting expands into many individual `heuristics/*/freq` parameter changes. ([SCIP Optimization Library][5])

PySCIPOpt syntax:

```python id="e1ffb4"
from pyscipopt import Model, SCIP_PARAMSETTING

m = Model()
m.setHeuristics(SCIP_PARAMSETTING.AGGRESSIVE)
```

Value case:

```text id="xavdee"
Increase heuristics when:
  need feasible solution quickly
  time-limited run
  primal bound poor
  feasibility > proof

Decrease heuristics when:
  proof speed more important
  heuristics consume time without incumbents
  deterministic benchmarking needs minimal variability
```

Pyomo deployment pattern:

```python id="diz038"
opt = SolverFactory("scip")
opt.options["limits/time"] = 60
opt.options["limits/gap"] = 0.05
# Additional heuristic tuning should be derived from installed SCIP parameter file.
```

---

### 2.2.8 Conflict analysis

Role:

```text id="g4zgwu"
conflict analysis:
  analyze infeasible subproblem
  derive conflict constraints / no-good information
  learn from failed search
  prune future nodes
```

Value case:

```text id="dqhhu6"
High value:
  combinatorial infeasibility
  binary implication structure
  CP/SAT-like substructure
  repeated infeasible branches
```

SCIP’s feature list states conflict analysis can be applied to learn from infeasible subproblems. ([SCIP Optimization Library][2])

SCIP 10 note:

```text id="g9fi27"
SCIP 10 introduced cut-based conflict analysis and a tool for explaining infeasibility via irreducible infeasible subsystems.
```

The SCIP 10 report lists cut-based conflict analysis and a tool for explanations of infeasibility through irreducible infeasible subsystems among the SCIP 10 developments. ([Optimization Online][4])

Pyomo advisory:

```text id="e4km7k"
For infeasible Pyomo models:
  first inspect Pyomo-level constraints/bounds
  preserve solver log
  keep .nl with keepfiles=True
  compare relaxed model
  then use SCIP native infeasibility/explanation tooling if needed
```

---

### 2.2.9 Benders’ decomposition

Role:

```text id="w0qlrc"
Benders decomposition:
  separate master problem and subproblems
  solve master iteratively
  generate Benders cuts from subproblem information
  exploit block-angular / linking-variable structure
```

SCIP architecture hook:

```text id="3dtsal"
Benders plugins:
  decomposition plugin category
  Benders cuts
  master/subproblem framework
```

SCIP documents plugins to apply Benders’ decomposition and implement Benders’ cuts. ([SCIP Optimization Library][2])

SCIP 10 note:

```text id="txercd"
SCIP 10 improves Benders’ decomposition with more flexible problem formulation and improved detection of master linking variables.
```

The SCIP 10 report explicitly lists improvements to SCIP’s Benders’ decomposition framework, including a more flexible problem formulation and improved detection of master linking variables. ([Optimization Online][4])

Pyomo advisory:

```text id="2jhgqg"
Do not assume Pyomo SolverFactory("scip") automatically exposes full Benders control.
For decomposition-aware implementation:
  native SCIP / PySCIPOpt / GCG path
  or explicit Pyomo decomposition algorithm outside SCIP
```

---

### 2.2.10 Branch-cut-and-price

Role:

```text id="yzftf8"
branch-cut-and-price:
  branch-and-bound
  + cuts/separation
  + column generation/pricing
  + dynamic variable creation
```

SCIP plugin hook:

```text id="0ndbwu"
variable pricer:
  dynamically create problem variables
  implement column generation
```

SCIP documents variable pricers for dynamic variable creation and describes itself as a framework for branch-cut-and-price. ([SCIP Optimization Library][2])

Value case:

```text id="ovwlwd"
Use branch-cut-and-price when:
  enormous implicit variable set
  set partitioning / routing / scheduling / cutting-stock-like structure
  compact full formulation too large
  decomposition/column generation natural
```

Pyomo implication:

```text id="bhtnmq"
Pyomo external SCIP path:
  static model file
  no dynamic variable-pricer callback API

Use:
  GCG / SCIP native / PySCIPOpt extension path for genuine pricing
```

The SCIP Optimization Suite includes GCG, described as a generic branch-cut-and-price solver. ([SCIP Optimization Library][2])

---

## 2.3 SCIP access modes: standalone vs C library vs Python interface vs Pyomo

### 2.3.1 Standalone executable

Value case:

```text id="4hyha1"
Use standalone SCIP when:
  solving existing .mps/.lp/.cip/.opb/.wbo/.cnf/.zpl-like files
  reproducing solver behavior outside Pyomo
  debugging solver parameters
  using interactive shell
  saving/loading .set parameter files
  exact-mode file-reader path needed
```

Syntax:

```bash id="b88tfg"
scip
```

SCIP shell:

```text id="k15x5a"
SCIP> read model.lp
SCIP> set limits time 300
SCIP> set limits gap 0.001
SCIP> optimize
SCIP> display solution
SCIP> display statistics
SCIP> write solution solution.sol
SCIP> set diffsave tuned.set
```

Batch-ish shell input:

```bash id="p4q0cs"
cat > run_scip.txt <<'EOF'
read model.lp
set limits time 300
set limits gap 0.001
optimize
display statistics
write solution solution.sol
quit
EOF

scip < run_scip.txt
```

SCIP’s shell tutorial documents saving/loading parameter files via `set save`, `set diffsave`, and `set load`; it also notes that a file named `scip.set` in the working directory is loaded automatically when the shell starts. ([SCIP Optimization Library][5])

---

### 2.3.2 Callable C library / C++ plugin wrapper

Value case:

```text id="fhm4ml"
Use C/C++ when:
  implementing production native plugins
  custom constraint handler
  custom separator
  custom pricer
  custom branching rule
  custom event handler
  maximum solve-process control required
```

C-like skeleton:

```c id="m9nnl3"
#include "scip/scip.h"
#include "scip/scipdefplugins.h"

int main(void)
{
    SCIP* scip = NULL;

    SCIPcreate(&scip);
    SCIPincludeDefaultPlugins(scip);

    SCIPreadProb(scip, "model.lp", NULL);
    SCIPsetRealParam(scip, "limits/time", 300.0);

    SCIPsolve(scip);

    SCIPfree(&scip);
    return 0;
}
```

SCIP is implemented as a C-callable library and provides C++ wrapper classes for user plugins. ([SCIP Optimization Library][2])

---

### 2.3.3 PySCIPOpt

Value case:

```text id="mhfl45"
Use PySCIPOpt when:
  Python required
  direct SCIP model/control required
  callbacks/plugins/events needed
  parameter tuning via native API
  solution/process inspection required
```

Install:

```bash id="ibuo1o"
micromamba install -c conda-forge pyscipopt
```

Minimal model:

```python id="rfz2y3"
from pyscipopt import Model, quicksum

m = Model("mip")
x = {i: m.addVar(vtype="B", name=f"x_{i}") for i in range(5)}

m.setObjective(quicksum(i * x[i] for i in range(5)), "minimize")
m.addCons(quicksum(x[i] for i in range(5)) >= 2)

m.setRealParam("limits/time", 60.0)
m.optimize()

print("status:", m.getStatus())
for i in range(5):
    print(i, m.getVal(x[i]))
```

PySCIPOpt’s docs list direct tutorials/API areas for model objects, variables, constraints, nonlinear expressions, log files, branching rules, cut selectors, separators, heuristics, node selectors, lazy constraints via constraint handlers, and event handlers. ([PySCIPOpt Documentation][6])

---

### 2.3.4 Pyomo external solver interface

Value case:

```text id="i2gz15"
Use Pyomo + SCIP when:
  algebraic modeling
  solver portability
  Pyomo transformations
  .nl external solve acceptable
  no native SCIP callback/plugin needed
```

Syntax:

```python id="pvjl3p"
from pyomo.environ import *

m = ConcreteModel()
# build model ...

opt = SolverFactory("scip")
opt.options["limits/time"] = 300
opt.options["limits/gap"] = 1e-4

res = opt.solve(
    m,
    tee=True,
    symbolic_solver_labels=True,
    keepfiles=False,
)
```

Pyomo’s SCIP plugin is registered as `scip`, uses `ProblemFormat.nl`, expects `ResultsFormat.sol`, detects `scip` version 8+ before falling back to `scipampl`, and invokes the external executable with `-AMPL`. ([Pyomo Documentation][3])

Agent rule:

```text id="u8sd21"
If user says:
  “Pyomo model solve with SCIP” -> SolverFactory("scip")
  “SCIP callback / branching / separator / lazy constraint” -> PySCIPOpt or native SCIP
  “existing MPS/LP/OPB/WBO file” -> standalone scip
  “column generation / pricing” -> GCG/native SCIP/PySCIPOpt, not plain Pyomo external solve
```

---

## 2.4 Exact solving mode in SCIP 10

### 2.4.1 Exact mode definition

```text id="41ki1f"
SCIP exact mode:
  target: rational MILP
  arithmetic: rational + extended precision + safe floating-point
  goal: no unsafe floating-point roundoff influence
  optional output: independently checkable proof/certificate
```

SCIP’s exact-mode guide states that exact mode solves mixed-integer linear programs using rational, extended-precision, and safe floating-point computation to guarantee results are not affected by roundoff errors from unsafe floating-point arithmetic. ([SCIP Optimization Library][7])

### 2.4.2 Build requirements

Exact mode requires SCIP to be built with:

```text id="nnzs9q"
GMP    -> rational arithmetic in ZIMPL, SoPlex, SCIP, PaPILO
Boost  -> multiprecision rationals in SCIP / PaPILO if linked
MPFR   -> rational-to-floating approximations in SCIP
exact LP solver, e.g. SoPlex
```

The exact-mode guide lists GMP, Boost multiprecision, MPFR, and an exact LP solver such as SoPlex as build requirements. ([SCIP Optimization Library][7])

### 2.4.3 Activation syntax

Standalone SCIP:

```text id="kaz9le"
SCIP> set exact enable TRUE
SCIP> read model.lp
SCIP> optimize
```

Parameter-file style:

```text id="ugj1lz"
# scip.set
exact/enable = TRUE
```

C API:

```c id="tepvee"
SCIPenableExactSolving(scip);  /* must be before reading/creating problem */
```

SCIP’s exact-mode guide says enabling exact solving is done by setting `exact/enable = TRUE` or calling `SCIPenableExactSolving()`, and this must happen before reading a problem instance. ([SCIP Optimization Library][7])

### 2.4.4 Certificate syntax

SCIP 10 can log a proof of correctness for the LP-based branch-and-bound process by setting:

```text id="r6ip0k"
certificate/filename = proof.vipr
```

The SCIP 10 report states that SCIP can produce a VIPR-format certificate encoding SCIP’s reasoning for claimed primal and dual bounds, verifiable by independent proof checkers. ([Optimization Online][4])

### 2.4.5 Exact-mode feature scope

Supported in SCIP 10 exact mode:

```text id="lzwlsa"
MILP only
rational input data
rational presolving via PaPILO
safe dual bounding
reliability pseudocost branching
safe Gomory mixed-integer cuts
safe dual proof analysis
constraint propagation
exact post-processing of floating-point primal heuristic solutions
LP-based branch-and-bound certification, with presolving caveats
```

The SCIP 10 report states that exact solving mode is restricted to mixed-integer linear programs and lists rational presolving, safe dual bounding, reliability pseudocost branching, safe Gomory mixed-integer cuts, safe dual proof analysis, constraint propagation, exact solution post-processing, and LP-based branch-and-bound certification features. ([Optimization Online][4])

### 2.4.6 Exact readers and Pyomo caveat

Important file-reader boundary:

```text id="pvspcg"
SCIP 10 exact readers named in SCIP 10 report:
  MPS
  LP
  CIP
  OPB/WBO
  ZIMPL

Not guaranteed from that list:
  Pyomo .nl / AMPL NL exact rational reader path
```

The SCIP 10 report says exact-mode extensions were added to readers for MPS, LP, CIP, OPB/WBO, and ZIMPL files to read instances in exact arithmetic; it does not list AMPL `.nl` in that exact-reader sentence. ([Optimization Online][4])

Agent deployment rule:

```text id="oj2tzi"
Do not assume Pyomo SolverFactory("scip") + .nl transport yields certifiable rational exact MILP solving.

For exact-mode workflows:
  prefer standalone SCIP with native exact-supported file format
  or verify installed SCIP/Pyomo path with logs and certificate output
  archive input file, scip.set, certificate, solver log
```

Possible Pyomo experiment, not guaranteed contract:

```python id="23u3s9"
opt = SolverFactory("scip")
opt.options["exact/enable"] = "TRUE"
opt.options["certificate/filename"] = "proof.vipr"
res = opt.solve(m, tee=True, keepfiles=True, logfile="scip-exact.log")
```

Validation checklist:

```text id="1m2cds"
Confirm from log:
  exact mode actually enabled
  problem accepted as exact MILP
  certificate file created
  no unsupported nonlinear/quadratic/model-reader warning
  termination status proof-compatible
```

---

## 2.5 Floating-point mode vs exact mode decision table

| Requirement                                          |                Use normal SCIP |                                   Use exact SCIP 10 |
| ---------------------------------------------------- | -----------------------------: | --------------------------------------------------: |
| general MILP performance                             |                            yes |                                          usually no |
| MINLP                                                |                            yes |                   no, exact mode restricted to MILP |
| MIQP / MIQCP                                         |     yes, formulation-dependent |                                 no, not target mode |
| routine production solve                             |                            yes |                only if audit/certification requires |
| numerically fragile MILP                             | maybe, with scaling/tolerances |                                    strong candidate |
| legal/regulatory proof need                          |             insufficient alone |                                    strong candidate |
| independent certificate                              |                             no |                  yes, if certificate output enabled |
| Pyomo `.nl` convenience                              |                            yes | verify carefully; not the primary exact-reader path |
| rational benchmark input in LP/MPS/CIP/OPB/WBO/ZIMPL |                       possible |                                preferred exact path |

SCIP’s exact mode exists because floating-point MIP solvers cannot by design guarantee immunity from accumulated roundoff errors or produce independently verifiable certificates; SCIP 10 exact mode targets rational MILPs with no numerical tolerances. ([Optimization Online][4])

---

## 2.6 Capability-to-interface routing matrix

| Task                            | Recommended interface                         | Reason                                    |
| ------------------------------- | --------------------------------------------- | ----------------------------------------- |
| solve Pyomo MILP                | `SolverFactory("scip")`                       | simple algebraic modeling                 |
| solve Pyomo MINLP               | `SolverFactory("scip")`                       | SCIP supports MINLP; Pyomo writes `.nl`   |
| tune limits/gap/logging         | Pyomo `opt.options[...]`                      | direct SCIP parameter file path           |
| use SCIP shell/statistics       | standalone `scip`                             | full shell commands                       |
| solve OPB/WBO/CNF               | standalone `scip`                             | native readers                            |
| exact rational MILP certificate | standalone SCIP native exact-supported reader | exact-mode reader/certificate control     |
| custom branching                | PySCIPOpt / C/C++                             | plugin/callback needed                    |
| custom separator/cuts           | PySCIPOpt / C/C++                             | plugin/callback needed                    |
| dynamic column generation       | GCG / SCIP pricer / PySCIPOpt-native          | Pyomo external solve is static-file based |
| Benders framework control       | native SCIP/PySCIPOpt/GCG                     | decomposition plugin surface              |
| algebraic model portability     | Pyomo                                         | solver-agnostic model layer               |

---

## 2.7 Agent-oriented feature value cases

```text id="a82kbj"
presolve:
  value = smaller model, tighter bounds, early infeasibility
  deployment = default on; inspect stats before disabling

propagation:
  value = CP-like domain tightening
  deployment = strongest with explicit finite bounds and binary/integer domains

LP relaxation:
  value = dual bounds and branching/cut signal
  deployment = formulation strength dominates solver performance

cutting planes:
  value = reduce root/tree gap
  deployment = tune when proof slow; monitor LP/cut overhead

branching:
  value = controls search tree
  deployment = native callbacks require PySCIPOpt/C, not Pyomo

primal heuristics:
  value = early incumbent
  deployment = aggressive for feasible-first/time-limited runs

conflict analysis:
  value = learn from infeasible nodes
  deployment = useful for combinatorial infeasibility

Benders:
  value = exploit decomposable structure
  deployment = SCIP-native/GCG path for serious decomposition control

branch-cut-and-price:
  value = huge implicit variable sets
  deployment = GCG/native pricer path, not normal Pyomo file solve

exact MILP:
  value = rational correctness/certificates
  deployment = SCIP 10 exact build + exact-supported reader + proof archive
```

---

## 2.8 Minimal syntax inventory

### Pyomo MIP solve

```python id="s52rni"
opt = SolverFactory("scip")
opt.options["limits/time"] = 300
opt.options["limits/gap"] = 1e-4
res = opt.solve(model, tee=True)
```

### Standalone SCIP

```text id="js3zz1"
SCIP> read model.lp
SCIP> set limits time 300
SCIP> set limits gap 0.0001
SCIP> optimize
SCIP> display statistics
SCIP> write solution model.sol
```

### Save installed-version parameter inventory

```text id="oal7wv"
SCIP> set save all_params.set
SCIP> set diffsave changed_params.set
```

### PySCIPOpt parameter tuning

```python id="xu30km"
from pyscipopt import Model, SCIP_PARAMSETTING

m = Model()
m.setRealParam("limits/time", 300.0)
m.setRealParam("limits/gap", 1e-4)
m.setHeuristics(SCIP_PARAMSETTING.AGGRESSIVE)
m.setSeparating(SCIP_PARAMSETTING.FAST)
m.setPresolve(SCIP_PARAMSETTING.DEFAULT)
```

### Exact mode standalone

```text id="es8wkh"
SCIP> set exact enable TRUE
SCIP> set certificate filename proof.vipr
SCIP> read model.lp
SCIP> optimize
```

---

## 2.9 Deployment best-practice summary

```text id="g8bqvk"
Default Pyomo deployment:
  conda-forge::scip
  Pyomo SolverFactory("scip")
  opt.options["limits/time"]
  opt.options["limits/gap"]
  tee=True + logfile
  keepfiles=True for debugging

Performance deployment:
  preserve logs
  inspect display statistics
  tune presolving/separating/heuristics only after baseline
  benchmark with fixed seed/version/options/data
  compare gap/time/nodes/primal/dual

Advanced SCIP-native deployment:
  PySCIPOpt or C/C++
  implement callbacks/plugins only outside Pyomo external solver path

Exact/audit deployment:
  SCIP 10 exact-capable build
  exact/enable before reading
  native exact-supported file format
  certificate/filename
  independent proof verification pipeline
  avoid assuming Pyomo .nl exact rational semantics
```

[1]: https://www.scipopt.org/doc/html/ "SCIP Doxygen Documentation: Overview"
[2]: https://www.scipopt.org/ "SCIP"
[3]: https://pyomo.readthedocs.io/en/6.8.2/_modules/pyomo/solvers/plugins/solvers/SCIPAMPL.html "pyomo.solvers.plugins.solvers.SCIPAMPL — Pyomo 6.8.2 documentation"
[4]: https://optimization-online.org/wp-content/uploads/2025/11/scipopt-100.pdf "The SCIP Optimization Suite 10.0"
[5]: https://www.scipopt.org/doc/html/SHELL.php "SCIP Doxygen Documentation: Tutorial: the interactive shell"
[6]: https://pyscipopt.readthedocs.io/en/stable/install.html "Installation Guide — PySCIPOpt  documentation"
[7]: https://www.scipopt.org/doc-10.0.0/html/EXACT.php "SCIP Doxygen Documentation: How to use the numerically exact solving mode"

# 3) Pyomo integration map — SCIP backend semantics

Target: LLM programming agents generating, debugging, deploying, and validating Pyomo+SCIP code. Style follows the uploaded advanced-reference pattern. 

---

## 3.0 Interface identity

```text id="4x6m5w"
Pyomo solver key:
  "scip"

Factory:
  SolverFactory("scip")

Implementation:
  pyomo.solvers.plugins.solvers.SCIPAMPL.SCIPAMPL

Interface class:
  SystemCallSolver

Transport:
  file-based external process

Problem format:
  NL / AMPL Solver Library .nl

Result format:
  .sol

Native SCIP object persistence:
  no

PySCIPOpt dependency:
  no

Executable dependency:
  yes: scip or legacy scipampl
```

Pyomo registers the SCIP interface as `SolverFactory.register("scip")`; the class is `SCIPAMPL`, inherits `SystemCallSolver`, accepts only `ProblemFormat.nl`, maps NL problems to `ResultsFormat.sol`, and sets the default problem format to NL. ([Pyomo Documentation][1])

---

## 3.1 Main invocation surface

### 3.1.1 Default Pyomo solve

```python id="0zdkyc"
from pyomo.environ import *

opt = SolverFactory("scip")
results = opt.solve(model, tee=True)
```

Operational meaning:

```text id="28kv98"
SolverFactory("scip"):
  locate executable
  verify executable version
  prepare NL writer
  write temporary .nl problem
  optionally write .row/.col name maps
  write temporary SCIP option file if opt.options nonempty
  invoke external scip process with -AMPL
  parse .sol
  parse SCIP log fields when available
  return SolverResults
  optionally load primal solution into Pyomo model
```

### 3.1.2 Explicit solver I/O

```python id="7vww2y"
opt = SolverFactory("scip", solver_io="nl")
results = opt.solve(model, tee=True)
```

Use `solver_io="nl"` for agent clarity and old-code compatibility. For the current SCIP plugin, NL is not merely one option among many; the plugin declares NL as the only valid problem format and SOL as the result format for NL. ([Pyomo Documentation][1])

### 3.1.3 Full deployment-form solve call

```python id="vri5j2"
from pyomo.environ import *
from pyomo.opt import SolverStatus, TerminationCondition

opt = SolverFactory("scip", solver_io="nl")
assert opt.available(False), "SCIP executable unavailable"

opt.options["limits/time"] = 300
opt.options["limits/gap"] = 1e-4

results = opt.solve(
    model,
    tee=True,
    logfile="scip.log",
    keepfiles=True,
    symbolic_solver_labels=True,
)

status = results.solver.status
tc = results.solver.termination_condition

if status == SolverStatus.ok and tc == TerminationCondition.optimal:
    pass
elif tc in {TerminationCondition.maxTimeLimit, TerminationCondition.feasible}:
    pass
else:
    raise RuntimeError(f"SCIP failed or returned unexpected termination: {status=} {tc=}")
```

---

## 3.2 Executable resolution: modern `scip`, legacy `scipampl`

Pyomo’s SCIP plugin first searches for executable `scip`; if found, it runs `scip --version` and accepts it when the parsed version is `>= (8,)`; otherwise it falls back to legacy `scipampl`. If neither executable is found, the solver is disabled and Pyomo logs a warning. ([Pyomo Documentation][1])

```text id="mfw7pn"
Executable selection:
  1. search PATH for "scip"
  2. call "scip --version"
  3. if version >= 8:
       use scip
     else:
       search PATH for "scipampl"
  4. if neither found:
       SolverFactory("scip").available(False) == False
```

Agent probe:

```python id="l5ehgo"
from pyomo.environ import SolverFactory

opt = SolverFactory("scip")
print("available:", opt.available(False))
print("executable:", opt.executable())
print("version:", opt.version())
```

Modern conda-forge deployments should normally resolve to `.../bin/scip` or `...\Scripts\scip.exe`, not `scipampl`.

---

## 3.3 What Pyomo writes

### 3.3.1 Primary file: `.nl`

```text id="g0o8tg"
model.py
  Pyomo expression system
    ↓
  NLWriter
    ↓
  temporary_problem.nl
```

Pyomo’s `NLWriter.write()` writes a model in NL format to an output stream and returns `NLWriterInfo`; it accepts a concrete Pyomo model plus optional row and column streams. ([Pyomo Documentation][2])

### 3.3.2 Optional name maps: `.row` / `.col`

```text id="mhmxk1"
.row:
  ASL row file
  constraint/objective names in solver row order

.col:
  ASL col file
  variable names in solver column order
```

The NL writer writes the ASL row file and col file only when `symbolic_solver_labels=True`; the row file contains constraint/objective names, and the col file contains variable names. ([Pyomo Documentation][2])

Pyomo solve syntax:

```python id="ts8zcy"
results = opt.solve(
    model,
    symbolic_solver_labels=True,
    keepfiles=True,
    tee=True,
)
```

Direct write syntax:

```python id="2lz2kp"
model.write(
    filename="debug_model.nl",
    format="nl",
    io_options={"symbolic_solver_labels": True},
)
```

Best-practice use cases:

```text id="hlck6j"
Enable symbolic_solver_labels=True when:
  debugging infeasibility
  comparing .nl across runs
  mapping solver row/col indices back to Pyomo components
  archiving reproducibility artifacts
  diagnosing nonlinear expression export

Disable for production speed when:
  artifact mapping not needed
  model is large
  file size / write time matters
```

### 3.3.3 Solution file: `.sol`

During command-line construction, Pyomo derives the solution filename from the problem filename by stripping the extension and appending `.sol`; it also sets the results file to that `.sol` because an external parser is used. ([Pyomo Documentation][1])

```text id="f7xo7e"
temporary_problem.nl
  -> temporary_problem.sol
```

### 3.3.4 Log file: `_scip.log`

If no log file is provided, Pyomo creates a temporary file with suffix `_scip.log`. ([Pyomo Documentation][1])

```python id="6008vr"
results = opt.solve(model, tee=True, logfile="run/scip.log")
```

---

## 3.4 What SCIP receives

### 3.4.1 Command shape

Pyomo constructs the external command list as:

```text id="293qgd"
[executable, problem_file, "-AMPL"]
```

For SCIP version `>= 8.0.0`, Pyomo strips the `.nl` extension before passing the problem path; for older versions, it passes the `.nl` filename directly. ([Pyomo Documentation][1])

Equivalent shell shape:

```bash id="t8p4je"
scip /tmp/tmp_model -AMPL
```

Not:

```bash id="7js2jf"
scip /tmp/tmp_model.nl -AMPL   # not for SCIP >= 8 in Pyomo command construction
```

Version branch:

```text id="yxm5rz"
SCIP >= 8:
  input written by Pyomo: /tmp/tmp_model.nl
  command arg to SCIP:    /tmp/tmp_model
  command:                scip /tmp/tmp_model -AMPL

SCIP < 8:
  command arg:            /tmp/tmp_model.nl
  executable fallback:    scipampl if available
```

### 3.4.2 AMPL external function environment

Pyomo merges `PYOMO_AMPLFUNC` into `AMPLFUNC` in the environment before launching SCIP, preserving user-specified `AMPLFUNC` and appending Pyomo’s external function libraries when needed. ([Pyomo Documentation][1])

Deployment implication:

```text id="0o2jeo"
If Pyomo model uses external functions:
  preserve environment variables
  avoid clearing AMPLFUNC / PYOMO_AMPLFUNC in wrappers
  use micromamba run instead of manual subprocess env stripping
```

---

## 3.5 Options transport: `opt.options` → temporary `scip.set`

### 3.5.1 Syntax

```python id="8fsjbp"
opt = SolverFactory("scip")
opt.options["limits/time"] = 600
opt.options["limits/gap"] = 1e-4
opt.options["display/verblevel"] = 4

results = opt.solve(model, tee=True)
```

### 3.5.2 Internal transport

Pyomo iterates over `self.options`, formats each option as `key = value`, creates a temporary directory, writes a file named `scip.set`, and runs SCIP with that directory as the current working directory. ([Pyomo Documentation][1])

```text id="0dcqgx"
opt.options:
  {"limits/time": 300, "limits/gap": 0.001}
    ↓
temporary options_dir/scip.set:
  limits/time = 300
  limits/gap = 0.001
    ↓
SCIP working directory = options_dir
    ↓
SCIP auto-loads scip.set
```

### 3.5.3 Time limit aliasing

If Pyomo’s `_timelimit` is set and `limits/time` is not already present in `opt.options`, Pyomo writes `limits/time = <timelimit>` into the SCIP option file. ([Pyomo Documentation][1])

```python id="x09aqh"
# Preferred: explicit SCIP-native key
opt.options["limits/time"] = 300

# Also works through Pyomo solve kwarg in many SystemCallSolver flows
results = opt.solve(model, tee=True, timelimit=300)
```

Agent recommendation:

```text id="6jrxas"
For SCIP-specific code:
  prefer opt.options["limits/time"]
  prefer opt.options["limits/gap"]
  prefer explicit SCIP parameter names

For solver-generic wrappers:
  accept timelimit kwarg
  normalize to SCIP option when SolverFactory("scip")
```

### 3.5.4 `scip.set` collision warning

If `opt.options` is nonempty and a file named `scip.set` exists in the current working directory, Pyomo warns that the current-directory file will be ignored because Pyomo writes and uses its own temporary `scip.set`. ([Pyomo Documentation][1])

Deployment advisory:

```text id="wkk7l9"
Do not rely on ambient ./scip.set when using Pyomo opt.options.
Choose one strategy:

Strategy A, Pyomo-controlled:
  opt.options[...] = ...
  archive option dict
  ignore cwd scip.set

Strategy B, standalone SCIP-controlled:
  run scip directly
  manage scip.set yourself

Strategy C, strict reproducible Pyomo:
  fail if cwd/scip.set exists
  materialize opt.options from a versioned JSON/YAML manifest
```

---

## 3.6 Result processing

### 3.6.1 Primary result object

```python id="zk41jy"
results = opt.solve(model, tee=True)

print(results.solver.status)
print(results.solver.termination_condition)
print(results.solver.time)
print(getattr(results.solver, "gap", None))
print(getattr(results.solver, "primal_bound", None))
print(getattr(results.solver, "dual_bound", None))
```

### 3.6.2 Log-derived fields

For SCIP version `>= 8`, Pyomo writes the command line and captured solver log to the log file, parses the log, and stores solving time, gap, primal bound, and dual bound on the solver results when those fields are read. ([Pyomo Documentation][1])

```text id="fbjqvn"
SolverResults.solver:
  status
  termination_condition
  message
  time              # if parsed / available
  gap               # if parsed / available
  primal_bound      # if parsed / available
  dual_bound        # if parsed / available
```

### 3.6.3 Solution-file lifecycle

If `keepfiles=False`, Pyomo removes the derived `.sol` file after processing; if `keepfiles=True`, it preserves generated files. ([Pyomo Documentation][1])

```python id="jxh59o"
# Debug mode: preserve .nl/.sol/.row/.col/log artifacts
results = opt.solve(
    model,
    tee=True,
    keepfiles=True,
    symbolic_solver_labels=True,
    logfile="scip.log",
)
```

---

## 3.7 Declared Pyomo SCIP capabilities

Pyomo’s SCIP plugin sets these capability flags:

```python id="x0n23l"
linear = True
integer = True
quadratic_objective = True
quadratic_constraint = True
sos1 = True
sos2 = True
```

These flags are assigned in the SCIP plugin constructor. ([Pyomo Documentation][1])

Agent-side capability probe:

```python id="kfk78m"
opt = SolverFactory("scip")

for cap in [
    "linear",
    "integer",
    "quadratic_objective",
    "quadratic_constraint",
    "sos1",
    "sos2",
    "nonlinear",
    "warm_start",
]:
    print(cap, opt.has_capability(cap))
```

The public API documents `has_capability(cap)` as returning whether a solver supports a feature and defaulting to `False` if the solver is unaware of the option. ([Pyomo Documentation][3])

Interpretation:

```text id="xb6g92"
Capability flag meaning:
  Pyomo interface claims writer/solver path can support this feature family.

Capability flag non-meaning:
  not a guarantee of good performance
  not a guarantee of convexity
  not a guarantee of native SCIP plugin exposure
  not a guarantee of PySCIPOpt callback availability
  not a full SCIP feature inventory
```

---

## 3.8 NL writer controls relevant to SCIP

### 3.8.1 Determinism

NL writer option `file_determinism` controls effort spent ensuring deterministic file output; documented levels include `NONE`, `ORDERED`, `SORT_INDICES`, and `SORT_SYMBOLS`. ([Pyomo Documentation][2])

```python id="biv7xa"
model.write(
    "model.nl",
    format="nl",
    io_options={
        "symbolic_solver_labels": True,
        "file_determinism": 30,   # SORT_SYMBOLS
    },
)
```

Use for regression testing and artifact diffing.

### 3.8.2 Scaling

The NL writer can output model constraints and variables in “scaled space” using the `scaling_factor` suffix when `scale_model=True`, which is the default. ([Pyomo Documentation][2])

```python id="ydb2qj"
m.scaling_factor = Suffix(direction=Suffix.EXPORT)
m.scaling_factor[m.obj] = 0.001
m.scaling_factor[m.c1] = 100.0
```

Agent warning:

```text id="29urww"
Scaling affects exported NL representation.
When debugging solver logs vs Pyomo expressions:
  record scaling suffixes
  keep .row/.col
  keep NL file
```

### 3.8.3 Trivial constraints and linear presolve

The NL writer skips constant-body constraints by default via `skip_trivial_constraints=True`, and performs basic linear presolve via `linear_presolve=True` by default. ([Pyomo Documentation][2])

Debugging pattern:

```python id="2fddxf"
model.write(
    "debug_model.nl",
    format="nl",
    io_options={
        "symbolic_solver_labels": True,
        "skip_trivial_constraints": False,
        "linear_presolve": False,
    },
)
```

Use when the exported solver model appears not to contain a Pyomo component expected by an agent.

---

## 3.9 File-based interface limitation

### 3.9.1 What file-based means

```text id="xmv37m"
Each solve:
  Pyomo serializes model to disk
  Pyomo launches external process
  SCIP reads model from file
  SCIP solves from scratch
  SCIP writes solution file
  Pyomo parses solution
  external SCIP process exits

No persistent solver object:
  no retained branch-and-bound tree
  no retained presolved model
  no in-memory SCIP model
  no incremental add/remove constraint API
  no native callback/control surface
```

### 3.9.2 Consequence for repeated solves

Bad pattern for many tiny modifications:

```python id="qtw2mz"
for t in range(1000):
    model.p.set_value(t)
    results = SolverFactory("scip").solve(model)  # repeated factory + file write + process launch
```

Better file-based pattern:

```python id="kmhkkj"
opt = SolverFactory("scip")
opt.options["limits/time"] = 30

for t in range(1000):
    model.p.set_value(t)
    results = opt.solve(model, tee=False)
```

This reuses the Pyomo solver wrapper object but still writes files and launches a new SCIP process each solve.

### 3.9.3 Persistent solver contrast

Pyomo’s persistent solvers exist to efficiently notify a solver of incremental changes, create/store a solver-side model instance through the solver’s Python API, and avoid recreating/re-writing the full model each solve. ([Pyomo Documentation][4])

Persistent solver semantics:

```text id="r3r5rc"
Persistent solver:
  opt.set_instance(model)
  opt.add_constraint(...)
  opt.remove_constraint(...)
  opt.update_var(...)
  opt.solve()
  solver model persists in memory

SCIPAMPL:
  opt.solve(model)
  write .nl
  run scip process
  parse .sol
  no persistent SCIP model
```

GitHub source for Pyomo’s persistent solver base class says direct solver interfaces do not use file I/O and instead interface directly with the solver’s Python bindings; persistent solvers are similar but “remember” their model and allow incremental changes to the solver model. ([GitHub][5])

---

## 3.10 APPSI limitation: no current SCIP APPSI solver export

APPSI means “Auto-Persistent Pyomo Solver Interfaces”; its docs state these interfaces are efficient for resolving the same model with small changes and list current solver pages for Gurobi, Ipopt, Cplex, Cbc, HiGHS, and MAiNGO. SCIP is not listed in that APPSI solver list. ([Pyomo Documentation][6])

```text id="wxbwyx"
APPSI value case:
  repeated solve
  small model mutations
  Benders
  OBBT
  Progressive Hedging
  Outer Approximation
  persistent/auto-persistent solver state

Current APPSI SCIP status:
  no documented APPSI SCIP solver in Pyomo solver list
```

Agent routing:

```text id="k8lynj"
If user asks:
  “efficient repeated Pyomo+SCIP resolves with incremental model changes”
Then answer:
  Pyomo's current SCIP interface is file-based.
  APPSI is the right architectural idea, but current APPSI solver list does not include SCIP.
  Options:
    accept file-based overhead
    use PySCIPOpt directly
    use another APPSI-supported solver if model class permits
    implement custom bridge only if necessary
```

---

## 3.11 Practical interface selection matrix

| Need                           | Recommended interface          | Syntax                                                      |
| ------------------------------ | ------------------------------ | ----------------------------------------------------------- |
| basic Pyomo MIP/MINLP solve    | SCIPAMPL file-based            | `SolverFactory("scip")`                                     |
| force explicit NL path         | SCIPAMPL with solver_io        | `SolverFactory("scip", solver_io="nl")`                     |
| inspect generated solver files | keepfiles + labels             | `opt.solve(m, keepfiles=True, symbolic_solver_labels=True)` |
| tune SCIP options              | Pyomo option dict              | `opt.options["limits/time"] = 300`                          |
| repeated small model changes   | APPSI if solver supports model | `appsi.solvers.Highs()`, etc.; no SCIP listed               |
| native SCIP callbacks/plugins  | PySCIPOpt or C/C++             | `from pyscipopt import Model`                               |
| exact control over SCIP shell  | standalone `scip`              | `scip model -AMPL` / shell commands                         |

---

## 3.12 Debugging map: expected artifacts

### 3.12.1 With default `keepfiles=False`

```text id="ox8t4x"
temporary .nl:
  created
  usually deleted

temporary .sol:
  created by SCIP
  parsed by Pyomo
  deleted after processing

temporary _scip.log:
  created or captured
  may be deleted unless logfile explicitly provided

.row/.col:
  only if symbolic_solver_labels=True
  usually deleted with tempfiles unless keepfiles=True
```

### 3.12.2 With debug settings

```python id="63zdce"
results = opt.solve(
    model,
    tee=True,
    keepfiles=True,
    symbolic_solver_labels=True,
    logfile="debug_scip.log",
)
```

Expected useful artifacts:

```text id="0nr95g"
*.nl       exported model
*.row      constraint/objective names
*.col      variable names
*.sol      SCIP solution file
*.log      SCIP log + command line
scip.set   temporary options file, if preserved/inspected through keepfiles/log output
```

### 3.12.3 Artifact triage

```text id="5op9vi"
If SCIP says row infeasible:
  use .row to map row index/name to Pyomo constraint

If variable value missing/suspicious:
  use .col to map solver variable order to Pyomo variable

If options not applied:
  inspect log command line
  inspect generated scip.set behavior
  confirm opt.options keys

If model differs run-to-run:
  set symbolic_solver_labels=True
  set deterministic NL writer options
  archive data ordering
```

---

## 3.13 Common failure modes

| Symptom                                           | Likely root cause                                | Probe                                       | Fix                                                             |
| ------------------------------------------------- | ------------------------------------------------ | ------------------------------------------- | --------------------------------------------------------------- |
| `SolverFactory("scip").available(False) == False` | no `scip`/`scipampl` on PATH                     | `which scip`; `opt.executable()`            | install/activate env                                            |
| `scip --version` works but Pyomo fails            | Python and `scip` from different envs            | print `sys.executable`, `opt.executable()`  | use `micromamba run -n env python ...`                          |
| `scip.set` ignored                                | Pyomo wrote temp options file                    | look for Pyomo warning                      | pass all options via `opt.options`                              |
| `.row/.col` missing                               | labels not enabled                               | check solve kwargs                          | `symbolic_solver_labels=True`                                   |
| `.sol` missing error                              | SCIP failed before solution file creation        | inspect log and command line                | validate model/export/options                                   |
| repeated solve too slow                           | file-based interface overhead                    | profile NL writing + process time           | use fewer resolves, batch, PySCIPOpt, or APPSI-supported solver |
| callback request impossible                       | SCIPAMPL not native API                          | inspect interface type                      | use PySCIPOpt/native SCIP                                       |
| model component absent from NL                    | NL writer skipped/presolved/exported differently | write debug NL with labels and presolve off | adjust writer options/model                                     |

---

## 3.14 Agent-ready canonical wrapper

```python id="wjqxil"
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pyomo.environ import SolverFactory
from pyomo.opt import SolverStatus, TerminationCondition


@dataclass(frozen=True)
class ScipSolveConfig:
    time_limit: float | None = None
    mip_gap: float | None = None
    tee: bool = True
    keepfiles: bool = False
    symbolic_solver_labels: bool = False
    logfile: str | None = None


def make_scip_solver(cfg: ScipSolveConfig):
    opt = SolverFactory("scip", solver_io="nl")

    if not opt.available(False):
        raise RuntimeError(
            "SCIP unavailable to Pyomo. Install/activate conda-forge::scip "
            "and verify `scip --version` plus SolverFactory('scip').available()."
        )

    if cfg.time_limit is not None:
        opt.options["limits/time"] = cfg.time_limit

    if cfg.mip_gap is not None:
        opt.options["limits/gap"] = cfg.mip_gap

    return opt


def solve_with_scip(model: Any, cfg: ScipSolveConfig):
    opt = make_scip_solver(cfg)

    results = opt.solve(
        model,
        tee=cfg.tee,
        keepfiles=cfg.keepfiles,
        symbolic_solver_labels=cfg.symbolic_solver_labels,
        logfile=cfg.logfile,
    )

    status = results.solver.status
    tc = results.solver.termination_condition

    acceptable = {
        TerminationCondition.optimal,
        TerminationCondition.feasible,
        TerminationCondition.maxTimeLimit,
    }

    if status != SolverStatus.ok and tc not in acceptable:
        raise RuntimeError(f"SCIP solve failed: status={status}, termination={tc}")

    return results
```

---

## 3.15 Minimal test harness

```python id="xqlqdb"
from pyomo.environ import *
from pyomo.opt import SolverStatus, TerminationCondition

def build_smoke_model():
    m = ConcreteModel()
    m.x = Var(domain=Binary)
    m.y = Var(bounds=(0, None))
    m.obj = Objective(expr=3*m.x + m.y, sense=maximize)
    m.c = Constraint(expr=2*m.x + m.y <= 4)
    return m

def test_scip_available_and_solves():
    m = build_smoke_model()
    opt = SolverFactory("scip", solver_io="nl")

    assert opt.available(False)
    assert opt.executable() is not None

    res = opt.solve(m, tee=False)

    assert res.solver.status == SolverStatus.ok
    assert res.solver.termination_condition == TerminationCondition.optimal
    assert abs(value(m.obj) - 5.0) <= 1e-7
```

---

## 3.16 Compact mental model

```text id="r6z47x"
Pyomo + SCIP:
  not in-process
  not PySCIPOpt
  not APPSI
  not persistent

It is:
  Pyomo model
  -> NLWriter
  -> .nl (+ optional .row/.col)
  -> external scip/scipampl command
  -> -AMPL mode
  -> .sol
  -> Pyomo SolverResults
  -> optional model variable loading

Best default:
  opt = SolverFactory("scip", solver_io="nl")
  opt.options["limits/time"] = ...
  opt.options["limits/gap"] = ...
  opt.solve(model, tee=True)

Best debug:
  keepfiles=True
  symbolic_solver_labels=True
  logfile="scip.log"

Best repeated-solve warning:
  file-based overhead persists each solve;
  APPSI solves this class of problem generally,
  but current APPSI solver docs do not list SCIP.
```

[1]: https://pyomo.readthedocs.io/en/6.8.2/_modules/pyomo/solvers/plugins/solvers/SCIPAMPL.html "pyomo.solvers.plugins.solvers.SCIPAMPL — Pyomo 6.8.2 documentation"
[2]: https://pyomo.readthedocs.io/en/6.8.2/api/pyomo.repn.plugins.nl_writer.NLWriter.html "NLWriter — Pyomo 6.8.2 documentation"
[3]: https://pyomo.readthedocs.io/en/latest/api/pyomo.solvers.plugins.solvers.SCIPAMPL.SCIPAMPL.html "SCIPAMPL — Pyomo 6.10.1.dev0 documentation"
[4]: https://pyomo.readthedocs.io/en/6.8.0/advanced_topics/persistent_solvers.html "Persistent Solvers — Pyomo 6.8.0 documentation"
[5]: https://github.com/Pyomo/pyomo/blob/master/pyomo/solvers/plugins/solvers/persistent_solver.py "pyomo/pyomo/solvers/plugins/solvers/persistent_solver.py at main · Pyomo/pyomo · GitHub"
[6]: https://pyomo.readthedocs.io/en/stable/reference/topical/appsi/appsi.html "APPSI — Pyomo 6.10.0 documentation"

# 4) Model classes in Pyomo that map well to SCIP — formulation, syntax, routing, deployment guidance

Reference style follows the uploaded advanced technical-doc template. 

---

## 4.0 Core routing invariant

```text id="m5x41c"
Pyomo model class -> SCIP fit:
  MILP/MIP                         excellent default fit
  MIQP / MIQCP-style quadratic     good fit; convexity/scale/bounds matter
  MINLP                            good open-source fit; nonlinear structure matters heavily
  SOS1/SOS2                        supported by Pyomo SCIP plugin
  GDP/logical/indicator            transform to MILP/MINLP before solve
  Piecewise-linear                 good fit; choose representation deliberately

Pyomo SCIP interface:
  SolverFactory("scip")
  file-based .nl -> scip -AMPL -> .sol
  declared Pyomo capability flags:
    linear
    integer
    quadratic_objective
    quadratic_constraint
    sos1
    sos2
```

Pyomo’s SCIP plugin declares valid NL problem format and sets capability flags for `linear`, `integer`, `quadratic_objective`, `quadratic_constraint`, `sos1`, and `sos2`; these flags are interface declarations, not a guarantee that every native SCIP feature is reachable through Pyomo’s file-based interface. ([Pyomo Documentation][1])

---

## 4.1 MILP / MIP

### 4.1.1 Model signature

```text id="se3o6j"
MILP:
  variables:
    continuous: Reals / NonNegativeReals / bounds=(lb, ub)
    integer: Integers / NonNegativeIntegers
    binary: Binary
  constraints:
    affine linear
  objective:
    affine linear
```

Pyomo `Var` accepts a `domain` set such as `Reals`, `NonNegativeReals`, or `Binary`, and accepts explicit bounds through `bounds=(lower, upper)` or a bounds rule. ([Pyomo Documentation][2])

### 4.1.2 Canonical Pyomo syntax

```python id="i7mkvw"
from pyomo.environ import *

m = ConcreteModel()

m.I = RangeSet(4)

# domains
m.x = Var(m.I, domain=Binary)
m.y = Var(m.I, domain=NonNegativeIntegers, bounds=(0, 10))
m.z = Var(domain=NonNegativeReals)

# linear objective
m.obj = Objective(
    expr=sum([4, 7, 2, 9][i-1] * m.x[i] for i in m.I)
       + sum(0.5 * m.y[i] for i in m.I)
       + 3.0 * m.z,
    sense=maximize,
)

# linear constraints
m.capacity = Constraint(
    expr=sum([3, 5, 2, 6][i-1] * m.x[i] for i in m.I)
       + sum(m.y[i] for i in m.I)
       + m.z <= 12
)

m.link = Constraint(m.I, rule=lambda m, i: m.y[i] <= 10 * m.x[i])

opt = SolverFactory("scip")
opt.options["limits/time"] = 300
results = opt.solve(m, tee=True)
```

### 4.1.3 Value case for SCIP

```text id="novzjq"
SCIP value for MILP:
  strong presolve
  domain propagation
  cutting planes
  primal heuristics
  conflict analysis
  robust branch-and-bound / branch-and-cut
  open-source conda deployability
  good default for difficult combinatorial Pyomo models
```

### 4.1.4 MILP formulation best practices

```text id="rsno1p"
Always:
  use Binary for 0/1 decisions, not bounds=(0,1) continuous variables
  use finite, tight bounds on integer/continuous variables
  replace loose big-M with tight M from data
  avoid products of decision variables unless intentionally MIQP/MINLP
  scale coefficients into sane numeric ranges
  isolate optional constraints behind binary logic carefully
  validate objective/constraint polynomial degree before solver call
```

### 4.1.5 Anti-patterns

```python id="krwh1w"
# Bad: continuous variable masquerading as binary
m.x = Var(bounds=(0, 1))  # relaxation only; not binary

# Good
m.x = Var(domain=Binary)
```

```python id="cwpyhx"
# Bad: unnecessary nonlinear product in a MILP
m.c = Constraint(expr=m.x_binary * m.y_continuous <= 5)

# Better: linearize if y has known bounds
m.w = Var(bounds=(0, Y_UB))
m.c1 = Constraint(expr=m.w <= Y_UB * m.x_binary)
m.c2 = Constraint(expr=m.w <= m.y_continuous)
m.c3 = Constraint(expr=m.w >= m.y_continuous - Y_UB * (1 - m.x_binary))
m.c4 = Constraint(expr=m.w >= 0)
```

---

## 4.2 MIQP / quadratic models

### 4.2.1 Model signatures

```text id="iwvmko"
MIQP:
  objective: quadratic
  constraints: linear
  variables: continuous + integer/binary

MIQCP / QCQP-style:
  objective: linear or quadratic
  constraints: linear + quadratic
  variables: continuous + integer/binary
```

Pyomo SCIP explicitly declares support for quadratic objectives and quadratic constraints through the `SCIPAMPL` capability flags. ([Pyomo Documentation][1])

### 4.2.2 Quadratic objective syntax

```python id="r1ow1z"
from pyomo.environ import *

m = ConcreteModel()
m.I = RangeSet(3)

m.x = Var(m.I, domain=Binary)
m.y = Var(bounds=(-10, 10))

# MIQP: binary variables + quadratic objective
m.obj = Objective(
    expr=(m.y - 2.0)**2
       + 3.0 * m.x[1]
       + 5.0 * m.x[2]
       + 7.0 * m.x[3],
    sense=minimize,
)

m.c = Constraint(expr=sum(m.x[i] for i in m.I) >= 1)

SolverFactory("scip").solve(m, tee=True)
```

### 4.2.3 Quadratic constraint syntax

```python id="i4ygu6"
from pyomo.environ import *

m = ConcreteModel()

m.x = Var(bounds=(-5, 5))
m.y = Var(bounds=(-5, 5))
m.z = Var(domain=Binary)

m.obj = Objective(expr=m.x + 2*m.y + 10*m.z)

# MIQCP-style quadratic constraint
m.ball = Constraint(expr=m.x**2 + m.y**2 <= 4 + 100*m.z)

SolverFactory("scip").solve(m, tee=True)
```

### 4.2.4 Convex vs nonconvex implications

```text id="r6f9ff"
Convex quadratic:
  minimization objective with PSD Hessian
  convex <= quadratic constraints of suitable form
  continuous relaxation easier
  commercial QP/QCP solvers often strong

Nonconvex quadratic:
  bilinear terms
  indefinite Hessian
  binary-continuous products
  quadratic equalities
  harder global optimization behavior
  bound quality becomes critical
```

### 4.2.5 Binary-continuous product routing

```text id="yt9tdx"
x ∈ {0,1}, 0 ≤ y ≤ U, w = x*y

If solver/formulation target = MILP:
  use McCormick/big-M linearization

If solver target = MINLP/MIQP and bounds tight:
  product may be left nonlinear/quadratic

Default agent policy:
  linearize binary-continuous products when exact linearization is cheap
```

```python id="r3eaxs"
# Exact linearization for w = x*y, x binary, 0 <= y <= U
m.x = Var(domain=Binary)
m.y = Var(bounds=(0, U))
m.w = Var(bounds=(0, U))

m.lin1 = Constraint(expr=m.w <= U * m.x)
m.lin2 = Constraint(expr=m.w <= m.y)
m.lin3 = Constraint(expr=m.w >= m.y - U * (1 - m.x))
m.lin4 = Constraint(expr=m.w >= 0)
```

### 4.2.6 Quadratic routing advisory

```text id="jz9pnx"
Use SCIP:
  MIQP/MIQCP with mixed-integer structure
  nonconvex or discrete structure where open-source solver needed
  quadratic constraints plus combinatorial logic
  Pyomo portability desired

Use HiGHS:
  LP/MIP/QP emphasis, especially sparse linear optimization and QP without nonlinear generality

Use Gurobi/CPLEX:
  high-performance commercial LP/MIP/QP/QCP/MIQP/MIQCP
  licensed production workloads
  strong convex QP/QCP infrastructure
```

HiGHS describes itself as software for large-scale sparse LP, MIP, and QP models; Gurobi documents LP/QP/QCP continuous model classes and MIP/MIQP/MIQCP discrete model classes; IBM CPLEX documentation describes LP, QP, QCP, and MIP models, including MIQP and MIQCP terminology. ([highs.dev][3])

---

## 4.3 MINLP

### 4.3.1 Model signature

```text id="oif5a1"
MINLP:
  variables:
    continuous + integer/binary
  expressions:
    nonlinear objective and/or constraints
  examples:
    log(x)
    exp(x)
    sqrt(x)
    x*y
    x**a
    nonlinear equality
    nonlinear inequality
    nonlinear disjunction after GDP transformation
```

### 4.3.2 Pyomo syntax

```python id="k21k1f"
from pyomo.environ import *

m = ConcreteModel()

m.x = Var(bounds=(0.1, 10.0))
m.y = Var(bounds=(0.1, 10.0))
m.z = Var(domain=Binary)

m.obj = Objective(expr=(m.x - 3)**2 + exp(m.y / 10) + 20*m.z)

m.c1 = Constraint(expr=log(m.x) + m.z >= 1.0)
m.c2 = Constraint(expr=m.x * m.y <= 12 + 100*m.z)

opt = SolverFactory("scip")
opt.options["limits/time"] = 600
res = opt.solve(m, tee=True)
```

### 4.3.3 MINLP value case for SCIP

```text id="hdo41p"
SCIP is appropriate when:
  integer/binary decisions are intrinsic
  nonlinear constraints/objective cannot be cleanly linearized
  global/discrete search is needed
  open-source deployment matters
  finite bounds exist for nonlinear variables
  model size moderate enough for branch-and-bound search
```

### 4.3.4 MINLP model hygiene

```text id="sjkr2v"
Required:
  finite lower/upper bounds for nonlinear variables
  domain-safe expressions:
    log(x): x.lb > 0
    sqrt(x): x.lb >= 0
    division 1/x: exclude x = 0
    x**a fractional: enforce domain
  avoid unbounded nonlinear products
  provide good initial values for difficult nonlinear expressions
  scale nonlinear expressions and objective terms
```

```python id="f24xlt"
m.x = Var(bounds=(1e-3, 100), initialize=1.0)  # safe for log(x)
m.y = Var(bounds=(0, 50), initialize=5.0)      # safe for sqrt(y)
m.c = Constraint(expr=log(m.x) + sqrt(m.y) <= 4)
```

### 4.3.5 Solver routing: SCIP vs alternatives

```text id="n1ees0"
SCIP:
  mixed-integer nonlinear, open-source, global/discrete tree-search orientation
  good Pyomo default for bounded MINLP with combinatorial structure

IPOPT:
  continuous nonlinear programming only; local NLP solutions
  use for NLP relaxations or models without integer variables

BONMIN:
  COIN-OR MINLP solver; useful for convex/general MINLP experiments; older ecosystem

Couenne:
  global optimization for nonconvex MINLP via branch-and-bound, linearization, bound reduction

HiGHS:
  LP/MIP/QP; not a general MINLP solver

Gurobi/CPLEX:
  strong commercial LP/MIP/QP/QCP/MIQP/MIQCP
  not general-purpose symbolic MINLP in the same sense as Pyomo+SCIP/Couenne
```

Ipopt is a large-scale nonlinear optimization solver for problems with continuous variables and smooth functions; BONMIN is a COIN-OR code for general MINLP; Couenne targets global optima of nonconvex MINLPs using linearization, bound reduction, and branch-and-bound methods; HiGHS targets LP, MIP, and QP, not general symbolic MINLP. ([GitHub][4])

### 4.3.6 Agent decision rule

```text id="y5th4n"
If no integer/binary variables:
  try IPOPT for continuous NLP first
  use SCIP only if global/discrete or file-format consistency needed

If linear + integer only:
  use MILP path; compare HiGHS/CBC/SCIP/Gurobi/CPLEX

If quadratic + integer only:
  use MIQP/MIQCP path; compare SCIP/Gurobi/CPLEX/HiGHS depending structure

If nonlinear + integer:
  use SCIP / Couenne / BONMIN / commercial MINLP if available
  ensure finite bounds
  consider linearization/reformulation first
```

---

## 4.4 SOS1 / SOS2

### 4.4.1 Semantic definition

```text id="h6gq3i"
SOS1:
  at most one variable in ordered set can be nonzero

SOS2:
  at most two variables can be nonzero
  if two are nonzero, they must be adjacent in ordered set
```

Pyomo documents SOS constraints as ordered sets of variables where only a limited number can be nonzero and, for higher SOS types, nonzero variables must be adjacent; Pyomo supports explicit SOS declarations with `SOSConstraint`. ([Pyomo Documentation][5])

### 4.4.2 Non-indexed SOS syntax

```python id="vyukmn"
from pyomo.environ import *

m = ConcreteModel()
m.K = RangeSet(5)

m.lam = Var(m.K, bounds=(0, 1))

# Sum-to-one often paired with convex combination
m.sum_lam = Constraint(expr=sum(m.lam[k] for k in m.K) == 1)

# SOS2 adjacency structure
m.sos2 = SOSConstraint(var=m.lam, sos=2)

SolverFactory("scip").solve(m, tee=True)
```

### 4.4.3 SOS with explicit weights

```python id="f1iher"
from pyomo.environ import *

m = ConcreteModel()
m.K = RangeSet(5)

m.x = Var(m.K, bounds=(0, None))
m.w = Param(m.K, initialize={1: 0.0, 2: 1.0, 3: 2.0, 4: 4.0, 5: 8.0})

m.sos = SOSConstraint(var=m.x, sos=2, weights=m.w)
```

Pyomo allows SOS weights to be specified through a `Param`; otherwise weights are determined automatically from variable order. ([Pyomo Documentation][5])

### 4.4.4 Indexed SOS syntax

```python id="z2zwzf"
from pyomo.environ import *

m = ConcreteModel()
m.I = Set(initialize=["a", "b"])
m.K = RangeSet(4)

m.x = Var(m.I, m.K, bounds=(0, 1))

def sos_rule(m, i):
    return [m.x[i, k] for k in m.K]

m.sos2 = SOSConstraint(m.I, rule=sos_rule, sos=2)
```

### 4.4.5 Why SOS maps well to SCIP

```text id="kss37v"
SCIP Pyomo plugin declares:
  sos1 = True
  sos2 = True

Use SOS2 for:
  piecewise-linear interpolation
  convex-combination formulations
  ordered regime selection
  adjacent breakpoint selection

Use SOS1 for:
  choose-one among continuous alternatives
  sparse activity selection
  alternative linear pieces
```

Pyomo’s SCIP plugin explicitly declares `sos1` and `sos2` capability flags. ([Pyomo Documentation][1])

---

## 4.5 Indicator / logical constraints

### 4.5.1 Key interface reality

```text id="xz58kr"
Pyomo + SCIP through SolverFactory("scip"):
  use algebraic reformulations or GDP transformations
  do not assume a direct native SCIP indicator-constraint callback/API path

Logical modeling routes:
  BooleanVar / LogicalConstraint
  Disjunct / Disjunction
  TransformationFactory("core.logical_to_linear")
  TransformationFactory("contrib.logical_to_disjunctive")
  TransformationFactory("gdp.bigm")
  TransformationFactory("gdp.hull")
  manual big-M / convex-hull linearization
```

Pyomo GDP documentation recommends passing mixed logical/algebraic models to MI(N)LP reformulations or GDPopt directly; it describes logical-to-linear transformations and Big-M/Hull reformulations for converting disjunctive models to standard MILP/MINLP form. ([Pyomo Documentation][6])

### 4.5.2 Manual implication syntax

Target logic:

```text id="a9lv9w"
z = 0 -> x = 0
z = 1 -> 0 <= x <= U
```

Linear formulation:

```python id="k8vlf7"
m.z = Var(domain=Binary)
m.x = Var(bounds=(0, U))

m.ind = Constraint(expr=m.x <= U * m.z)
```

Target logic:

```text id="uy410c"
z = 1 -> aᵀx <= b
```

Big-M formulation:

```python id="23tfm0"
m.z = Var(domain=Binary)

# M must be valid and tight
m.ind = Constraint(expr=sum(a[i] * m.x[i] for i in m.I) <= b + M * (1 - m.z))
```

### 4.5.3 Big-M selection

```text id="f5g7ky"
M must be:
  valid: does not cut off feasible intended solutions
  tight: as small as possible
  scale-compatible: not 1e9 unless units truly require it
  data-derived: computed from bounds, not guessed
```

```python id="8gyx5v"
def linear_expr_upper_bound(a, lb, ub):
    # upper bound for sum_i a_i*x_i using variable bounds
    total = 0.0
    for i, ai in a.items():
        total += ai * (ub[i] if ai >= 0 else lb[i])
    return total

M = linear_expr_upper_bound(a, lb, ub) - b
M = max(0.0, M)
```

Pyomo’s Big-M GDP transformation documents an M selection hierarchy: explicit `bigM` arguments, `BigM` suffixes, and, for linear constraints, estimation from variable bounds when possible. ([Pyomo Documentation][7])

### 4.5.4 GDP Big-M syntax

```python id="bqywnj"
from pyomo.environ import *
from pyomo.gdp import Disjunct, Disjunction

m = ConcreteModel()

m.x = Var(bounds=(0, 10))
m.y = Var(bounds=(0, 10))

m.left = Disjunct()
m.left.c = Constraint(expr=m.x + m.y <= 3)

m.right = Disjunct()
m.right.c = Constraint(expr=m.x - m.y >= 2)

m.choice = Disjunction(expr=[m.left, m.right])

# Reformulate to MILP/MINLP using Big-M
TransformationFactory("gdp.bigm").apply_to(m)

SolverFactory("scip").solve(m, tee=True)
```

### 4.5.5 GDP Hull syntax

```python id="cprst8"
from pyomo.environ import *
from pyomo.gdp import Disjunct, Disjunction

# build GDP model...

TransformationFactory("gdp.hull").apply_to(m)
SolverFactory("scip").solve(m, tee=True)
```

### 4.5.6 Big-M vs Hull decision

```text id="gyo1o6"
Big-M:
  smaller formulation
  fewer variables
  weaker continuous relaxation
  M quality critical
  good when bounds are tight and disjunctions are many/simple

Hull:
  larger formulation
  stronger continuous relaxation
  better root bounds
  often more robust for nonlinear/disjunctive structure
  requires bounded variables in disjunctive terms

Cutting-plane hybrid:
  linear GDP only
  tries to strengthen BM without full HR size
```

Pyomo GDP docs state that Big-M reformulation is smaller but yields looser continuous relaxations, and that Big-M can estimate reasonably tight M values when variables are bounded; missing M values for unsupported cases raise GDP errors. ([Pyomo Documentation][6])

### 4.5.7 When to linearize manually

```text id="b7624i"
Manual linearization preferred when:
  implication pattern simple
  M values easy and tight
  performance-critical model
  transformation output too large/opaque
  you need stable names and artifact debugging
  you want solver-independent MILP

GDP transformation preferred when:
  model logic is complex
  many disjunctions
  maintainability > hand-coded constraints
  algebraic alternatives are naturally disjunctive
  agents risk writing incorrect manual logic
```

---

## 4.6 Piecewise-linear models

### 4.6.1 Pyomo `Piecewise` capability

Pyomo `Piecewise` constructs constraints of the form:

```text id="jffmke"
y = f(x)
y <= f(x)
y >= f(x)
```

Core arguments:

```text id="b31064"
Piecewise(
  optional_index_sets,
  yvar,
  xvar,
  pw_pts=breakpoints,
  f_rule=function_or_values,
  pw_constr_type="EQ" | "UB" | "LB",
  pw_repn="SOS2" | "BIGM_BIN" | "BIGM_SOS1" | "DCC" | "DLOG" | "CC" | "LOG" | "MC" | "INC",
)
```

Pyomo’s `Piecewise` API requires `pw_pts`, uses `pw_repn` to choose the formulation, and documents options including `SOS2`, `BIGM_BIN`, `BIGM_SOS1`, `DCC`, `DLOG`, `CC`, `LOG`, `MC`, and `INC`; it also notes that representation choice can have a major performance impact. ([Pyomo Documentation][8])

### 4.6.2 Basic SOS2 piecewise syntax

```python id="yzw8mi"
from pyomo.environ import *

m = ConcreteModel()

m.x = Var(bounds=(0, 4))
m.y = Var()

breakpoints = [0, 1, 2, 3, 4]
values = [0, 1, 4, 9, 16]

m.pw = Piecewise(
    m.y,
    m.x,
    pw_pts=breakpoints,
    f_rule=values,
    pw_constr_type="EQ",
    pw_repn="SOS2",
)

m.obj = Objective(expr=m.y)
SolverFactory("scip").solve(m, tee=True)
```

### 4.6.3 Indexed piecewise syntax

```python id="f5skul"
from pyomo.environ import *

m = ConcreteModel()

m.I = RangeSet(3)
m.x = Var(m.I, bounds=(0, 4))
m.y = Var(m.I)

pts = [0, 1, 2, 3, 4]

def f_rule(m, i, x):
    return i * x**2

m.pw = Piecewise(
    m.I,
    m.y,
    m.x,
    pw_pts=pts,
    f_rule=f_rule,
    pw_constr_type="EQ",
    pw_repn="SOS2",
)

m.obj = Objective(expr=sum(m.y[i] for i in m.I))
```

### 4.6.4 Representation selection

```text id="ca5wfl"
SOS2:
  standard SOS2 formulation
  compact
  relies on solver SOS2 handling
  natural fit for SCIP because Pyomo SCIP declares sos2=True

BIGM_BIN:
  big-M constraints + binary variables
  theoretically tightest M values automatically determined by Pyomo
  can be fast if M values strong
  can be numerically risky if breakpoints/scales poor

BIGM_SOS1:
  big-M + SOS1 variables
  solver SOS1 support required

CC:
  convex combination formulation
  often transparent and solver-independent

DCC:
  disaggregated convex combination
  stronger/larger formulation
  supports step functions

LOG / DLOG:
  logarithmic formulations
  fewer binaries for many breakpoints
  more complex structure
  breakpoint count restrictions may apply

INC:
  incremental/delta method
  useful for ordered piecewise structures
```

Pyomo documents `SOS2` as the standard SOS2 representation, `BIGM_BIN` and `BIGM_SOS1` as Big-M formulations with automatically determined theoretically tightest M values, and `DCC`, `DLOG`, `CC`, `LOG`, `MC`, and `INC` as alternative formulations. ([Pyomo Documentation][8])

### 4.6.5 Piecewise formulation decision rule

```text id="x12ws0"
Default with SCIP:
  pw_repn="SOS2"

Use DCC/CC when:
  solver SOS handling uncertain
  want explicit linear algebraic formulation
  debugging formulation
  stronger relaxation preferred

Use DLOG/LOG when:
  many breakpoints
  binary count matters
  logarithmic formulation assumptions satisfied

Use BIGM_BIN only when:
  breakpoints/bounds/scales clean
  formulation tested against known solutions
  generated M values inspected or trusted
```

### 4.6.6 Breakpoint hygiene

```text id="xcwj18"
Always:
  sort breakpoints strictly increasing
  cover full x variable bounds
  avoid extrapolation unless intentional
  use finite x bounds
  scale x and y values
  test at breakpoints
  test interpolation midpoints
  snapshot generated model for production
```

```python id="n14jjf"
def validate_piecewise_points(points, x_lb, x_ub):
    assert len(points) >= 2
    assert all(points[i] < points[i+1] for i in range(len(points)-1))
    assert points[0] <= x_lb
    assert points[-1] >= x_ub
```

---

## 4.7 Unified model-class decision table

| Model pattern                                 | Pyomo construct                                                        |                        SCIP fit | Preferred representation |
| --------------------------------------------- | ---------------------------------------------------------------------- | ------------------------------: | ------------------------ |
| binary/integer + linear constraints/objective | `Var(domain=Binary/Integers)`, linear `Constraint`, linear `Objective` |                       excellent | MILP                     |
| continuous + linear only                      | linear Pyomo model                                                     |   good, but HiGHS often simpler | LP                       |
| integer + quadratic objective                 | quadratic `Objective`                                                  |                            good | MIQP                     |
| integer + quadratic constraints               | quadratic `Constraint`                                                 |  good; bounds/scaling important | MIQCP-style              |
| continuous nonlinear only                     | nonlinear expressions, no integer vars                                 | possible, but IPOPT often first | NLP                      |
| integer + nonlinear                           | nonlinear expressions + Binary/Integers                                |            good open-source fit | MINLP                    |
| ordered adjacent breakpoint selection         | `SOSConstraint(..., sos=2)`                                            |                            good | SOS2                     |
| choose one continuous alternative             | `SOSConstraint(..., sos=1)` or binaries                                |                            good | SOS1 / MILP              |
| if-then logic                                 | GDP / manual implication                                               |        good after reformulation | Big-M/Hull/MILP          |
| piecewise-linear equality                     | `Piecewise(..., pw_repn="SOS2")`                                       |                            good | SOS2 default             |
| large piecewise many breakpoints              | `Piecewise(..., pw_repn="DLOG"/"LOG")`                                 |                 model-dependent | logarithmic formulation  |

---

## 4.8 Agent-side classification utility

Use this before solver routing or before claiming “MILP” vs “MIQP” vs “MINLP”.

```python id="ebfi94"
from pyomo.environ import Var, Constraint, Objective
from pyomo.core.expr.visitor import identify_variables

def expression_degree(expr):
    """
    Returns:
      0 for constant,
      1 for linear,
      2 for quadratic,
      None for non-polynomial or unknown degree.
    """
    return expr.polynomial_degree()

def model_degree_summary(model):
    rows = []

    for obj in model.component_data_objects(Objective, active=True):
        rows.append(("objective", obj.name, expression_degree(obj.expr)))

    for con in model.component_data_objects(Constraint, active=True):
        if con.body is not None:
            rows.append(("constraint", con.name, expression_degree(con.body)))

    has_binary = False
    has_integer = False

    for v in model.component_data_objects(Var, descend_into=True):
        if v.is_binary():
            has_binary = True
        elif v.is_integer():
            has_integer = True

    max_degree = None
    saw_unknown = False
    for _, _, deg in rows:
        if deg is None:
            saw_unknown = True
        else:
            max_degree = deg if max_degree is None else max(max_degree, deg)

    if saw_unknown:
        algebra = "nonlinear_or_unknown"
    elif max_degree is None or max_degree <= 1:
        algebra = "linear"
    elif max_degree == 2:
        algebra = "quadratic"
    else:
        algebra = f"polynomial_degree_{max_degree}"

    if has_binary or has_integer:
        discrete = "mixed_integer"
    else:
        discrete = "continuous"

    return {
        "algebra": algebra,
        "discrete": discrete,
        "has_binary": has_binary,
        "has_integer": has_integer,
        "rows": rows,
    }
```

Routing:

```python id="jwtn5a"
summary = model_degree_summary(model)

if summary["algebra"] == "linear" and summary["discrete"] == "mixed_integer":
    model_class = "MILP"
elif summary["algebra"] == "quadratic" and summary["discrete"] == "mixed_integer":
    model_class = "MIQP/MIQCP"
elif summary["algebra"] == "nonlinear_or_unknown" and summary["discrete"] == "mixed_integer":
    model_class = "MINLP"
elif summary["algebra"] == "nonlinear_or_unknown":
    model_class = "NLP"
else:
    model_class = "LP/QP/other"

print(model_class)
```

---

## 4.9 Capability probe for SCIP in Pyomo

```python id="k8qck9"
from pyomo.environ import SolverFactory

opt = SolverFactory("scip", solver_io="nl")

required = [
    "linear",
    "integer",
    "quadratic_objective",
    "quadratic_constraint",
    "sos1",
    "sos2",
]

for cap in required:
    print(cap, opt.has_capability(cap))
```

Expected for the Pyomo SCIP plugin:

```text id="m0un9a"
linear=True
integer=True
quadratic_objective=True
quadratic_constraint=True
sos1=True
sos2=True
```

The `SCIPAMPL` constructor sets these exact capability flags. ([Pyomo Documentation][1])

---

## 4.10 Deployment advice by model class

```text id="nqy6yd"
MILP:
  use SCIP confidently
  set limits/time and limits/gap
  compare HiGHS for pure linear open-source baseline

MIQP / MIQCP:
  use SCIP if discrete/quadratic structure matters
  add bounds aggressively
  test convexity assumptions
  compare Gurobi/CPLEX when licensed

MINLP:
  use SCIP when integrality + nonlinear terms are unavoidable
  bound every nonlinear variable
  compare IPOPT continuous relaxation
  compare Couenne for nonconvex global MINLP
  compare BONMIN for convex/general MINLP experiments

SOS:
  use Pyomo SOSConstraint directly
  verify solver capability with opt.has_capability("sos2")
  keep symbolic labels for debugging

Logical/indicator:
  transform GDP or manually linearize
  never rely on unbounded big-M
  archive transformed model for production

Piecewise:
  start with SOS2 under SCIP
  switch to DCC/CC/logarithmic forms only after benchmark
  avoid BIGM_BIN unless tested and scaled
```

---

## 4.11 Minimal canonical SCIP-friendly Pyomo template

```python id="epor2d"
from pyomo.environ import *
from pyomo.opt import SolverStatus, TerminationCondition

def solve_scip(model, *, time_limit=300, gap=1e-4, debug=False):
    opt = SolverFactory("scip", solver_io="nl")
    if not opt.available(False):
        raise RuntimeError("SCIP executable unavailable to Pyomo")

    opt.options["limits/time"] = time_limit
    opt.options["limits/gap"] = gap

    results = opt.solve(
        model,
        tee=True,
        logfile="scip.log" if debug else None,
        keepfiles=debug,
        symbolic_solver_labels=debug,
    )

    status = results.solver.status
    tc = results.solver.termination_condition

    if status == SolverStatus.ok and tc == TerminationCondition.optimal:
        return results

    if tc in {TerminationCondition.maxTimeLimit, TerminationCondition.feasible}:
        return results

    raise RuntimeError(f"SCIP solve did not terminate acceptably: {status=} {tc=}")
```

---

## 4.12 Compact mental model

```text id="z0tasr"
Best Pyomo classes for SCIP:
  MILP:
    binary/integer + linear algebra

  MIQP/MIQCP:
    quadratic objective/constraints + integer decisions
    require bounds/scaling/convexity awareness

  MINLP:
    nonlinear expressions + integer decisions
    require finite bounds and domain-safe expressions

  SOS:
    SOSConstraint(sos=1/2)
    directly declared capability in Pyomo SCIP plugin

  Logical/indicator:
    use GDP transformations or manual linearization
    Big-M quality determines relaxation quality

  Piecewise:
    Piecewise(..., pw_repn="SOS2") default for SCIP
    DCC/CC/LOG/DLOG as benchmark alternatives

Solver routing:
  continuous NLP -> IPOPT first
  pure LP/MIP/QP -> HiGHS/SCIP/commercial comparison
  difficult open-source MINLP -> SCIP/Couenne/BONMIN comparison
  production commercial MILP/MIQP/MIQCP -> Gurobi/CPLEX comparison
```

[1]: https://pyomo.readthedocs.io/en/6.8.2/_modules/pyomo/solvers/plugins/solvers/SCIPAMPL.html "pyomo.solvers.plugins.solvers.SCIPAMPL — Pyomo 6.8.2 documentation"
[2]: https://pyomo.readthedocs.io/en/6.9.0/api/pyomo.core.base.var.Var.html "Var — Pyomo 6.9.0 documentation"
[3]: https://highs.dev/?utm_source=chatgpt.com "HiGHS - High-performance parallel linear optimization software"
[4]: https://github.com/coin-or/IPOPT?utm_source=chatgpt.com "coin-or/Ipopt: COIN-OR Interior Point Optimizer IPOPT"
[5]: https://pyomo.readthedocs.io/en/6.6.2/advanced_topics/sos_constraints.html "Special Ordered Sets (SOS) — Pyomo 6.6.2 documentation"
[6]: https://pyomo.readthedocs.io/en/6.8.0/modeling_extensions/gdp/solving.html "Solving Logic-based Models with Pyomo.GDP — Pyomo 6.8.0 documentation"
[7]: https://pyomo.readthedocs.io/en/6.8.2/api/pyomo.gdp.plugins.bigm.BigM_Transformation.html "BigM_Transformation — Pyomo 6.8.2 documentation"
[8]: https://pyomo.readthedocs.io/en/latest/api/pyomo.core.base.piecewise.Piecewise.html "Piecewise — Pyomo 6.10.1.dev0 documentation"

# 5) Core Pyomo solve syntax — SCIP backend

Dense technical reference for LLM programming agents. Style aligned with the uploaded advanced-doc template. 

---

## 5.0 Solve-call mental model

```text id="s5dwow"
Pyomo SCIP solve:
  ConcreteModel / model instance
  -> SolverFactory("scip")
  -> opt.solve(...)
  -> Pyomo writes NL file
  -> external scip executable runs
  -> SCIP writes solution/log artifacts
  -> Pyomo returns SolverResults
  -> Pyomo optionally loads solution values into model variables
```

The SCIP plugin is a legacy-style external solver interface; its solve-call surface includes `tee`, `load_solutions`, `logfile`, `timelimit`, `options`, `keepfiles`, and `symbolic_solver_labels` keyword arguments. ([Pyomo Documentation][1])

---

## 5.1 Minimal solve

### 5.1.1 Canonical syntax

```python id="yvu7j2"
from pyomo.environ import *

m = ConcreteModel()

# variables
m.x = Var(domain=Binary)
m.y = Var(bounds=(0, None))

# objective
m.obj = Objective(expr=5*m.x + m.y, sense=maximize)

# constraints
m.cap = Constraint(expr=3*m.x + m.y <= 4)

# solver
opt = SolverFactory("scip")
res = opt.solve(m, tee=True)

print(res.solver.status)
print(res.solver.termination_condition)
print(value(m.x), value(m.y), value(m.obj))
```

`tee=True` streams solver output to the console; Pyomo documents it as the standard way to see solver output and notes it is useful for troubleshooting solver difficulties. ([Pyomo Documentation][2])

### 5.1.2 Agent invariants

```text id="df7rdm"
After opt.solve(m) with default load_solutions=True:
  variable values are normally loaded into m if a solution exists

After opt.solve(m, load_solutions=False):
  values remain in SolverResults
  agent must decide whether to load into m
```

Pyomo documentation states that `solve()` loads results into the model instance by default, and recommends `load_solutions=False` when the script must inspect termination before loading values. ([Pyomo Documentation][3])

---

## 5.2 Recommended status-checking pattern

### 5.2.1 Strict optimal-only loader

```python id="jzvhvy"
from pyomo.environ import *
from pyomo.opt import SolverStatus, TerminationCondition

opt = SolverFactory("scip")

res = opt.solve(m, tee=True, load_solutions=False)

if (
    res.solver.status == SolverStatus.ok
    and res.solver.termination_condition == TerminationCondition.optimal
):
    m.solutions.load_from(res)
else:
    raise RuntimeError(
        f"SCIP did not prove optimality: "
        f"status={res.solver.status}, termination={res.solver.termination_condition}"
    )
```

Pyomo’s solver recipe shows the `SolverStatus.ok` plus `TerminationCondition.optimal` check as the standard “feasible and optimal” test, and separately shows the `load_solutions=False` plus `model.solutions.load_from(results)` pattern. ([Pyomo Documentation][2])

### 5.2.2 Practical production loader: accept optimal or time-limited feasible

```python id="hpyk71"
from pyomo.environ import *
from pyomo.opt import SolverStatus, TerminationCondition

ACCEPTABLE_WITH_SOLUTION = {
    TerminationCondition.optimal,
    TerminationCondition.feasible,
    TerminationCondition.maxTimeLimit,
}

res = opt.solve(m, tee=True, load_solutions=False)

tc = res.solver.termination_condition
status = res.solver.status

if status == SolverStatus.ok and tc == TerminationCondition.optimal:
    m.solutions.load_from(res)
elif tc in ACCEPTABLE_WITH_SOLUTION and len(res.solution) > 0:
    m.solutions.load_from(res)
else:
    raise RuntimeError(f"No acceptable SCIP solution: status={status}, termination={tc}")
```

Use this pattern only when downstream code can tolerate incumbent-but-not-proven-optimal solutions. For exact optimization reports, keep the strict optimal-only loader.

### 5.2.3 Anti-pattern

```python id="bksjy3"
# Anti-pattern: unconditional value access after a non-optimal solve
res = opt.solve(m, tee=True)
print(value(m.x))  # may be stale, uninitialized, or loaded from a nonideal termination
```

---

## 5.3 Loading results: default vs controlled

### 5.3.1 Default load path

```python id="xltmk4"
res = opt.solve(m, tee=True)
print(value(m.x))
```

Meaning:

```text id="u6ehaq"
load_solutions=True default
  -> if a solution exists, Pyomo loads solver variable values into model variables
  -> results object still contains solver metadata
```

The current legacy-compatible solve signature shows `load_solutions=True` as the default. ([Pyomo Documentation][1])

### 5.3.2 Controlled load path

```python id="qzyb74"
res = opt.solve(m, tee=True, load_solutions=False)

if res.solver.termination_condition == TerminationCondition.optimal:
    m.solutions.load_from(res)
```

Pyomo’s solver recipe explicitly shows this exact controlled-load pattern. ([Pyomo Documentation][2])

### 5.3.3 Agent rule

```text id="n97l5o"
For notebooks / quick demos:
  opt.solve(m, tee=True)

For production / services / pipelines:
  opt.solve(m, tee=True, load_solutions=False)
  inspect status + termination
  load only if acceptable
```

---

## 5.4 Keeping files

### 5.4.1 Debug solve

```python id="yt9p1d"
res = opt.solve(
    m,
    tee=True,
    keepfiles=True,
    symbolic_solver_labels=True,
)
```

`keepfiles=True` instructs Pyomo to preserve files generated for the solver and print their names; Pyomo docs recommend pairing it with `symbolic_solver_labels=True` so generated files contain meaningful component names. ([Pyomo Documentation][4])

### 5.4.2 Why pair `keepfiles` with `symbolic_solver_labels`

```text id="ldmvpt"
keepfiles=True:
  preserves generated solver input/output files

symbolic_solver_labels=True:
  uses Pyomo component names instead of opaque autogenerated symbols

Combined value:
  map solver rows/columns/errors back to Pyomo components
  inspect .nl / .row / .col / .sol / log artifacts
  reproduce failures outside Python
```

### 5.4.3 Debug artifact pattern

```python id="gbjt03"
res = opt.solve(
    m,
    tee=True,
    logfile="artifacts/scip.log",
    keepfiles=True,
    symbolic_solver_labels=True,
    load_solutions=False,
)
```

Recommended artifact directory:

```text id="h98qny"
artifacts/
  scip.log
  generated_model.nl
  generated_model.row
  generated_model.col
  generated_model.sol
  solver_options.json
  solve_summary.json
```

---

## 5.5 Logging

### 5.5.1 Console logging

```python id="aiayl1"
res = opt.solve(m, tee=True)
```

`tee=True` is Pyomo’s solver-independent option for streaming solver output. ([Pyomo Documentation][2])

### 5.5.2 File logging

```python id="xr8nod"
res = opt.solve(
    m,
    tee=True,
    logfile="scip.log",
)
```

The legacy-compatible Pyomo solve signature includes a `logfile` argument, and the signature also exposes `keepfiles`, `symbolic_solver_labels`, `timelimit`, and `options`. ([Pyomo Documentation][1])

### 5.5.3 Production logging wrapper

```python id="dp53hu"
from pathlib import Path

run_dir = Path("runs/run_001")
run_dir.mkdir(parents=True, exist_ok=True)

res = opt.solve(
    m,
    tee=True,
    logfile=str(run_dir / "scip.log"),
    keepfiles=True,
    symbolic_solver_labels=True,
    load_solutions=False,
)
```

### 5.5.4 Logging policy

```text id="fwjv0l"
Interactive development:
  tee=True

CI:
  tee=False
  logfile="scip.log"
  print short summary after solve

Hard debugging:
  tee=True
  logfile="scip.log"
  keepfiles=True
  symbolic_solver_labels=True

Production batch:
  logfile per run
  tee configurable
  persist solver options + termination condition + objective + bounds/gap
```

---

## 5.6 Solver options: persistent object options vs per-solve options

### 5.6.1 Persistent solver-object options

```python id="naj7ax"
opt = SolverFactory("scip")
opt.options["limits/time"] = 300
opt.options["limits/gap"] = 1e-4

res1 = opt.solve(m1, tee=True)
res2 = opt.solve(m2, tee=True)  # same opt.options still apply
```

Pyomo documents that options attached to a solver object persist across every call to `optimizer.solve(...)` unless deleted from the options dictionary. ([Pyomo Documentation][2])

### 5.6.2 Per-solve options

```python id="l90k6f"
res = opt.solve(
    m,
    tee=True,
    options={
        "limits/time": 300,
        "limits/gap": 1e-4,
    },
)
```

Pyomo documents passing an `options` dictionary into `solve()`; these solve-call options persist only within that solve and temporarily override matching solver-object options. ([Pyomo Documentation][2])

### 5.6.3 Agent rule

```text id="whb5xs"
Use opt.options[...] when:
  one solver instance has a stable policy across many solves

Use solve(..., options={...}) when:
  per-run policy changes
  wrapper is stateless
  avoiding option leakage matters
```

---

## 5.7 SCIP time limits

### 5.7.1 Native SCIP option

```python id="ow6gex"
opt = SolverFactory("scip")
opt.options["limits/time"] = 300
res = opt.solve(m, tee=True)
```

SCIP’s parameter list defines `limits/time` as the maximal runtime in seconds, and also lists related stopping controls such as `limits/gap`, `limits/nodes`, `limits/memory`, and `limits/solutions`. ([SCIP Optimization Library][5])

### 5.7.2 Pyomo generic `timelimit` argument

```python id="fzt7yn"
res = opt.solve(m, tee=True, timelimit=300)
```

Pyomo’s SCIP plugin maps the generic `_timelimit` into `limits/time = <timelimit>` when `_timelimit` is positive and `limits/time` is not already present in `opt.options`. ([Pyomo Documentation][6])

### 5.7.3 Precedence rule

```text id="nv2ok6"
If opt.options["limits/time"] exists:
  Pyomo does not overwrite it with solve(..., timelimit=...)

If opt.options["limits/time"] absent and solve(..., timelimit=T):
  Pyomo writes limits/time = T into SCIP options file
```

This precedence follows directly from the SCIP plugin condition checking `self._timelimit` and `'limits/time' not in self.options` before writing the option. ([Pyomo Documentation][6])

### 5.7.4 Best-practice syntax

```python id="ayh7cv"
# SCIP-specific explicitness; preferred in SCIP-focused code
opt.options["limits/time"] = 300

# Solver-generic wrapper compatibility; acceptable in abstraction layers
res = opt.solve(m, timelimit=300)
```

### 5.7.5 Common stopping options

```python id="j7z134"
opt.options["limits/time"] = 300       # seconds
opt.options["limits/gap"] = 1e-4       # relative MIP gap
opt.options["limits/absgap"] = 1e-6    # absolute gap
opt.options["limits/nodes"] = 100000   # branch-and-bound node limit
opt.options["limits/solutions"] = 10   # solution-count stop
```

SCIP’s current parameter list defines `limits/gap` as a relative primal-dual gap stopping rule and `limits/absgap` as an absolute primal-dual gap stopping rule. ([SCIP Optimization Library][5])

---

## 5.8 How Pyomo transmits SCIP options

### 5.8.1 Mechanism

```text id="nx3h5d"
opt.options["a/b"] = value
  ↓
Pyomo formats:
  a/b = value
  ↓
Pyomo writes temporary scip.set
  ↓
Pyomo launches SCIP in that temporary options directory
  ↓
SCIP reads scip.set
```

The SCIP plugin formats each option as `key = value`, writes these lines to a temporary `scip.set`, and uses the temporary directory as the solver working directory. ([Pyomo Documentation][6])

### 5.8.2 Ambient `scip.set` conflict

```text id="v2ejcv"
If current directory contains ./scip.set
and opt.options is nonempty:
  Pyomo warns that ./scip.set will be ignored
  Pyomo uses its generated temporary scip.set instead
```

The SCIP plugin explicitly checks for a current-working-directory `scip.set` and warns that it will be ignored when Pyomo is setting SCIP options through a separate options file. ([Pyomo Documentation][6])

### 5.8.3 Agent rule

```text id="m54ejk"
Do not mix:
  opt.options[...] plus ambient ./scip.set

Choose:
  Pyomo option dict for Pyomo-driven runs
  standalone scip + scip.set for solver-shell runs
```

---

## 5.9 Canonical production solve wrapper

```python id="yqm2ia"
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pyomo.environ import SolverFactory, value
from pyomo.opt import SolverStatus, TerminationCondition


@dataclass(frozen=True)
class ScipSolvePolicy:
    time_limit: float | None = 300
    rel_gap: float | None = None
    abs_gap: float | None = None
    tee: bool = True
    debug_files: bool = False
    logfile: str | None = "scip.log"
    load_mode: str = "optimal_only"  # "optimal_only" | "accept_feasible" | "never"


def configure_scip(policy: ScipSolvePolicy):
    opt = SolverFactory("scip", solver_io="nl")

    if not opt.available(False):
        raise RuntimeError(
            "SCIP unavailable. Verify conda/micromamba env, `scip --version`, "
            "and `SolverFactory('scip').available(False)`."
        )

    if policy.time_limit is not None:
        opt.options["limits/time"] = float(policy.time_limit)

    if policy.rel_gap is not None:
        opt.options["limits/gap"] = float(policy.rel_gap)

    if policy.abs_gap is not None:
        opt.options["limits/absgap"] = float(policy.abs_gap)

    return opt


def solve_scip(model: Any, policy: ScipSolvePolicy):
    opt = configure_scip(policy)

    res = opt.solve(
        model,
        tee=policy.tee,
        logfile=policy.logfile,
        keepfiles=policy.debug_files,
        symbolic_solver_labels=policy.debug_files,
        load_solutions=False,
    )

    status = res.solver.status
    tc = res.solver.termination_condition

    has_solution = len(res.solution) > 0

    if policy.load_mode == "never":
        return res

    if policy.load_mode == "optimal_only":
        if status == SolverStatus.ok and tc == TerminationCondition.optimal:
            model.solutions.load_from(res)
            return res
        raise RuntimeError(f"SCIP did not prove optimality: status={status}, termination={tc}")

    if policy.load_mode == "accept_feasible":
        acceptable = {
            TerminationCondition.optimal,
            TerminationCondition.feasible,
            TerminationCondition.maxTimeLimit,
        }
        if tc in acceptable and has_solution:
            model.solutions.load_from(res)
            return res
        raise RuntimeError(f"No acceptable solution: status={status}, termination={tc}")

    raise ValueError(f"Unknown load_mode={policy.load_mode!r}")
```

---

## 5.10 Minimal smoke-test solve

```python id="h8e7j4"
from pyomo.environ import *
from pyomo.opt import SolverStatus, TerminationCondition

def build_model():
    m = ConcreteModel()
    m.x = Var(domain=Binary)
    m.y = Var(bounds=(0, None))
    m.obj = Objective(expr=5*m.x + m.y, sense=maximize)
    m.c = Constraint(expr=3*m.x + m.y <= 4)
    return m

def test_scip_minimal_solve():
    m = build_model()
    opt = SolverFactory("scip")

    assert opt.available(False)

    res = opt.solve(m, tee=False, load_solutions=False)

    assert res.solver.status == SolverStatus.ok
    assert res.solver.termination_condition == TerminationCondition.optimal

    m.solutions.load_from(res)

    assert abs(value(m.x) - 1.0) <= 1e-8
    assert abs(value(m.y) - 1.0) <= 1e-8
    assert abs(value(m.obj) - 6.0) <= 1e-8
```

---

## 5.11 Solve-call option matrix

| Goal                       | Syntax                                     | Agent note                               |
| -------------------------- | ------------------------------------------ | ---------------------------------------- |
| minimal solve              | `res = opt.solve(m)`                       | loads solution by default if available   |
| stream solver log          | `res = opt.solve(m, tee=True)`             | troubleshooting default                  |
| inspect before load        | `res = opt.solve(m, load_solutions=False)` | production-safe                          |
| manually load              | `m.solutions.load_from(res)`               | after termination check                  |
| preserve generated files   | `keepfiles=True`                           | pair with labels                         |
| meaningful generated names | `symbolic_solver_labels=True`              | slower/larger but debuggable             |
| write log file             | `logfile="scip.log"`                       | archive by run ID                        |
| set SCIP time limit        | `opt.options["limits/time"] = 300`         | explicit SCIP-native                     |
| generic time limit         | `opt.solve(m, timelimit=300)`              | maps to `limits/time` if not already set |
| one-run options            | `opt.solve(m, options={...})`              | avoids option leakage                    |
| persistent options         | `opt.options[...] = ...`                   | applies to later solves                  |

---

## 5.12 Failure-mode diagnostics

| Symptom                              | Likely cause                           | Probe                                      | Fix                                          |
| ------------------------------------ | -------------------------------------- | ------------------------------------------ | -------------------------------------------- |
| `No value for uninitialized VarData` | solution not loaded or no solution     | `len(res.solution)`, termination           | use `load_solutions=False`, check, then load |
| stale variable values                | previous solve values still on model   | inspect `res.solver.termination_condition` | do not read values after failed solve        |
| no solver output                     | `tee=False`                            | solve kwarg                                | `tee=True`                                   |
| no file artifacts                    | `keepfiles=False`                      | solve kwargs                               | `keepfiles=True`                             |
| unreadable solver files              | symbolic labels disabled               | generated names                            | `symbolic_solver_labels=True`                |
| time limit ignored                   | wrong option name or overridden policy | inspect log / options                      | use `limits/time`; avoid conflicting options |
| ambient `scip.set` ignored           | Pyomo wrote temp `scip.set`            | Pyomo warning                              | put settings in `opt.options`                |
| per-run options leak                 | mutated `opt.options` reused           | print `opt.options`                        | use `solve(..., options={...})`              |
| load on nonoptimal result            | default `load_solutions=True`          | solver status                              | set `load_solutions=False`                   |

---

## 5.13 Agent-ready default recipe

```python id="s2je6w"
from pyomo.environ import *
from pyomo.opt import SolverStatus, TerminationCondition

opt = SolverFactory("scip", solver_io="nl")
if not opt.available(False):
    raise RuntimeError("SCIP unavailable")

opt.options["limits/time"] = 300
opt.options["limits/gap"] = 1e-4

res = opt.solve(
    m,
    tee=True,
    logfile="scip.log",
    keepfiles=False,
    symbolic_solver_labels=False,
    load_solutions=False,
)

if (
    res.solver.status == SolverStatus.ok
    and res.solver.termination_condition == TerminationCondition.optimal
):
    m.solutions.load_from(res)
else:
    raise RuntimeError(
        f"SCIP did not return proven optimal solution: "
        f"{res.solver.status=} {res.solver.termination_condition=}"
    )
```

---

## 5.14 Compact mental model

```text id="pqremm"
Fast demo:
  opt = SolverFactory("scip")
  res = opt.solve(m, tee=True)

Production:
  res = opt.solve(m, tee=True, load_solutions=False)
  inspect SolverStatus + TerminationCondition
  m.solutions.load_from(res) only when acceptable

Debug:
  res = opt.solve(
      m,
      tee=True,
      logfile="scip.log",
      keepfiles=True,
      symbolic_solver_labels=True,
      load_solutions=False,
  )

Time limit:
  opt.options["limits/time"] = 300
  or solve(..., timelimit=300) if limits/time absent

Options:
  opt.options persists across solves
  solve(..., options={...}) is per-call
  Pyomo writes SCIP options into temporary scip.set
```

[1]: https://pyomo.readthedocs.io/en/6.10.0/api/pyomo.contrib.solver.common.base.LegacySolverWrapper.html "LegacySolverWrapper — Pyomo 6.10.0 documentation"
[2]: https://pyomo.readthedocs.io/en/6.10.0/howto/solver_recipes.html "Solver Recipes — Pyomo 6.10.0 documentation"
[3]: https://pyomo.readthedocs.io/en/6.4.3/working_models.html "Working with Pyomo Models — Pyomo 6.4.3 documentation"
[4]: https://pyomo.readthedocs.io/en/6.8.0/working_abstractmodels/pyomo_command.html "The pyomo Command — Pyomo 6.8.0 documentation"
[5]: https://www.scipopt.org/doc/html/PARAMETERS.php "SCIP Doxygen Documentation: List of all SCIP parameters"
[6]: https://pyomo.readthedocs.io/en/6.8.2/_modules/pyomo/solvers/plugins/solvers/SCIPAMPL.html "pyomo.solvers.plugins.solvers.SCIPAMPL — Pyomo 6.8.2 documentation"

# 6) SCIP parameter system and Pyomo option syntax — agent-ready deep dive

Dense technical reference for Pyomo+SCIP deployment. Style aligned with the uploaded advanced-doc template. 

---

## 6.0 Core contract

```text id="59tmbm"
SCIP native parameter:
  slash-separated hierarchical key
  examples:
    limits/time
    limits/gap
    display/verblevel
    presolving/maxrounds
    separating/maxroundsroot
    heuristics/rens/freq
    branching/preferbinary
    numerics/feastol

Pyomo syntax:
  opt.options["<exact SCIP key>"] = <value>

Pyomo transport:
  opt.options dict
    -> temporary scip.set
    -> scip executable working directory
    -> SCIP reads settings file
```

The current SCIP parameter reference is for **SCIP 10.0.2** and says the full parameter list can be generated from the interactive shell with `SCIP> set save <file name>` or via `SCIPwriteParams(...)`. ([SCIP Optimization Library][1])

---

## 6.1 Native SCIP parameter naming

### 6.1.1 Naming grammar

```text id="eq3ops"
<family>/<subfamily>/<parameter>
<family>/<parameter>

Examples:
  limits/time
  limits/gap
  limits/absgap
  display/verblevel
  lp/initalgorithm
  lp/threads
  numerics/feastol
  presolving/maxrounds
  separating/maxcutsroot
  heuristics/rens/freq
  constraints/nonlinear/reformbinprods
  parallel/maxnthreads
```

SCIP parameters are shown in the official parameter file format as `key = value`, with metadata comments containing type, advanced flag, range, and default value; examples include `branching/scorefunc`, `branching/preferbinary`, `display/verblevel`, `limits/time`, and `limits/gap`. ([SCIP Optimization Library][1])

### 6.1.2 Parameter value types

```text id="0k7gkr"
SCIP parameter metadata types:
  bool
  int
  longint
  real
  char
  string

SCIP docs render booleans as:
  TRUE
  FALSE

SCIP docs render char options as single letters:
  lp/initalgorithm = s
  branching/scorefunc = p
```

For Pyomo, values are converted with `str(value)` when written to `scip.set`; for maximum portability, agent-generated boolean options should use `"TRUE"` / `"FALSE"` strings rather than relying on Python `True` / `False` spelling. Pyomo’s SCIP plugin formats each option line as `str(key) + " = " + str(value)`. ([Pyomo Documentation][2])

---

## 6.2 Parameter file generation and settings lifecycle

### 6.2.1 Generate all current parameters

SCIP shell:

```text id="tu7ypf"
SCIP> set save scip.set
```

This writes all current parameter values, including defaults and any changes. The shell tutorial shows `set save settingsfile.set` saving a parameter file, `set diffsave settingsfile.set` saving only non-default settings, and `set load settingsfile.set` loading settings. ([SCIP Optimization Library][3])

### 6.2.2 Generate only changed parameters

```text id="vp52h5"
SCIP> set diffsave tuned.set
```

Use `diffsave` for production tuning overlays because it is smaller, reviewable, and easier to compare across solver versions. SCIP’s shell docs explicitly describe `set diffsave` as saving only non-default parameter settings and note that multiple non-overlapping setting files can be combined more easily when only changes are stored. ([SCIP Optimization Library][3])

### 6.2.3 Load parameter file in standalone SCIP

```text id="bic46i"
SCIP> set load tuned.set
```

### 6.2.4 Automatic `scip.set` behavior in standalone SCIP

```text id="84i8e1"
If standalone SCIP starts in a working directory containing:
  scip.set

Then:
  SCIP shell auto-loads scip.set
```

The SCIP shell tutorial states that a settings file named `scip.set` in the working directory is automatically used when the interactive shell starts. ([SCIP Optimization Library][3])

### 6.2.5 Pyomo-specific warning

```text id="ycue7u"
Do not rely on ambient ./scip.set for Pyomo-driven solves when opt.options is nonempty.

Pyomo creates its own temporary scip.set and runs SCIP with that temporary directory as cwd.
```

Pyomo’s SCIP plugin checks whether a `scip.set` exists in the current working directory and warns that it will be ignored when Pyomo is setting SCIP options through a separate options file. ([Pyomo Documentation][2])

---

## 6.3 Pyomo option syntax

### 6.3.1 Minimal option setting

```python id="twekii"
from pyomo.environ import *

opt = SolverFactory("scip")
opt.options["limits/time"] = 600
opt.options["limits/gap"] = 1e-4
opt.options["display/verblevel"] = 4

res = opt.solve(model, tee=True)
```

### 6.3.2 Type-safe-ish helper

```python id="glyclv"
from pyomo.environ import SolverFactory

def make_scip_solver(
    *,
    time_limit: float | None = None,
    rel_gap: float | None = None,
    abs_gap: float | None = None,
    verbosity: int | None = None,
    threads: int | None = None,
):
    opt = SolverFactory("scip", solver_io="nl")

    if time_limit is not None:
        opt.options["limits/time"] = float(time_limit)

    if rel_gap is not None:
        opt.options["limits/gap"] = float(rel_gap)

    if abs_gap is not None:
        opt.options["limits/absgap"] = float(abs_gap)

    if verbosity is not None:
        opt.options["display/verblevel"] = int(verbosity)

    if threads is not None:
        opt.options["parallel/maxnthreads"] = int(threads)
        opt.options["parallel/minnthreads"] = int(threads)

    return opt
```

### 6.3.3 Per-solve options vs persistent options

```python id="2ozp16"
# Persistent on solver object: applies to every later solve through this opt object
opt = SolverFactory("scip")
opt.options["limits/time"] = 300
res1 = opt.solve(m1)
res2 = opt.solve(m2)

# Per-call override/overlay
res = opt.solve(
    model,
    options={
        "limits/time": 60,
        "limits/gap": 0.05,
    },
)
```

Pyomo’s SCIP plugin iterates over `self.options` and writes every non-`solver` option to the generated SCIP options file; any solve-call options that are merged into `self.options` follow the same file path. ([Pyomo Documentation][2])

---

## 6.4 How Pyomo passes SCIP options

### 6.4.1 Internal sequence

```text id="94joz1"
opt.options = {
  "limits/time": 300,
  "limits/gap": 1e-4,
}

Pyomo SCIPAMPL:
  for each option:
    write "limits/time = 300"
    write "limits/gap = 0.0001"
  create temp directory
  write tempdir/scip.set
  launch:
    scip <problem> -AMPL
  with cwd=tempdir
```

Pyomo’s SCIP plugin constructs the command as `[executable, problem_file, "-AMPL"]`, formats each option as `key = value`, creates a temporary directory, writes `scip.set` there, and returns a command object whose `cwd` is that options directory. ([Pyomo Documentation][2])

### 6.4.2 `timelimit` mapping

```python id="013ygh"
# SCIP-native explicit option
opt.options["limits/time"] = 300

# Pyomo generic solve kwarg
res = opt.solve(model, timelimit=300)
```

If `_timelimit` is positive and `limits/time` is not already present in `self.options`, Pyomo appends `limits/time = <timelimit>` to the generated option file. ([Pyomo Documentation][2])

### 6.4.3 Precedence rule

```text id="5cm8xj"
If opt.options["limits/time"] exists:
  solve(..., timelimit=T) does not overwrite it.

If opt.options["limits/time"] absent:
  solve(..., timelimit=T) becomes:
    limits/time = T
```

---

## 6.5 Option validation model

```text id="c4cdgd"
Pyomo validation:
  minimal
  stringifies key/value pairs
  does not deeply validate SCIP parameter names/ranges

SCIP validation:
  checks key existence
  checks type
  checks range
  emits solver-side error/warning if invalid
```

This follows from Pyomo’s implementation: keys and values are looped over, stringified, and written into `scip.set` without consulting the SCIP parameter schema. ([Pyomo Documentation][2])

### 6.5.1 Defensive validation helper

```python id="vucjao"
KNOWN_SCIP_OPTION_PREFIXES = {
    "limits/",
    "display/",
    "table/",
    "presolving/",
    "separating/",
    "heuristics/",
    "branching/",
    "constraints/",
    "lp/",
    "numerics/",
    "parallel/",
    "concurrent/",
    "randomization/",
    "conflict/",
    "propagating/",
    "cutselection/",
}

def validate_scip_option_keys(options: dict[str, object]) -> None:
    bad = [
        k for k in options
        if not any(k.startswith(prefix) for prefix in KNOWN_SCIP_OPTION_PREFIXES)
    ]
    if bad:
        raise ValueError(f"Suspicious SCIP option keys: {bad}")
```

Use this only as a guardrail; the authoritative parameter list is the installed SCIP’s own `set save` output.

---

## 6.6 Critical nuance: `display/statistics`

```text id="dmns7u"
SCIP shell command:
  display statistics

Current SCIP parameter:
  display/relevantstats
  table/<name>/active

Not a current native parameter in the official 10.0.2 parameter list:
  display/statistics
```

SCIP’s shell tutorial says `display statistics` is a shell command for solution-process statistics; the parameter file contains `display/relevantstats = TRUE` and many `table/*/active` switches for statistics tables, but a search of the current parameter page does not show a `display/statistics` parameter. ([SCIP Optimization Library][3])

Recommended Pyomo syntax for statistics-adjacent output:

```python id="in9361"
opt.options["display/verblevel"] = 4
opt.options["display/relevantstats"] = "TRUE"

# Selectively activate/deactivate statistics tables
opt.options["table/lp/active"] = "TRUE"
opt.options["table/heuristics/active"] = "TRUE"
opt.options["table/separator/active"] = "TRUE"
```

---

## 6.7 Parameter family: `limits/*`

### 6.7.1 Common keys

```python id="mvcov1"
opt.options["limits/time"] = 300          # seconds
opt.options["limits/gap"] = 1e-4          # relative primal-dual gap
opt.options["limits/absgap"] = 1e-6       # absolute primal-dual gap
opt.options["limits/nodes"] = 100000      # branch-and-bound node cap
opt.options["limits/totalnodes"] = 200000 # including restarts
opt.options["limits/stallnodes"] = 50000  # nodes since last primal improvement
opt.options["limits/memory"] = 8192       # MB
opt.options["limits/solutions"] = 1       # stop after N solutions
opt.options["limits/maxsol"] = 100        # solution storage cap
```

The current SCIP parameter list defines `limits/time`, `limits/nodes`, `limits/totalnodes`, `limits/stallnodes`, `limits/memory`, `limits/gap`, `limits/absgap`, `limits/primal`, `limits/dual`, `limits/solutions`, and related solution/restart limits with documented types, ranges, and defaults. ([SCIP Optimization Library][1])

### 6.7.2 Value cases

```text id="71r83k"
limits/time:
  hard wall-clock budget
  production SLA
  notebook safety guard

limits/gap:
  stop once relative proof gap acceptable
  MIP/MINLP practical optimality

limits/absgap:
  stop when objective units have absolute tolerance meaning

limits/nodes:
  deterministic-ish tree budget
  benchmarking / algorithm comparison

limits/solutions:
  feasibility-first / find-one-solution workflows

limits/memory:
  batch/HPC guardrail
```

### 6.7.3 Production preset

```python id="cjbs6l"
def apply_production_limits(opt, *, seconds=1800, rel_gap=1e-4, memory_mb=32768):
    opt.options["limits/time"] = float(seconds)
    opt.options["limits/gap"] = float(rel_gap)
    opt.options["limits/memory"] = float(memory_mb)
```

### 6.7.4 Feasible-first preset

```python id="7fme5i"
def apply_feasible_first_limits(opt, *, seconds=120, solutions=1):
    opt.options["limits/time"] = float(seconds)
    opt.options["limits/solutions"] = int(solutions)
```

---

## 6.8 Parameter family: `display/*` and `table/*`

### 6.8.1 Common display keys

```python id="ln2rud"
opt.options["display/verblevel"] = 4      # 0..5
opt.options["display/width"] = 143
opt.options["display/freq"] = 100
opt.options["display/headerfreq"] = 15
opt.options["display/lpinfo"] = "FALSE"
opt.options["display/allviols"] = "FALSE"
opt.options["display/relevantstats"] = "TRUE"
```

SCIP defines `display/verblevel` as verbosity level with range `[0,5]` and default `4`; it also defines display line width, node-line frequency, header frequency, LP-info display flag, all-violations display flag, and `display/relevantstats`. ([SCIP Optimization Library][1])

### 6.8.2 Statistics table switches

```python id="fksraf"
opt.options["table/status/active"] = "TRUE"
opt.options["table/timing/active"] = "TRUE"
opt.options["table/presolver/active"] = "TRUE"
opt.options["table/constraint/active"] = "TRUE"
opt.options["table/propagator/active"] = "TRUE"
opt.options["table/conflict/active"] = "TRUE"
opt.options["table/separator/active"] = "TRUE"
opt.options["table/branchrules/active"] = "TRUE"
opt.options["table/heuristics/active"] = "TRUE"
opt.options["table/lp/active"] = "TRUE"
opt.options["table/nlp/active"] = "TRUE"
opt.options["table/tree/active"] = "TRUE"
opt.options["table/solution/active"] = "TRUE"
```

The parameter list contains many `table/<name>/active` booleans for statistics tables, including timing, presolver, constraint, propagator, conflict, separator, branchrules, heuristics, LP, NLP, tree, and solution tables. ([SCIP Optimization Library][1])

### 6.8.3 Logging presets

```python id="l3cy5o"
def apply_quiet_display(opt):
    opt.options["display/verblevel"] = 0

def apply_debug_display(opt):
    opt.options["display/verblevel"] = 5
    opt.options["display/lpinfo"] = "TRUE"
    opt.options["display/relevantstats"] = "TRUE"
```

---

## 6.9 Parameter family: `presolving/*`

### 6.9.1 Common keys

```python id="gnc3x5"
opt.options["presolving/maxrounds"] = -1     # -1 unlimited, 0 off
opt.options["presolving/abortfac"] = 0.0008
opt.options["presolving/maxrestarts"] = -1
opt.options["presolving/donotmultaggr"] = "FALSE"
opt.options["presolving/donotaggr"] = "FALSE"
```

SCIP defines `presolving/maxrounds` as the maximal number of presolving rounds, with `-1` unlimited and `0` off; it also defines `presolving/abortfac`, `presolving/maxrestarts`, and aggregation-related controls. ([SCIP Optimization Library][1])

### 6.9.2 Value cases

```text id="pvvt9n"
Increase / keep aggressive presolve when:
  model generated by transformations
  many redundant constraints
  weak bounds
  GDP / piecewise / big-M expansion
  large MILP with exploitable structure

Disable or reduce presolve when:
  debugging raw exported model
  row/column mapping must stay simple
  presolve time dominates tiny instances
  numerical issue suspected inside presolve
```

### 6.9.3 Debug preset

```python id="4k8v5b"
def apply_low_presolve_debug(opt):
    opt.options["presolving/maxrounds"] = 0
```

Use only for diagnosis; default presolve is usually beneficial.

### 6.9.4 Emphasis setting caveat

```text id="mm8d1c"
SCIP shell supports:
  set presolving emphasis aggressive|fast|off|default

This is a shell/meta command, not a single scip.set key in the exported parameter list.
For Pyomo, use explicit parameters from a saved/diffed settings file.
```

SCIP’s shell tutorial shows emphasis menus for heuristics and that selecting an emphasis expands into many concrete parameter changes; the same concept applies to presolving/separating emphasis settings in SCIP’s shell workflows. ([SCIP Optimization Library][3])

---

## 6.10 Parameter family: `separating/*`

### 6.10.1 Common keys

```python id="7z9f0z"
opt.options["separating/maxrounds"] = -1
opt.options["separating/maxroundsroot"] = -1
opt.options["separating/maxcuts"] = 100
opt.options["separating/maxcutsroot"] = 2000
opt.options["separating/poolfreq"] = 10
opt.options["separating/cutagelimit"] = 80
```

SCIP defines `separating/maxrounds`, `separating/maxroundsroot`, `separating/maxcuts`, `separating/maxcutsroot`, `separating/cutagelimit`, and `separating/poolfreq`, with documented meanings and ranges. ([SCIP Optimization Library][1])

### 6.10.2 Value cases

```text id="8vwgt3"
Increase separation:
  root gap large
  proof slow
  LP relaxations cheap
  cuts visibly improve dual bound

Reduce separation:
  LP solve time explodes
  many cuts but no bound movement
  memory pressure
  feasible incumbent enough
  time-limited primal search
```

### 6.10.3 Cut-limited preset

```python id="qekxjy"
def apply_cut_light(opt):
    opt.options["separating/maxroundsroot"] = 5
    opt.options["separating/maxrounds"] = 1
    opt.options["separating/maxcutsroot"] = 500
    opt.options["separating/maxcuts"] = 50
```

---

## 6.11 Parameter family: `heuristics/*`

### 6.11.1 Common pattern

```text id="l2qn3n"
heuristics/<heuristic>/freq:
  -1 = never
   0 = only at depth freqofs
  >0 = call frequency

heuristics/<heuristic>/maxdepth:
  -1 = no depth limit

heuristics/<heuristic>/nodesquot / nodesofs / maxnodes:
  subproblem node budget controls
```

SCIP’s RENS heuristic parameters illustrate the pattern: `heuristics/rens/freq`, `freqofs`, `maxdepth`, `minfixingrate`, `maxnodes`, `nodesofs`, `nodesquot`, `minnodes`, and other subproblem controls. ([SCIP Optimization Library][1])

### 6.11.2 Example keys

```python id="fqx42e"
opt.options["heuristics/rens/freq"] = 10
opt.options["heuristics/rens/maxnodes"] = 5000
opt.options["heuristics/rens/minfixingrate"] = 0.5

opt.options["heuristics/alns/freq"] = 20
```

### 6.11.3 Value cases

```text id="7ow3yp"
Increase heuristic effort:
  no incumbent found
  time-limited feasible-solution workflow
  objective proof less important than usable plan
  binary combinatorial structure
  LNS neighborhoods likely useful

Decrease heuristic effort:
  good incumbent already available
  proof dominates
  heuristics consume time without improvements
  benchmarking root-bound behavior
```

### 6.11.4 Heuristic emphasis caveat

```text id="7r1fjy"
SCIP shell:
  set heuristics emphasis aggressive
  set heuristics emphasis fast
  set heuristics emphasis off

Pyomo:
  no direct `heuristics/emphasis` parameter in the exported list
  generate a diff settings file from standalone SCIP after selecting emphasis
  port concrete changed keys into opt.options
```

SCIP’s shell tutorial shows `set heuristics emphasis` with choices `aggressive`, `default`, `fast`, and `off`, and selecting aggressive expands into concrete `heuristics/*` frequency changes such as `heuristics/rins/freq` and `heuristics/crossover/freq`. ([SCIP Optimization Library][3])

---

## 6.12 Parameter family: `branching/*`

### 6.12.1 Common keys

```python id="t6uipv"
opt.options["branching/scorefunc"] = "p"          # s=sum, p=product, q=quotient
opt.options["branching/preferbinary"] = "FALSE"
opt.options["branching/clamp"] = 0.2
opt.options["branching/midpull"] = 0.75
```

The current parameter list defines `branching/scorefunc`, `branching/scorefac`, `branching/preferbinary`, `branching/clamp`, `branching/midpull`, and other branching controls. ([SCIP Optimization Library][1])

### 6.12.2 Value cases

```text id="6fa9h8"
branching/preferbinary:
  may help binary-heavy MILPs
  can hurt if continuous spatial branching is critical in MINLP

branching/scorefunc:
  affects scoring of up/down branching gains
  advanced tuning only after baseline profiling

branching/clamp and midpull:
  continuous-variable branching behavior
  relevant for nonlinear/spatial branching
```

### 6.12.3 Advisory

```text id="9z76wb"
Default branching is usually strong.
Do not tune branching first.
Tune only after:
  model formulation review
  bounds/scaling review
  limits/gap/time policy set
  presolve/cut/heuristic diagnostics inspected
```

---

## 6.13 Parameter family: `constraints/*`

### 6.13.1 Linear constraint-handler examples

```python id="6id1gx"
opt.options["constraints/linear/maxrounds"] = 5
opt.options["constraints/linear/maxroundsroot"] = -1
opt.options["constraints/linear/maxsepacuts"] = 50
opt.options["constraints/linear/maxsepacutsroot"] = 200
opt.options["constraints/linear/separateall"] = "FALSE"
```

SCIP’s linear constraint-handler parameters include separation round limits, root separation round limits, cut limits, presolve/hash options, bound-tightening frequencies, and other linear-constraint behavior controls. ([SCIP Optimization Library][1])

### 6.13.2 Nonlinear constraint-handler examples

```python id="qs7qjq"
opt.options["constraints/nonlinear/maxproprounds"] = 10
opt.options["constraints/nonlinear/reformbinprods"] = "TRUE"
opt.options["constraints/nonlinear/reformbinprodsand"] = "TRUE"
opt.options["constraints/nonlinear/weakcutthreshold"] = 0.2
opt.options["constraints/nonlinear/branching/aux"] = 2147483647
```

SCIP’s nonlinear constraint-handler parameters include propagation-round limits, auxiliary variable propagation, bound relaxation strategies, binary-product reformulation controls, weak/strong cut controls, enforcement behavior, and nonlinear branching weights. ([SCIP Optimization Library][1])

### 6.13.3 Value cases

```text id="lbkzpl"
constraints/linear/*:
  tune linear cut generation and presolve behavior
  useful for MILP formulations with many linear rows

constraints/nonlinear/*:
  tune MINLP nonlinear propagation, reformulations, estimator cuts, and branching behavior
  useful for bilinear, nonconvex, nonlinear Pyomo models
```

---

## 6.14 Parameter family: `lp/*`

### 6.14.1 Common keys

```python id="51ng99"
opt.options["lp/solvefreq"] = 1
opt.options["lp/iterlim"] = -1
opt.options["lp/rootiterlim"] = -1
opt.options["lp/initalgorithm"] = "s"      # s,p,d,b,c
opt.options["lp/resolvealgorithm"] = "s"   # s,p,d,b,c
opt.options["lp/pricing"] = "l"
opt.options["lp/threads"] = 0
```

SCIP defines LP solve frequency, LP iteration limits, initial/resolve algorithms, pricing strategy, and LP thread count; `lp/initalgorithm` and `lp/resolvealgorithm` accept automatic simplex, primal simplex, dual simplex, barrier, or barrier with crossover via single-character codes. ([SCIP Optimization Library][1])

### 6.14.2 Value cases

```text id="596h49"
lp/solvefreq:
  controls when node LPs are solved
  risky to change unless diagnosing LP bottlenecks

lp/initalgorithm, lp/resolvealgorithm:
  advanced tuning for LP-heavy instances
  default automatic usually preferred

lp/threads:
  LP solver thread count
  separate from SCIP parallel/concurrent solving controls
```

---

## 6.15 Parameter family: `numerics/*`

### 6.15.1 Common keys

```python id="llj47q"
opt.options["numerics/epsilon"] = 1e-9
opt.options["numerics/sumepsilon"] = 1e-6
opt.options["numerics/feastol"] = 1e-6
```

SCIP defines `numerics/epsilon` for values considered zero, `numerics/sumepsilon` for sums considered zero, and `numerics/feastol` as the feasibility tolerance for constraints. ([SCIP Optimization Library][1])

### 6.15.2 Advisory

```text id="wlv7bo"
Do not tighten numerics first.
First:
  scale model
  tighten bounds
  remove huge big-M
  inspect coefficient ranges
  validate units

Then, if needed:
  adjust numerics/feastol cautiously
  benchmark solution feasibility and solve time
```

### 6.15.3 Bad vs better

```python id="zd3ei0"
# Bad first response to infeasibility/noise
opt.options["numerics/feastol"] = 1e-12

# Better first response
# 1. scale objective/constraints
# 2. tighten bounds
# 3. reduce big-M
# 4. inspect solver log
# 5. only then adjust feasibility tolerance
```

---

## 6.16 Parameter family: `parallel/*` and `concurrent/*`

### 6.16.1 Common keys

```python id="hh56hr"
opt.options["parallel/mode"] = 1          # 0 opportunistic, 1 deterministic
opt.options["parallel/minnthreads"] = 4
opt.options["parallel/maxnthreads"] = 4

opt.options["concurrent/changeseeds"] = "TRUE"
opt.options["concurrent/changechildsel"] = "TRUE"
opt.options["concurrent/commvarbnds"] = "TRUE"
```

SCIP’s current parameter list defines `parallel/mode`, `parallel/minnthreads`, and `parallel/maxnthreads`, plus concurrent-solver communication and randomization controls such as `concurrent/changeseeds`, `concurrent/changechildsel`, and `concurrent/commvarbnds`. ([SCIP Optimization Library][1])

### 6.16.2 Platform/build caveat

```text id="lgyspz"
parallel/* availability and effect are build-dependent.
Always verify:
  installed SCIP parameter file contains parallel/*
  solver log reports expected thread behavior
  wall-time improves on target platform
```

The official parameter page reflects the installed/current SCIP documentation, but the actual effect of parallel settings depends on the SCIP build and available concurrent-solving support; confirm through `set save` and logs in the deployed conda/micromamba environment. ([SCIP Optimization Library][1])

### 6.16.3 Determinism advisory

```text id="ysacph"
For reproducible benchmarks:
  parallel/mode = 1
  fixed thread count
  archived SCIP version
  archived parameter file
  same hardware class where possible

For best wall time:
  test parallel/mode = 0 vs 1
  benchmark maxnthreads values
```

---

## 6.17 Shell-driven tuning → Pyomo option migration

### 6.17.1 Workflow

```text id="77iy9u"
1. Run standalone SCIP on representative instance.
2. Interactively set emphasis / display statistics / tune parameters.
3. Save non-default settings:
     SCIP> set diffsave tuned.set
4. Review tuned.set.
5. Convert `key = value` lines into:
     opt.options["key"] = value
6. Run Pyomo with logfile + keepfiles.
7. Compare runtime, gap, nodes, primal/dual bounds.
```

### 6.17.2 Converter sketch

```python id="y79rjm"
from pathlib import Path

def parse_scip_set(path: str | Path) -> dict[str, str]:
    options: dict[str, str] = {}
    for raw in Path(path).read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        options[key.strip()] = value.strip()
    return options

def apply_scip_set(opt, path: str | Path) -> None:
    for key, value in parse_scip_set(path).items():
        opt.options[key] = value
```

### 6.17.3 Use

```python id="mux4im"
opt = SolverFactory("scip")
apply_scip_set(opt, "tuned.set")
res = opt.solve(model, tee=True, logfile="scip.log")
```

---

## 6.18 Agent-ready option profiles

### 6.18.1 Default safe production

```python id="3d7r5t"
def scip_profile_safe_production(opt):
    opt.options["limits/time"] = 1800
    opt.options["limits/gap"] = 1e-4
    opt.options["display/verblevel"] = 4
    opt.options["display/relevantstats"] = "TRUE"
```

### 6.18.2 Quiet CI smoke test

```python id="cvh6a5"
def scip_profile_ci_smoke(opt):
    opt.options["limits/time"] = 60
    opt.options["limits/gap"] = 1e-3
    opt.options["display/verblevel"] = 0
```

### 6.18.3 Debug artifacts

```python id="78vdf8"
def scip_profile_debug(opt):
    opt.options["limits/time"] = 300
    opt.options["display/verblevel"] = 5
    opt.options["display/lpinfo"] = "TRUE"
    opt.options["display/relevantstats"] = "TRUE"
    opt.options["table/presolver/active"] = "TRUE"
    opt.options["table/separator/active"] = "TRUE"
    opt.options["table/heuristics/active"] = "TRUE"
    opt.options["table/lp/active"] = "TRUE"
```

Solve call:

```python id="cb3xse"
res = opt.solve(
    model,
    tee=True,
    logfile="scip-debug.log",
    keepfiles=True,
    symbolic_solver_labels=True,
    load_solutions=False,
)
```

### 6.18.4 Feasibility-first

```python id="m35g8z"
def scip_profile_feasible_first(opt):
    opt.options["limits/time"] = 300
    opt.options["limits/solutions"] = 1
    opt.options["limits/gap"] = 0.10
    opt.options["display/verblevel"] = 4
```

### 6.18.5 Proof-focused

```python id="of8pao"
def scip_profile_proof_focused(opt):
    opt.options["limits/time"] = 7200
    opt.options["limits/gap"] = 1e-6
    opt.options["limits/absgap"] = 1e-8
    opt.options["display/verblevel"] = 4
    opt.options["display/relevantstats"] = "TRUE"
```

---

## 6.19 Reproducible option manifest

### 6.19.1 JSON manifest

```json id="40n7e0"
{
  "limits/time": 1800,
  "limits/gap": 0.0001,
  "limits/absgap": 1e-06,
  "display/verblevel": 4,
  "display/relevantstats": "TRUE",
  "parallel/mode": 1,
  "parallel/minnthreads": 1,
  "parallel/maxnthreads": 1
}
```

### 6.19.2 Loader

```python id="1kowki"
import json
from pathlib import Path
from pyomo.environ import SolverFactory

def solver_from_manifest(path: str):
    options = json.loads(Path(path).read_text())
    validate_scip_option_keys(options)

    opt = SolverFactory("scip")
    for key, value in options.items():
        opt.options[key] = value
    return opt
```

### 6.19.3 Archive policy

```text id="ohh9kg"
Archive per run:
  SCIP version text
  Pyomo version
  opt.options JSON
  generated scip.set if available
  solver log
  termination condition
  primal/dual bounds
  gap
  wall time
```

---

## 6.20 Failure-mode diagnostics

| Symptom                       | Likely cause                                         | Probe                                          | Fix                                                                                       |
| ----------------------------- | ---------------------------------------------------- | ---------------------------------------------- | ----------------------------------------------------------------------------------------- |
| SCIP rejects option           | misspelled key / invalid range / wrong type          | inspect `scip.log`; compare against `set save` | use exact key from installed SCIP                                                         |
| `display/statistics` invalid  | shell command confused with parameter                | `SCIP> set save all.set`; search key           | use `display/relevantstats` / `table/*/active`; use shell `display statistics` standalone |
| time limit ignored            | `limits/time` already set differently or wrong layer | print `opt.options`; inspect generated log     | set one source of truth                                                                   |
| local `scip.set` ignored      | Pyomo generated temp `scip.set`                      | look for Pyomo warning                         | move settings into `opt.options`                                                          |
| boolean rejected              | Python `True`/`False` string issue or case issue     | inspect generated setting line                 | use `"TRUE"` / `"FALSE"`                                                                  |
| no statistics in log          | verbosity too low / table inactive / no logfile      | `display/verblevel`, `display/relevantstats`   | enable display/table options and `logfile`                                                |
| parallel option has no effect | build/platform limitation or too-small model         | log + `set save`                               | verify build; benchmark; pin threads                                                      |
| tuned profile slower          | parameter overfitting                                | compare nodes/gap/log tables                   | roll back; tune one family at a time                                                      |

---

## 6.21 Agent checklist

```text id="t5a1hf"
1. Generate authoritative parameter list:
   SCIP> set save scip-all.set

2. Use exact slash-separated keys in Pyomo:
   opt.options["limits/time"] = 600

3. Prefer SCIP-native keys for SCIP-specific wrappers:
   limits/time
   limits/gap
   display/verblevel

4. Use solve(..., timelimit=T) only for solver-generic abstraction.

5. Do not mix Pyomo opt.options with ambient ./scip.set.

6. Treat shell commands separately from parameters:
   display statistics != display/statistics

7. For booleans, write "TRUE"/"FALSE".

8. Tune in this order:
   model formulation
   limits/gap/time
   display/logging
   presolving
   separating
   heuristics
   branching/lp/numerics only after evidence

9. Archive:
   options manifest
   solver log
   SCIP version
   parameter diff file
```

---

## 6.22 Compact mental model

```text id="35z1zz"
SCIP parameter:
  key = value

Pyomo:
  opt.options[key] = value

Pyomo writes:
  temporary scip.set

SCIP reads:
  scip.set from Pyomo temp cwd

Use:
  limits/*       stopping
  display/*      log verbosity
  table/*        statistics tables
  presolving/*   reductions
  separating/*   cuts
  heuristics/*   incumbents
  branching/*    search decisions
  constraints/*  handler-specific behavior
  lp/*           relaxation solves
  numerics/*     tolerances
  parallel/*     concurrent/parallel behavior, if build supports it

Golden rule:
  generate `set save` from the installed SCIP, then use those exact keys in Pyomo.
```

[1]: https://www.scipopt.org/doc/html/PARAMETERS.php "SCIP Doxygen Documentation: List of all SCIP parameters"
[2]: https://pyomo.readthedocs.io/en/6.8.2/_modules/pyomo/solvers/plugins/solvers/SCIPAMPL.html "pyomo.solvers.plugins.solvers.SCIPAMPL — Pyomo 6.8.2 documentation"
[3]: https://www.scipopt.org/doc/html/SHELL.php "SCIP Doxygen Documentation: Tutorial: the interactive shell"

# 7) Termination conditions, result interpretation, and diagnostics — Pyomo + SCIP

Dense technical reference for LLM programming agents. Style aligned with the uploaded advanced-reference template. 

---

## 7.0 Core result contract

```text id="tk82b7"
Pyomo solve result:
  results = opt.solve(model, ...)

Primary fields:
  results.solver.status
  results.solver.termination_condition
  results.solver.message
  results.solver.time              # parsed when available
  results.solver.gap               # parsed when available
  results.solver.primal_bound      # parsed when available
  results.solver.dual_bound        # parsed when available
  len(results.solution)

Model value loading:
  default solve(..., load_solutions=True) may load solution values
  production solve should use load_solutions=False
  load manually only after status/termination inspection
```

Pyomo’s standard result-handling pattern is to inspect `SolverStatus` and `TerminationCondition` after a solve; Pyomo’s own solver-status guidance shows checking `SolverStatus.ok` together with `TerminationCondition.optimal`, then handling infeasible and other cases separately. ([Pyomo][1])

---

## 7.1 Result fields: semantics

### 7.1.1 `results.solver.status`

```text id="rigmlf"
SolverStatus.ok:
  normal solver termination

SolverStatus.warning:
  solver terminated with unusual but recognized condition
  examples in SCIP mapping: infeasible, unbounded

SolverStatus.aborted:
  externally interrupted condition
  examples in SCIP mapping: user interrupt

SolverStatus.unknown:
  message not recognized / uninitialized / unmapped

SolverStatus.error:
  internal solver or interface failure
```

Pyomo’s public status list includes `ok`, `warning`, `error`, `aborted`, and `unknown`; the intended use is solver-independent scripting decisions after a solve. ([Pyomo][1])

### 7.1.2 `results.solver.termination_condition`

```text id="ghk47o"
TerminationCondition.optimal:
  proven optimal solution

TerminationCondition.infeasible:
  infeasibility demonstrated

TerminationCondition.unbounded:
  unboundedness demonstrated

TerminationCondition.infeasibleOrUnbounded:
  ambiguous infeasible-or-unbounded condition, when mapped

TerminationCondition.maxTimeLimit:
  time limit reached

TerminationCondition.maxEvaluations:
  node/evaluation limit reached in SCIP mapping

TerminationCondition.other:
  normal but uncategorized termination
  SCIP mapping uses this for memory/gap/solution-limit style stops

TerminationCondition.userInterrupt:
  user interrupt for legacy pyomo.opt result enums

TerminationCondition.unknown:
  unrecognized solver message
```

Pyomo’s legacy solver-status table lists `optimal`, `maxEvaluations`, `other`, `unbounded`, `infeasible`, `userInterrupt`, `resourceInterrupt`, and `unknown`-style categories; newer APPSI enums use different names for some conditions, so agents should compare against the enum imported by the interface being used. ([Pyomo][1])

### 7.1.3 `results.solver.message`

```text id="k4bt1h"
SCIP-facing meaning:
  textual solver termination/status message
  Pyomo SCIP plugin inspects substrings in this message
  message drives postsolve mapping for SCIP >= 8
```

Pyomo’s SCIP postsolve code branches on substrings such as `"time limit reached"`, `"optimal solution"`, `"infeasible"`, `"unbounded"`, `"gap limit reached"`, and `"solution limit reached"` inside `results.solver.message`. ([Pyomo Documentation][2])

---

## 7.2 SCIP log-derived fields

For SCIP version 8 or newer, Pyomo writes the command line and captured solver log to the log file, then parses the final SCIP summary block. If expected labels are present, it populates `results.solver.time`, `results.solver.gap`, `results.solver.primal_bound`, and `results.solver.dual_bound`. ([Pyomo Documentation][2])

```text id="aqjntb"
Parsed from SCIP log tail:
  SCIP Status
  Solving Time (sec)
  Solving Nodes
  Primal Bound
  Dual Bound
  Gap
```

Code probe:

```python id="ei2hz9"
def solver_metric(results, name, default=None):
    return getattr(results.solver, name, default)

print("status:", results.solver.status)
print("termination:", results.solver.termination_condition)
print("message:", getattr(results.solver, "message", None))
print("time:", solver_metric(results, "time"))
print("gap:", solver_metric(results, "gap"))
print("primal_bound:", solver_metric(results, "primal_bound"))
print("dual_bound:", solver_metric(results, "dual_bound"))
print("solutions:", len(results.solution))
```

Important caveat:

```text id="9bxzyj"
If SCIP solves during presolve or log tail format differs:
  primal_bound / dual_bound / gap may be absent.
Always access with getattr(..., None), not direct attribute access.
```

Pyomo’s SCIP source comments explicitly note that if SCIP solves during presolve, log parsing may not populate `results.solver.primal_bound`. ([Pyomo Documentation][2])

---

## 7.3 SCIP termination message → Pyomo mapping

### 7.3.1 Mapping table: SCIP message substring to Pyomo result

| SCIP message substring checked by Pyomo | `results.solver.status` | `results.solver.termination_condition` | Solution status if present  | Agent interpretation                           |
| --------------------------------------- | ----------------------- | -------------------------------------- | --------------------------- | ---------------------------------------------- |
| `"unknown"`                             | `SolverStatus.unknown`  | `TerminationCondition.unknown`         | `SolutionStatus.unknown`    | no reliable conclusion                         |
| `"user interrupt"`                      | `SolverStatus.aborted`  | `TerminationCondition.userInterrupt`   | `SolutionStatus.unknown`    | interrupted; solution may or may not be useful |
| `"node limit reached"`                  | `SolverStatus.ok`       | `TerminationCondition.maxEvaluations`  | `stoppedByLimit`            | node limit; incumbent may exist                |
| `"total node limit reached"`            | `SolverStatus.ok`       | `TerminationCondition.maxEvaluations`  | `stoppedByLimit`            | total-node budget hit                          |
| `"stall node limit reached"`            | `SolverStatus.ok`       | `TerminationCondition.maxEvaluations`  | `stoppedByLimit`            | stalled-node budget hit                        |
| `"time limit reached"`                  | `SolverStatus.ok`       | `TerminationCondition.maxTimeLimit`    | `stoppedByLimit`            | time limit; incumbent may exist                |
| `"memory limit reached"`                | `SolverStatus.ok`       | `TerminationCondition.other`           | `stoppedByLimit`            | resource stop; inspect log                     |
| `"gap limit reached"`                   | `SolverStatus.ok`       | `TerminationCondition.other`           | `stoppedByLimit`            | acceptable gap stop; inspect gap               |
| `"solution limit reached"`              | `SolverStatus.ok`       | `TerminationCondition.other`           | `stoppedByLimit`            | solution-count stop                            |
| `"solution improvement limit reached"`  | `SolverStatus.ok`       | `TerminationCondition.other`           | `stoppedByLimit`            | improvement-limit stop                         |
| `"optimal solution"`                    | `SolverStatus.ok`       | `TerminationCondition.optimal`         | `SolutionStatus.optimal`    | proven optimal                                 |
| `"infeasible"`                          | `SolverStatus.warning`  | `TerminationCondition.infeasible`      | `SolutionStatus.infeasible` | infeasible proof or ambiguous-string caveat    |
| `"unbounded"`                           | `SolverStatus.warning`  | `TerminationCondition.unbounded`       | `SolutionStatus.unbounded`  | unbounded proof                                |
| `"infeasible or unbounded"`             | intended branch exists  | intended `infeasibleOrUnbounded`       | `SolutionStatus.unsure`     | version-sensitive; see caveat                  |
| otherwise                               | `SolverStatus.unknown`  | `TerminationCondition.unknown`         | `SolutionStatus.unknown`    | unexpected message                             |

The table follows Pyomo’s SCIP postsolve implementation for SCIP 8+; the code maps node limits to `maxEvaluations`, time limit to `maxTimeLimit`, memory/gap/solution-limit stops to `other`, optimal to `optimal`, infeasible/unbounded to warning statuses, and unknown messages to `unknown`. ([Pyomo Documentation][2])

### 7.3.2 Ambiguous infeasible-or-unbounded caveat

```text id="g6wq15"
Pyomo SCIP source contains a branch for:
  "infeasible or unbounded" -> TerminationCondition.infeasibleOrUnbounded

But in the inspected 6.9.3 source, the broader substring check:
  "infeasible" in results.solver.message
appears before:
  "infeasible or unbounded" in results.solver.message

Agent-safe behavior:
  inspect results.solver.message directly for "infeasible or unbounded"
  do not rely only on termination_condition for ambiguous SCIP messages
```

The relevant source order checks `"infeasible"` before the later `"infeasible or unbounded"` branch, so robust agent code should explicitly examine `results.solver.message` when ambiguity matters. ([Pyomo Documentation][2])

---

## 7.4 Best-practice solve checks

### 7.4.1 Minimal branching pattern

```python id="xr09n5"
from pyomo.opt import TerminationCondition, SolverStatus

tc = results.solver.termination_condition

if tc == TerminationCondition.optimal:
    ...
elif tc == TerminationCondition.maxTimeLimit:
    ...
elif tc == TerminationCondition.infeasible:
    ...
else:
    ...
```

### 7.4.2 Production-safe pattern: inspect status + termination + solution count

```python id="83zomj"
from pyomo.opt import SolverStatus, TerminationCondition

def classify_pyomo_scip_result(results):
    status = results.solver.status
    tc = results.solver.termination_condition
    msg = str(getattr(results.solver, "message", "") or "")
    nsol = len(results.solution)

    if status == SolverStatus.ok and tc == TerminationCondition.optimal:
        return "optimal"

    if tc == TerminationCondition.infeasible:
        return "infeasible"

    if tc == TerminationCondition.unbounded:
        return "unbounded"

    if "infeasible or unbounded" in msg.lower():
        return "infeasible_or_unbounded"

    if tc == TerminationCondition.maxTimeLimit:
        return "time_limit_with_solution" if nsol else "time_limit_no_solution"

    if tc == TerminationCondition.maxEvaluations:
        return "node_limit_with_solution" if nsol else "node_limit_no_solution"

    if tc == TerminationCondition.other:
        msg_l = msg.lower()
        if "gap limit reached" in msg_l:
            return "gap_limit"
        if "solution limit reached" in msg_l:
            return "solution_limit"
        if "memory limit reached" in msg_l:
            return "memory_limit"
        return "other"

    if tc == TerminationCondition.userInterrupt:
        return "user_interrupt"

    if status == SolverStatus.unknown or tc == TerminationCondition.unknown:
        return "unknown"

    return "unexpected"
```

### 7.4.3 Load only after classification

```python id="cp3gkg"
results = opt.solve(model, tee=True, load_solutions=False)

kind = classify_pyomo_scip_result(results)

if kind == "optimal":
    model.solutions.load_from(results)

elif kind in {"time_limit_with_solution", "node_limit_with_solution", "gap_limit", "solution_limit"}:
    # only load if downstream policy accepts incumbent / gap-limited solution
    if len(results.solution) > 0:
        model.solutions.load_from(results)
    else:
        raise RuntimeError(f"{kind}: no solution available")

elif kind in {"infeasible", "unbounded", "infeasible_or_unbounded"}:
    raise RuntimeError(f"Model status: {kind}")

else:
    raise RuntimeError(
        f"Unhandled SCIP termination: "
        f"status={results.solver.status}, "
        f"tc={results.solver.termination_condition}, "
        f"message={getattr(results.solver, 'message', None)}"
    )
```

Pyomo’s recommended pattern is to query solver status and termination condition before acting on a result; the SCIP plugin’s mapping further requires checking solution count for limit stops because a limit can be reached with or without an incumbent. ([Pyomo][1])

---

## 7.5 Acceptance policies

### 7.5.1 Strict exact optimization policy

```text id="nrcf6r"
Accept:
  SolverStatus.ok + TerminationCondition.optimal

Reject:
  infeasible
  unbounded
  infeasibleOrUnbounded
  maxTimeLimit
  maxEvaluations
  other
  unknown
```

```python id="sr109p"
def require_proven_optimal(results, model):
    if (
        results.solver.status == SolverStatus.ok
        and results.solver.termination_condition == TerminationCondition.optimal
    ):
        model.solutions.load_from(results)
        return

    raise RuntimeError(
        f"Expected proven optimality, got "
        f"{results.solver.status=} "
        f"{results.solver.termination_condition=} "
        f"message={getattr(results.solver, 'message', None)}"
    )
```

### 7.5.2 Gap-limited production policy

```text id="5qhocu"
Accept:
  optimal
  gap limit reached
  time limit with incumbent and acceptable gap
  node limit with incumbent and acceptable gap

Reject:
  no incumbent
  infeasible
  unbounded
  unknown
```

```python id="2b8c9j"
def get_gap(results):
    gap = getattr(results.solver, "gap", None)
    if isinstance(gap, str):
        if gap.lower() == "infinite":
            return float("inf")
        return None
    return gap

def accept_with_gap(results, model, max_gap_pct=1.0):
    tc = results.solver.termination_condition
    msg = str(getattr(results.solver, "message", "") or "").lower()
    gap = get_gap(results)

    if tc == TerminationCondition.optimal:
        model.solutions.load_from(results)
        return "optimal"

    if len(results.solution) == 0:
        raise RuntimeError("No solution incumbent available")

    if "gap limit reached" in msg:
        model.solutions.load_from(results)
        return "gap_limit"

    if tc in {TerminationCondition.maxTimeLimit, TerminationCondition.maxEvaluations}:
        if gap is not None and gap <= max_gap_pct:
            model.solutions.load_from(results)
            return f"limit_with_gap_{gap}"
        raise RuntimeError(f"Limit reached but gap unacceptable or unavailable: gap={gap}")

    raise RuntimeError(f"Unacceptable termination: {tc}, message={msg}")
```

Pyomo stores `results.solver.gap` when the SCIP log tail matches expected labels, parsing numeric percent values or the string `infinite` into `float("inf")`. ([Pyomo Documentation][2])

### 7.5.3 Feasible-first policy

```text id="4wxg0r"
Accept:
  first feasible solution
  solution limit reached with incumbent
  time limit with incumbent

Used for:
  planning
  warm-start generation
  heuristic pipelines
  model feasibility smoke tests

Not acceptable for:
  proof of optimality
  audited cost-minimization reports
```

```python id="pbmvp3"
def accept_any_incumbent(results, model):
    if len(results.solution) > 0:
        model.solutions.load_from(results)
        return

    raise RuntimeError(
        f"No incumbent solution: "
        f"{results.solver.status=} "
        f"{results.solver.termination_condition=} "
        f"message={getattr(results.solver, 'message', None)}"
    )
```

---

## 7.6 Bounds, gap, and objective interpretation

### 7.6.1 Field semantics

```text id="89rnfj"
primal_bound:
  objective value of best known feasible solution / incumbent

dual_bound:
  best proof bound from relaxation/tree

gap:
  primal-dual gap as reported by SCIP log
  parsed by Pyomo when final log summary format matches

problem.lower_bound / problem.upper_bound:
  Pyomo sets these on optimal runs from primal/dual bounds when available
```

For optimal SCIP messages, Pyomo tries to set `results.problem.lower_bound` and `results.problem.upper_bound` from the parsed primal and dual bounds, choosing lower/upper by numerical comparison. ([Pyomo Documentation][2])

### 7.6.2 Robust summary extraction

```python id="k8nm84"
def scip_result_summary(results):
    solver = results.solver
    return {
        "status": str(solver.status),
        "termination_condition": str(solver.termination_condition),
        "message": str(getattr(solver, "message", "")),
        "time": getattr(solver, "time", None),
        "gap": getattr(solver, "gap", None),
        "primal_bound": getattr(solver, "primal_bound", None),
        "dual_bound": getattr(solver, "dual_bound", None),
        "n_solutions": len(results.solution),
        "problem_lower_bound": getattr(results.problem, "lower_bound", None),
        "problem_upper_bound": getattr(results.problem, "upper_bound", None),
    }
```

### 7.6.3 Gap field caveat

```text id="u728xo"
SCIP log prints gap as a percent string.
Pyomo parser stores the numeric part as float.
Therefore:
  SCIP log "Gap : 0.01 %" -> results.solver.gap == 0.01
Interpret as percent units, not fraction, unless confirmed by local parser/log convention.
```

The parser extracts the text before `%` from the `Gap` line and converts it to `float`; if it sees `infinite`, it returns `float("inf")`. ([Pyomo Documentation][2])

---

## 7.7 Diagnostics by termination condition

### 7.7.1 `optimal`

```text id="x5h7sv"
Meaning:
  proven optimal by SCIP/Pyomo mapping

Agent action:
  load solution
  record objective
  record primal/dual/gap/time
  archive log and options
```

```python id="c0a9bk"
if results.solver.termination_condition == TerminationCondition.optimal:
    model.solutions.load_from(results)
```

### 7.7.2 `infeasible`

```text id="ur71th"
Meaning:
  SCIP/Pyomo message indicates infeasibility

Agent action:
  do not load solution
  run Pyomo infeasibility diagnostics
  check data bounds and big-M
  solve relaxed model
  preserve .nl/.row/.col/log
```

```python id="or4s69"
from pyomo.util.infeasible import log_infeasible_constraints

if tc == TerminationCondition.infeasible:
    log_infeasible_constraints(model, log_expression=True, log_variables=True)
```

### 7.7.3 `unbounded`

```text id="4fikaw"
Meaning:
  objective can improve without bound or formulation missing bounds

Agent action:
  inspect objective sense
  check missing variable bounds
  add physical/domain bounds
  solve feasibility-only version
  inspect extreme rays if solver/interface supports
```

### 7.7.4 `infeasibleOrUnbounded`

```text id="6iaphq"
Meaning:
  solver cannot distinguish infeasible from unbounded under current solve information

Agent action:
  inspect raw message
  add/verify bounds
  solve feasibility version
  disable objective or add artificial bounds
  compare with another solver
```

Version-sensitive caveat: in the inspected Pyomo SCIP source, the generic `"infeasible"` check occurs before `"infeasible or unbounded"`, so agents should check `results.solver.message` directly for this phrase. ([Pyomo Documentation][2])

### 7.7.5 `maxTimeLimit`

```text id="8d8bau"
Meaning:
  SCIP time limit reached

Agent action:
  if incumbent exists:
    evaluate solution quality
    inspect gap/primal/dual
    load only if policy accepts
  if no incumbent:
    treat as no-solution failure
```

```python id="ne3s29"
if tc == TerminationCondition.maxTimeLimit:
    if len(results.solution) > 0:
        gap = getattr(results.solver, "gap", None)
        ...
    else:
        raise RuntimeError("Time limit reached without incumbent")
```

### 7.7.6 `maxEvaluations` for node limits

```text id="z0xuxr"
SCIP messages:
  node limit reached
  total node limit reached
  stall node limit reached

Pyomo mapping:
  TerminationCondition.maxEvaluations

Agent action:
  inspect node limit settings
  inspect incumbent/gap
  increase limits/nodes or limits/totalnodes
  improve formulation strength
```

Pyomo maps SCIP node, total-node, and stall-node limit messages to `TerminationCondition.maxEvaluations`. ([Pyomo Documentation][2])

### 7.7.7 `other` for memory/gap/solution/improvement limits

```text id="u9gj8a"
SCIP messages mapped to other:
  memory limit reached
  gap limit reached
  solution limit reached
  solution improvement limit reached

Agent action:
  inspect results.solver.message
  branch by message substring
```

Pyomo maps SCIP memory limit, gap limit, solution limit, and solution-improvement limit messages to `TerminationCondition.other`, so robust code must inspect `results.solver.message` to distinguish these cases. ([Pyomo Documentation][2])

```python id="eu2ctq"
if tc == TerminationCondition.other:
    msg = str(getattr(results.solver, "message", "")).lower()
    if "gap limit reached" in msg:
        ...
    elif "memory limit reached" in msg:
        ...
    elif "solution limit reached" in msg:
        ...
    else:
        ...
```

### 7.7.8 `userInterrupt`

```text id="g2kwvj"
Meaning:
  user interrupted SCIP

Agent action:
  do not assume valid solution
  check len(results.solution)
  record partial artifacts
  treat as canceled job in orchestration layer
```

Pyomo maps `"user interrupt"` messages to `SolverStatus.aborted` and `TerminationCondition.userInterrupt`. ([Pyomo Documentation][2])

### 7.7.9 `unknown`

```text id="gujl86"
Meaning:
  message unknown or unmapped

Agent action:
  do not load by default
  inspect solver log
  preserve files
  emit diagnostic package
  consider solver/interface/version mismatch
```

Pyomo logs a warning for unexpected SCIP solver messages, sets status to `SolverStatus.unknown`, and sets termination to `TerminationCondition.unknown`. ([Pyomo Documentation][2])

---

## 7.8 Full diagnostic wrapper

```python id="qn1p4w"
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pyomo.environ import SolverFactory
from pyomo.opt import SolverStatus, TerminationCondition


@dataclass(frozen=True)
class ScipDecision:
    kind: str
    should_load: bool
    proven_optimal: bool
    has_incumbent: bool
    acceptable: bool
    reason: str


def summarize_scip_result(results) -> dict[str, Any]:
    solver = results.solver
    return {
        "status": str(solver.status),
        "termination_condition": str(solver.termination_condition),
        "message": str(getattr(solver, "message", "") or ""),
        "time": getattr(solver, "time", None),
        "gap": getattr(solver, "gap", None),
        "primal_bound": getattr(solver, "primal_bound", None),
        "dual_bound": getattr(solver, "dual_bound", None),
        "n_solutions": len(results.solution),
    }


def decide_scip_result(
    results,
    *,
    accept_limit_incumbent: bool = False,
    accept_gap_limit: bool = True,
    max_gap_percent: float | None = None,
) -> ScipDecision:
    status = results.solver.status
    tc = results.solver.termination_condition
    msg = str(getattr(results.solver, "message", "") or "").lower()
    nsol = len(results.solution)
    has_incumbent = nsol > 0
    gap = getattr(results.solver, "gap", None)

    if status == SolverStatus.ok and tc == TerminationCondition.optimal:
        return ScipDecision("optimal", True, True, has_incumbent, True, "proven optimal")

    if "infeasible or unbounded" in msg:
        return ScipDecision(
            "infeasible_or_unbounded", False, False, has_incumbent, False,
            "ambiguous infeasible-or-unbounded message"
        )

    if tc == TerminationCondition.infeasible:
        return ScipDecision("infeasible", False, False, has_incumbent, False, "infeasible")

    if tc == TerminationCondition.unbounded:
        return ScipDecision("unbounded", False, False, has_incumbent, False, "unbounded")

    if tc == TerminationCondition.maxTimeLimit:
        if not has_incumbent:
            return ScipDecision("time_limit_no_solution", False, False, False, False, "no incumbent")
        if accept_limit_incumbent:
            if max_gap_percent is None or (isinstance(gap, (int, float)) and gap <= max_gap_percent):
                return ScipDecision("time_limit_incumbent", True, False, True, True, "accepted incumbent")
        return ScipDecision("time_limit_incumbent_rejected", False, False, True, False, "policy rejected")

    if tc == TerminationCondition.maxEvaluations:
        if not has_incumbent:
            return ScipDecision("node_limit_no_solution", False, False, False, False, "no incumbent")
        if accept_limit_incumbent:
            return ScipDecision("node_limit_incumbent", True, False, True, True, "accepted incumbent")
        return ScipDecision("node_limit_incumbent_rejected", False, False, True, False, "policy rejected")

    if tc == TerminationCondition.other:
        if "gap limit reached" in msg and has_incumbent and accept_gap_limit:
            return ScipDecision("gap_limit", True, False, True, True, "gap limit reached")
        if "solution limit reached" in msg and has_incumbent and accept_limit_incumbent:
            return ScipDecision("solution_limit", True, False, True, True, "solution limit reached")
        if "memory limit reached" in msg:
            return ScipDecision("memory_limit", False, False, has_incumbent, False, "memory limit")
        return ScipDecision("other", False, False, has_incumbent, False, "uncategorized other")

    if tc == TerminationCondition.userInterrupt:
        return ScipDecision("user_interrupt", False, False, has_incumbent, False, "user interrupt")

    return ScipDecision("unknown", False, False, has_incumbent, False, f"unhandled {status=} {tc=}")


def solve_scip_with_policy(model, *, options=None, logfile="scip.log", debug=False):
    opt = SolverFactory("scip", solver_io="nl")
    if not opt.available(False):
        raise RuntimeError("SCIP unavailable")

    for k, v in (options or {}).items():
        opt.options[k] = v

    results = opt.solve(
        model,
        tee=True,
        logfile=logfile,
        keepfiles=debug,
        symbolic_solver_labels=debug,
        load_solutions=False,
    )

    decision = decide_scip_result(
        results,
        accept_limit_incumbent=False,
        accept_gap_limit=True,
    )

    if decision.should_load:
        model.solutions.load_from(results)

    return results, decision, summarize_scip_result(results)
```

---

## 7.9 Recommended `solve()` policy presets

### 7.9.1 Proven-optimal-only

```python id="h9r3jr"
results = opt.solve(model, tee=True, load_solutions=False)
decision = decide_scip_result(results)

if decision.kind != "optimal":
    raise RuntimeError(summarize_scip_result(results))

model.solutions.load_from(results)
```

### 7.9.2 Accept optimal or SCIP gap-limit stop

```python id="gvxiek"
results = opt.solve(model, tee=True, load_solutions=False)
decision = decide_scip_result(results, accept_gap_limit=True)

if decision.kind in {"optimal", "gap_limit"} and decision.should_load:
    model.solutions.load_from(results)
else:
    raise RuntimeError(summarize_scip_result(results))
```

### 7.9.3 Accept time-limited incumbent under gap threshold

```python id="of0g1y"
results = opt.solve(model, tee=True, load_solutions=False)
decision = decide_scip_result(
    results,
    accept_limit_incumbent=True,
    max_gap_percent=1.0,
)

if decision.acceptable and decision.should_load:
    model.solutions.load_from(results)
else:
    raise RuntimeError(summarize_scip_result(results))
```

---

## 7.10 Diagnostic artifacts

```text id="kwf3n5"
For any non-optimal/nontrivial termination, preserve:
  results.solver.status
  results.solver.termination_condition
  results.solver.message
  results.solver.time
  results.solver.gap
  results.solver.primal_bound
  results.solver.dual_bound
  len(results.solution)
  SCIP log file
  generated .nl
  generated .row/.col if symbolic labels enabled
  generated .sol if keepfiles enabled
  solver options manifest
  environment fingerprint
```

Debug solve call:

```python id="brb3ij"
results = opt.solve(
    model,
    tee=True,
    logfile="debug/scip.log",
    keepfiles=True,
    symbolic_solver_labels=True,
    load_solutions=False,
)
```

---

## 7.11 Termination-condition triage table

| Termination                                        |                    Load solution? | Trust optimality? | Primary diagnostic action                    |
| -------------------------------------------------- | --------------------------------: | ----------------: | -------------------------------------------- |
| `optimal`                                          |                               yes |               yes | archive objective/gap/bounds/log             |
| `infeasible`                                       |                                no |               n/a | infeasibility diagnostics, data/bounds check |
| `unbounded`                                        |                                no |               n/a | bound audit, objective-sense audit           |
| `infeasibleOrUnbounded` or message contains phrase |                                no |               n/a | disambiguate with bounds/feasibility solve   |
| `maxTimeLimit` with incumbent                      |                  policy-dependent |                no | inspect gap/primal/dual                      |
| `maxTimeLimit` without incumbent                   |                                no |                no | reformulate, increase time, heuristics       |
| `maxEvaluations` with incumbent                    |                  policy-dependent |                no | inspect gap/nodes/formulation                |
| `maxEvaluations` without incumbent                 |                                no |                no | reformulate, increase node limits            |
| `other` + gap message                              | usually yes if gap policy says so |                no | inspect `gap` field                          |
| `other` + solution-limit message                   |                  policy-dependent |                no | inspect solution count/objective             |
| `other` + memory message                           |                        usually no |                no | reduce model, memory, cuts, presolve         |
| `userInterrupt`                                    |                        usually no |                no | mark canceled, preserve partial artifacts    |
| `unknown`                                          |                                no |                no | inspect full log and plugin/version behavior |

---

## 7.12 Compact mental model

```text id="jgykuq"
Always read:
  status = results.solver.status
  tc = results.solver.termination_condition
  msg = results.solver.message

Never assume:
  time limit implies feasible incumbent
  gap limit maps to a unique enum
  memory limit maps to resourceInterrupt
  infeasible-or-unbounded always maps cleanly
  gap/primal_bound/dual_bound always exist

For SCIP via Pyomo:
  optimal -> SolverStatus.ok + TerminationCondition.optimal
  node limits -> maxEvaluations
  time limit -> maxTimeLimit
  memory/gap/solution limits -> other
  infeasible/unbounded -> SolverStatus.warning
  unknown/unexpected -> unknown

Production default:
  solve(..., load_solutions=False)
  classify result
  load only if policy accepts
  archive message + log + gap/bounds
```

[1]: https://www.pyomo.org/blog/2015/1/8/accessing-solver "Accessing solver status and termination conditions — Pyomo"
[2]: https://pyomo.readthedocs.io/en/6.9.3/_modules/pyomo/solvers/plugins/solvers/SCIPAMPL.html "pyomo.solvers.plugins.solvers.SCIPAMPL — Pyomo 6.9.3 documentation"

# 8) Logging, statistics, and reproducibility — Pyomo + SCIP

Dense technical reference for LLM programming agents. Style aligned with the uploaded advanced-reference template. 

---

## 8.0 Logging/reproducibility contract

```text id="cjf6bb"
Pyomo logging surfaces:
  tee=True
  logfile="scip.log"
  keepfiles=True
  symbolic_solver_labels=True

SCIP logging surfaces:
  display/verblevel
  display/freq
  display/headerfreq
  display/relevantstats
  table/*/active

Artifacts:
  .nl
  .row
  .col
  .sol
  .log
  generated scip.set
  parameter snapshot
  environment fingerprint
  solver results JSON

Reproducibility hazards:
  package version drift
  SCIP parameter drift
  model data ordering
  Pyomo writer determinism
  randomization seeds
  parallel/concurrent solving
  numeric tolerances
  platform / CPU / LP solver behavior
```

Pyomo’s legacy solve signature exposes `tee`, `load_solutions`, `logfile`, `timelimit`, `options`, `keepfiles`, `symbolic_solver_labels`, and `writer_config`; the SCIP plugin itself captures SCIP output, writes a log, and parses final SCIP summary fields when available. ([pyomo.readthedocs.io][1])

---

## 8.1 `tee=True` vs `logfile=...`

### 8.1.1 `tee=True`

```python id="qoqsl7"
res = opt.solve(model, tee=True)
```

Semantics:

```text id="xxgfde"
tee=True:
  stream solver log to stdout/stderr during solve
  useful for interactive diagnosis
  not a durable artifact unless outer process captures stdout
  noisy in CI/batch unless intentionally enabled
```

### 8.1.2 `logfile="scip.log"`

```python id="0z7zgk"
res = opt.solve(model, logfile="scip.log")
```

Semantics:

```text id="c5vdas"
logfile="scip.log":
  write solver log to named file
  durable artifact
  required for postmortem parsing
  usually preferred in CI/production
```

### 8.1.3 Both

```python id="xysj4l"
res = opt.solve(
    model,
    tee=True,
    logfile="scip.log",
)
```

Semantics:

```text id="69ipjx"
tee=True + logfile:
  stream live progress
  preserve durable log
  preferred during manual tuning/debugging
```

### 8.1.4 Debug artifact solve

```python id="2xrn4u"
res = opt.solve(
    model,
    tee=True,
    logfile="runs/001/scip.log",
    keepfiles=True,
    symbolic_solver_labels=True,
    load_solutions=False,
)
```

`keepfiles=True` and `symbolic_solver_labels=True` are critical for mapping solver artifacts back to Pyomo variables/constraints; Pyomo’s solve wrapper documents both options directly in the solve signature. ([pyomo.readthedocs.io][1])

---

## 8.2 SCIP display verbosity

### 8.2.1 Native display parameters

```python id="7xxrwz"
opt.options["display/verblevel"] = 4
opt.options["display/width"] = 143
opt.options["display/freq"] = 100
opt.options["display/headerfreq"] = 15
opt.options["display/lpinfo"] = "FALSE"
opt.options["display/allviols"] = "FALSE"
opt.options["display/relevantstats"] = "TRUE"
```

Current SCIP parameters define `display/verblevel` with integer range `[0,5]` and default `4`; `display/freq`, `display/headerfreq`, `display/lpinfo`, `display/allviols`, and `display/relevantstats` are also native parameters. ([scipopt.org][2])

### 8.2.2 Verbosity presets

```python id="naem5c"
def scip_display_quiet(opt):
    opt.options["display/verblevel"] = 0

def scip_display_normal(opt):
    opt.options["display/verblevel"] = 4
    opt.options["display/relevantstats"] = "TRUE"

def scip_display_debug(opt):
    opt.options["display/verblevel"] = 5
    opt.options["display/lpinfo"] = "TRUE"
    opt.options["display/allviols"] = "TRUE"
    opt.options["display/relevantstats"] = "TRUE"
```

### 8.2.3 Display frequency controls

```python id="nezfzf"
# Fewer progress lines
opt.options["display/freq"] = 1000
opt.options["display/headerfreq"] = 50

# More progress lines
opt.options["display/freq"] = 10
opt.options["display/headerfreq"] = 5
```

Value case:

```text id="bj7nl4"
High-frequency display:
  useful for live tuning
  useful for progress monitoring
  increases log size

Low-frequency display:
  cleaner CI logs
  smaller artifacts
  less log parsing overhead
```

---

## 8.3 Statistics output: correct SCIP-native settings

### 8.3.1 Important correction: `display/statistics`

```text id="ihj3e2"
Do not use as a current native SCIP parameter:
  display/statistics = TRUE

Use instead:
  display/relevantstats = TRUE
  table/<name>/active = TRUE

Standalone shell command:
  display statistics
```

The current SCIP parameter list includes `display/relevantstats`, but not a native `display/statistics` key; the interactive shell separately supports commands such as `display statistics`. ([scipopt.org][2])

### 8.3.2 Enable relevant final statistics

```python id="zs5cj5"
opt.options["display/relevantstats"] = "TRUE"
```

SCIP’s parameter list describes `display/relevantstats` as “should the relevant statistics be displayed at the end of solving?” with default `TRUE`. ([scipopt.org][2])

### 8.3.3 Enable detailed statistics tables

```python id="dxwbtv"
opt.options["table/status/active"] = "TRUE"
opt.options["table/timing/active"] = "TRUE"
opt.options["table/presolver/active"] = "TRUE"
opt.options["table/constraint/active"] = "TRUE"
opt.options["table/propagator/active"] = "TRUE"
opt.options["table/conflict/active"] = "TRUE"
opt.options["table/separator/active"] = "TRUE"
opt.options["table/cutsel/active"] = "TRUE"
opt.options["table/branchrules/active"] = "TRUE"
opt.options["table/heuristics/active"] = "TRUE"
opt.options["table/lp/active"] = "TRUE"
opt.options["table/nlp/active"] = "TRUE"
opt.options["table/tree/active"] = "TRUE"
opt.options["table/root/active"] = "TRUE"
opt.options["table/solution/active"] = "TRUE"
```

SCIP exposes statistics-table activation switches such as `table/conflict/active`, `table/separator/active`, `table/branchrules/active`, `table/heuristics/active`, `table/lp/active`, `table/nlp/active`, `table/tree/active`, `table/root/active`, and `table/solution/active`. ([scipopt.org][2])

### 8.3.4 Standalone shell statistics

```text id="0mgyxl"
SCIP> read model.lp
SCIP> optimize
SCIP> display statistics
SCIP> set save all_params.set
SCIP> set diffsave tuned_params.set
```

The SCIP shell tutorial documents `display` commands, parameter saving/loading, and `set save` / `set diffsave` workflows. ([scipopt.org][3])

---

## 8.4 Pyomo SCIP log parsing

### 8.4.1 Parsed final summary labels

Pyomo’s SCIP plugin expects final log labels:

```text id="wgbg83"
SCIP Status        :
Solving Time (sec) :
Solving Nodes      :
Primal Bound       :
Dual Bound         :
Gap                :
```

The SCIP plugin source lists these exact expected labels and parses solving time, nodes, primal bound, dual bound, and gap from them. ([pyomo.readthedocs.io][4])

### 8.4.2 Access parsed fields

```python id="u7txi6"
summary = {
    "status": str(res.solver.status),
    "termination_condition": str(res.solver.termination_condition),
    "message": str(getattr(res.solver, "message", "")),
    "time": getattr(res.solver, "time", None),
    "gap": getattr(res.solver, "gap", None),
    "primal_bound": getattr(res.solver, "primal_bound", None),
    "dual_bound": getattr(res.solver, "dual_bound", None),
    "solutions": len(res.solution),
}
```

### 8.4.3 Parsing caveat

```text id="2azpap"
Do not assume fields exist:
  results.solver.gap
  results.solver.primal_bound
  results.solver.dual_bound

Reasons:
  SCIP solved during presolve
  log format mismatch
  solve failed before summary
  old SCIP / old Pyomo behavior
```

The SCIP plugin source explicitly warns that when SCIP solves during presolve, log parsing may not populate primal/dual bound attributes. ([pyomo.readthedocs.io][4])

---

## 8.5 Reading solver logs manually

### 8.5.1 Final summary block parser

```python id="nq6m0s"
from __future__ import annotations

from pathlib import Path
import math
import re

FINAL_LABELS = {
    "SCIP Status": "status",
    "Solving Time (sec)": "time_sec",
    "Solving Nodes": "nodes",
    "Primal Bound": "primal_bound",
    "Dual Bound": "dual_bound",
    "Gap": "gap",
}

def _parse_float_token(text: str):
    token = text.strip().split()[0]
    token_l = token.lower()
    if token_l in {"infinite", "inf", "+inf", "+infinity"}:
        return math.inf
    if token_l in {"-inf", "-infinity"}:
        return -math.inf
    return float(token)

def parse_scip_final_summary(log_path: str | Path) -> dict[str, object]:
    out: dict[str, object] = {}
    for raw in Path(log_path).read_text(errors="replace").splitlines():
        if ":" not in raw:
            continue
        left, right = raw.split(":", 1)
        key = left.strip()
        value = right.strip()
        if key not in FINAL_LABELS:
            continue

        dst = FINAL_LABELS[key]

        if dst == "status":
            out[dst] = value
        elif dst == "time_sec":
            out[dst] = _parse_float_token(value)
        elif dst == "nodes":
            out[dst] = int(float(value.strip().split()[0]))
        elif dst in {"primal_bound", "dual_bound"}:
            out[dst] = _parse_float_token(value)
        elif dst == "gap":
            if "infinite" in value.lower():
                out[dst] = math.inf
            else:
                out[dst] = _parse_float_token(value.replace("%", ""))
    return out
```

### 8.5.2 Presolve reductions: log patterns to inspect

```text id="n73q6f"
Search terms:
  presolving
  presolved problem
  deleted variables
  deleted constraints
  fixed variables
  upgraded constraints
  tightened bounds
  implications
  cliques
  symmetry
  restarts
```

Agent log triage:

```python id="mqk7kk"
def grep_log(log_path, patterns):
    lines = Path(log_path).read_text(errors="replace").splitlines()
    hits = []
    for i, line in enumerate(lines, start=1):
        low = line.lower()
        if any(p.lower() in low for p in patterns):
            hits.append((i, line))
    return hits

presolve_hits = grep_log("scip.log", [
    "presolving",
    "presolved problem",
    "deleted variables",
    "deleted constraints",
    "fixed",
    "upgraded",
    "symmetry",
])
```

### 8.5.3 Separator/cut diagnostics

```text id="xsql10"
Search terms:
  separator
  cut
  cuts
  separation
  LP rows
  root
  table/separator
  table/cutsel
```

Enable tables:

```python id="oyjg4e"
opt.options["display/relevantstats"] = "TRUE"
opt.options["table/separator/active"] = "TRUE"
opt.options["table/cutsel/active"] = "TRUE"
```

### 8.5.4 Heuristic diagnostics

```text id="odybf9"
Search terms:
  heuristic
  primal
  solution
  incumbent
  found
  table/heuristics
```

Enable table:

```python id="b1vblh"
opt.options["display/relevantstats"] = "TRUE"
opt.options["table/heuristics/active"] = "TRUE"
```

### 8.5.5 Branch-and-bound progress diagnostics

```text id="447jnn"
Read:
  Solving Nodes
  node lines
  primal bound changes
  dual bound changes
  gap trajectory
  root time
  tree size
  memory indicators
```

The Pyomo SCIP plugin parses the final `Solving Nodes`, `Primal Bound`, `Dual Bound`, and `Gap` summary labels when available; detailed time-series extraction still requires reading the raw solver log. ([pyomo.readthedocs.io][4])

---

## 8.6 Recommended logging profiles

### 8.6.1 Minimal CI profile

```python id="7rrmrf"
def apply_scip_ci_logging(opt):
    opt.options["display/verblevel"] = 0
    opt.options["display/relevantstats"] = "FALSE"
```

Solve:

```python id="2htm8t"
res = opt.solve(
    model,
    tee=False,
    logfile="scip-ci.log",
    load_solutions=False,
)
```

### 8.6.2 Production profile

```python id="jcvn15"
def apply_scip_production_logging(opt):
    opt.options["display/verblevel"] = 4
    opt.options["display/freq"] = 1000
    opt.options["display/headerfreq"] = 50
    opt.options["display/relevantstats"] = "TRUE"
    opt.options["table/timing/active"] = "TRUE"
    opt.options["table/lp/active"] = "TRUE"
    opt.options["table/tree/active"] = "TRUE"
    opt.options["table/solution/active"] = "TRUE"
```

Solve:

```python id="pn2vqo"
res = opt.solve(
    model,
    tee=False,
    logfile="runs/001/scip.log",
    keepfiles=False,
    load_solutions=False,
)
```

### 8.6.3 Debug/tuning profile

```python id="12yn6l"
def apply_scip_debug_logging(opt):
    opt.options["display/verblevel"] = 5
    opt.options["display/freq"] = 10
    opt.options["display/headerfreq"] = 5
    opt.options["display/lpinfo"] = "TRUE"
    opt.options["display/allviols"] = "TRUE"
    opt.options["display/relevantstats"] = "TRUE"

    for table in [
        "status",
        "timing",
        "presolver",
        "constraint",
        "propagator",
        "conflict",
        "separator",
        "cutsel",
        "branchrules",
        "heuristics",
        "lp",
        "nlp",
        "tree",
        "root",
        "solution",
    ]:
        opt.options[f"table/{table}/active"] = "TRUE"
```

Solve:

```python id="w5w1nq"
res = opt.solve(
    model,
    tee=True,
    logfile="debug/scip.log",
    keepfiles=True,
    symbolic_solver_labels=True,
    load_solutions=False,
)
```

---

## 8.7 Reproducibility checklist

### 8.7.1 Environment

```text id="ng4xnb"
Pin:
  python
  pyomo
  scip
  pyscipopt if used
  numpy/pandas if data generation depends on them
  platform lockfile if production

Capture:
  python executable
  Pyomo version
  SCIP executable
  SCIP --version output
  conda/micromamba package list
  channel list + channel priority
```

### 8.7.2 Solver parameter state

```text id="9pxslx"
Capture:
  full parameter file:
    SCIP> set save scip-all.set

  changed parameter file:
    SCIP> set diffsave scip-diff.set

  Pyomo options manifest:
    opt.options JSON
```

The official SCIP parameter page states the full parameter list can be generated with `SCIP> set save <file name>`; the shell tutorial documents `set save`, `set diffsave`, and `set load`. ([scipopt.org][5])

### 8.7.3 Model artifacts

```text id="fpzwyi"
Store for difficult cases:
  model.nl
  model.row
  model.col
  model.sol
  scip.log
  generated scip.set
  data input snapshot
  model build code version
  transformation choices
```

Pyomo’s SCIP path is NL/SOL based; Pyomo exposes `keepfiles` and `symbolic_solver_labels` in the solve call, and SCIPAMPL uses `.sol` as the result format for NL. ([pyomo.readthedocs.io][1])

### 8.7.4 Randomization and determinism

Recommended deterministic-ish settings:

```python id="cb3lae"
opt.options["randomization/randomseedshift"] = 0
opt.options["randomization/permutationseed"] = 0
opt.options["randomization/permuteconss"] = "FALSE"
opt.options["randomization/permutevars"] = "FALSE"
opt.options["randomization/lpseed"] = 0

opt.options["parallel/mode"] = 1
opt.options["parallel/minnthreads"] = 1
opt.options["parallel/maxnthreads"] = 1
```

SCIP exposes global randomization parameters including `randomization/randomseedshift`, `randomization/permutationseed`, `randomization/permuteconss`, `randomization/permutevars`, and `randomization/lpseed`; SCIP also exposes `parallel/mode` with `0` opportunistic and `1` deterministic, plus minimum/maximum thread count parameters. ([scipopt.org][2])

### 8.7.5 Writer determinism

```python id="wry3mi"
res = opt.solve(
    model,
    tee=False,
    logfile="scip.log",
    keepfiles=True,
    symbolic_solver_labels=True,
    writer_config={
        "file_determinism": 30,  # SORT_SYMBOLS in Pyomo NL writer conventions
    },
    load_solutions=False,
)
```

Value case:

```text id="43d7fk"
Use deterministic writer settings when:
  diffing .nl files
  auditing model generation
  regression testing
  comparing formulation changes
```

---

## 8.8 Capturing generated `scip.set` from Pyomo

### 8.8.1 Pyomo internal behavior

```text id="7420m8"
opt.options nonempty:
  Pyomo writes temporary scip.set
  Pyomo runs SCIP with cwd=temp_options_dir
  ambient cwd/scip.set ignored with warning
```

Pyomo’s SCIP plugin formats option lines as `key = value`, writes them to a temporary `scip.set`, sets the command working directory to that temporary options directory, and warns if a current-directory `scip.set` would be ignored. ([pyomo.readthedocs.io][4])

### 8.8.2 Reconstruct Pyomo-generated settings from `opt.options`

```python id="9eas78"
from pathlib import Path

def write_pyomo_scip_set(opt, path: str):
    lines = []
    for key, value in sorted(opt.options.items()):
        if key == "solver":
            continue
        lines.append(f"{key} = {value}")
    Path(path).write_text("\n".join(lines) + "\n")

write_pyomo_scip_set(opt, "runs/001/scip-from-pyomo-options.set")
```

### 8.8.3 Options manifest

```python id="8ak5op"
import json
from pathlib import Path

def write_options_manifest(opt, path: str):
    data = {str(k): str(v) for k, v in sorted(opt.options.items()) if k != "solver"}
    Path(path).write_text(json.dumps(data, indent=2, sort_keys=True))

write_options_manifest(opt, "runs/001/scip-options.json")
```

---

## 8.9 Environment fingerprint

```python id="pfz4lp"
from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from pathlib import Path

import pyomo
from pyomo.environ import SolverFactory

def _run(cmd):
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    ).stdout.strip()

def write_scip_fingerprint(path: str):
    opt = SolverFactory("scip")
    available = opt.available(False)
    exe = opt.executable() if available else None

    data = {
        "python_executable": sys.executable,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "pyomo_version": getattr(pyomo, "__version__", None),
        "conda_prefix": os.environ.get("CONDA_PREFIX"),
        "mamba_root_prefix": os.environ.get("MAMBA_ROOT_PREFIX"),
        "scip_available": available,
        "scip_executable": exe,
        "scip_version_tuple": tuple(opt.version()) if available else None,
        "scip_version_text": _run([exe, "--version"]) if exe else None,
    }

    Path(path).write_text(json.dumps(data, indent=2, sort_keys=True))

write_scip_fingerprint("runs/001/scip-fingerprint.json")
```

---

## 8.10 Run directory template

```text id="9m4owk"
runs/
  2026-05-06T120000Z_case001/
    inputs/
      data.json
      config.yaml
    model/
      model.nl
      model.row
      model.col
    solver/
      scip.log
      scip.sol
      scip-options.json
      scip-from-pyomo-options.set
      scip-all.set
      scip-diff.set
      scip-fingerprint.json
    results/
      pyomo-results-summary.json
      variable-values.csv
      objective.json
```

---

## 8.11 Result summary JSON

```python id="eqqrjx"
import json
from pathlib import Path

def write_results_summary(results, path: str):
    solver = results.solver
    problem = results.problem

    def safe(obj, name):
        return getattr(obj, name, None)

    data = {
        "solver_status": str(safe(solver, "status")),
        "termination_condition": str(safe(solver, "termination_condition")),
        "message": str(safe(solver, "message")),
        "time": safe(solver, "time"),
        "gap": safe(solver, "gap"),
        "primal_bound": safe(solver, "primal_bound"),
        "dual_bound": safe(solver, "dual_bound"),
        "problem_lower_bound": safe(problem, "lower_bound"),
        "problem_upper_bound": safe(problem, "upper_bound"),
        "n_solutions": len(results.solution),
    }

    Path(path).write_text(json.dumps(data, indent=2, sort_keys=True))

write_results_summary(res, "runs/001/results/pyomo-results-summary.json")
```

Pyomo’s SCIP parser populates `solver.time`, `solver.gap`, `solver.primal_bound`, and `solver.dual_bound` from the SCIP log when it can parse the expected final labels. ([pyomo.readthedocs.io][4])

---

## 8.12 Log-derived progress extraction

### 8.12.1 Why raw logs still matter

```text id="xg8jq7"
Pyomo parses final summary fields.
Pyomo does not expose full progress trajectory by default:
  time series of primal bound
  time series of dual bound
  time series of gap
  cut counts by round
  heuristic event times
  separator-level timing
```

### 8.12.2 Generic line scanner

```python id="n5h07b"
from pathlib import Path

def find_solver_events(log_path: str, terms: list[str]):
    out = []
    for lineno, line in enumerate(Path(log_path).read_text(errors="replace").splitlines(), 1):
        low = line.lower()
        if any(term.lower() in low for term in terms):
            out.append({"line": lineno, "text": line})
    return out

events = {
    "presolve": find_solver_events("scip.log", ["presolving", "presolved", "deleted", "fixed"]),
    "cuts": find_solver_events("scip.log", ["separator", "cut", "separation"]),
    "heuristics": find_solver_events("scip.log", ["heuristic", "solution", "incumbent"]),
    "conflicts": find_solver_events("scip.log", ["conflict"]),
}
```

### 8.12.3 Robust final field fallback

```python id="p7s3hj"
def merge_pyomo_and_log_summary(results, log_path):
    out = {
        "time": getattr(results.solver, "time", None),
        "gap": getattr(results.solver, "gap", None),
        "primal_bound": getattr(results.solver, "primal_bound", None),
        "dual_bound": getattr(results.solver, "dual_bound", None),
    }

    log_summary = parse_scip_final_summary(log_path)
    out["time"] = out["time"] if out["time"] is not None else log_summary.get("time_sec")
    out["gap"] = out["gap"] if out["gap"] is not None else log_summary.get("gap")
    out["primal_bound"] = (
        out["primal_bound"] if out["primal_bound"] is not None else log_summary.get("primal_bound")
    )
    out["dual_bound"] = (
        out["dual_bound"] if out["dual_bound"] is not None else log_summary.get("dual_bound")
    )
    out["nodes"] = log_summary.get("nodes")
    return out
```

---

## 8.13 Reproducible solve wrapper

```python id="m143oq"
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
from pyomo.environ import SolverFactory


@dataclass(frozen=True)
class ScipRunConfig:
    run_dir: str
    time_limit: float = 300.0
    rel_gap: float | None = 1e-4
    tee: bool = False
    debug: bool = True
    deterministic: bool = True


def apply_reproducibility_options(opt, cfg: ScipRunConfig):
    opt.options["limits/time"] = cfg.time_limit

    if cfg.rel_gap is not None:
        opt.options["limits/gap"] = cfg.rel_gap

    opt.options["display/verblevel"] = 4
    opt.options["display/relevantstats"] = "TRUE"
    opt.options["table/timing/active"] = "TRUE"
    opt.options["table/lp/active"] = "TRUE"
    opt.options["table/tree/active"] = "TRUE"
    opt.options["table/solution/active"] = "TRUE"

    if cfg.deterministic:
        opt.options["randomization/randomseedshift"] = 0
        opt.options["randomization/permutationseed"] = 0
        opt.options["randomization/permuteconss"] = "FALSE"
        opt.options["randomization/permutevars"] = "FALSE"
        opt.options["randomization/lpseed"] = 0
        opt.options["parallel/mode"] = 1
        opt.options["parallel/minnthreads"] = 1
        opt.options["parallel/maxnthreads"] = 1


def solve_scip_reproducibly(model, cfg: ScipRunConfig):
    run_dir = Path(cfg.run_dir)
    (run_dir / "solver").mkdir(parents=True, exist_ok=True)
    (run_dir / "results").mkdir(parents=True, exist_ok=True)

    opt = SolverFactory("scip", solver_io="nl")
    if not opt.available(False):
        raise RuntimeError("SCIP unavailable")

    apply_reproducibility_options(opt, cfg)

    write_options_manifest(opt, run_dir / "solver" / "scip-options.json")
    write_pyomo_scip_set(opt, run_dir / "solver" / "scip-from-pyomo-options.set")
    write_scip_fingerprint(run_dir / "solver" / "scip-fingerprint.json")

    res = opt.solve(
        model,
        tee=cfg.tee,
        logfile=str(run_dir / "solver" / "scip.log"),
        keepfiles=cfg.debug,
        symbolic_solver_labels=cfg.debug,
        load_solutions=False,
    )

    write_results_summary(res, run_dir / "results" / "pyomo-results-summary.json")
    return res
```

---

## 8.14 Diagnostic interpretation table

| Log artifact         | What to read                | Value case                                  |
| -------------------- | --------------------------- | ------------------------------------------- |
| final `SCIP Status`  | termination message         | classify solve result                       |
| `Solving Time (sec)` | wall-clock runtime          | SLA/performance regression                  |
| `Solving Nodes`      | search tree size            | formulation strength / branching difficulty |
| `Primal Bound`       | incumbent objective         | feasible solution quality                   |
| `Dual Bound`         | proof bound                 | proof progress                              |
| `Gap`                | proof gap                   | accept/reject incumbent                     |
| presolve lines       | reductions/fixings/upgrades | model redundancy, bound tightening          |
| separator table      | cuts and time               | cut aggressiveness tuning                   |
| heuristic table      | incumbent sources           | feasible-solution strategy                  |
| LP table             | LP iterations/time          | relaxation bottleneck                       |
| tree table           | branching/search footprint  | search behavior                             |
| conflict table       | conflict analysis           | infeasibility learning                      |

---

## 8.15 Reproducibility failure modes

| Symptom                                | Likely cause                                         | Probe                                | Fix                                         |
| -------------------------------------- | ---------------------------------------------------- | ------------------------------------ | ------------------------------------------- |
| different node counts                  | randomization, threading, presolve order, data order | compare seeds/options/logs           | set randomization/parallel controls         |
| different solution with same objective | multiple optima, randomization, order                | compare variable values/objective    | deterministic settings; tie-break objective |
| missing `gap` field                    | log parsing failed or presolve solved                | inspect raw log                      | parse log fallback; use `getattr`           |
| massive log files                      | high `display/freq`, `verblevel=5`                   | log size                             | reduce display frequency                    |
| no useful stats                        | stats disabled/low verbosity                         | `display/relevantstats`, table flags | enable table/*/active                       |
| local `scip.set` ignored               | Pyomo temporary options file                         | Pyomo warning                        | store options in `opt.options`              |
| non-reproducible CI                    | no lockfile / mixed channels                         | package list                         | conda-lock; strict conda-forge              |
| infeasibility not diagnosable          | no `.nl/.row/.col`                                   | keepfiles off                        | rerun debug profile                         |

---

## 8.16 Agent checklist

```text id="jr8uqw"
For every serious SCIP run through Pyomo:

1. Use:
   opt.solve(..., logfile="scip.log", load_solutions=False)

2. For debugging:
   keepfiles=True
   symbolic_solver_labels=True

3. For statistics:
   display/relevantstats = TRUE
   table/timing/active = TRUE
   table/lp/active = TRUE
   table/tree/active = TRUE
   table/heuristics/active = TRUE
   table/separator/active = TRUE

4. Do not use:
   display/statistics = TRUE
   unless targeting a different non-native AMPL wrapper that explicitly documents that alias.

5. Read final fields:
   SCIP Status
   Solving Time
   Solving Nodes
   Primal Bound
   Dual Bound
   Gap

6. Store:
   .nl
   .row
   .col
   .sol
   .log
   scip-options.json
   generated scip.set equivalent
   SCIP version
   Pyomo version
   environment lockfile

7. For deterministic-ish runs:
   randomization/randomseedshift = 0
   randomization/permutationseed = 0
   randomization/permuteconss = FALSE
   randomization/permutevars = FALSE
   randomization/lpseed = 0
   parallel/mode = 1
   parallel/minnthreads = parallel/maxnthreads = 1
```

---

## 8.17 Compact mental model

```text id="5ufrx9"
tee=True:
  live console stream

logfile:
  durable log artifact

keepfiles=True:
  preserve solver input/output files

symbolic_solver_labels=True:
  preserve Pyomo names in solver artifacts

SCIP statistics:
  display/relevantstats = TRUE
  table/*/active = TRUE
  shell command: display statistics

Pyomo SCIP parsing:
  final labels -> time, nodes, primal bound, dual bound, gap
  missing attributes are possible; use getattr

Reproducibility:
  pin versions
  capture scip --version
  capture scip.set / opt.options
  store .nl/.row/.col/.sol/.log
  fix randomization and parallel settings when comparing runs
```

[1]: https://pyomo.readthedocs.io/en/6.10.0/api/pyomo.contrib.solver.common.base.LegacySolverWrapper.html?utm_source=chatgpt.com "LegacySolverWrapper — Pyomo 6.10.0 documentation"
[2]: https://www.scipopt.org/doc/html/PARAMETERS.php "SCIP Doxygen Documentation: List of all SCIP parameters"
[3]: https://www.scipopt.org/doc/html/SHELL.php?utm_source=chatgpt.com "SCIP Doxygen Documentation: Tutorial: the interactive shell"
[4]: https://pyomo.readthedocs.io/en/6.8.2/_modules/pyomo/solvers/plugins/solvers/SCIPAMPL.html?utm_source=chatgpt.com "Source code for pyomo.solvers.plugins.solvers.SCIPAMPL"
[5]: https://www.scipopt.org/doc/html/PARAMETERS.php?utm_source=chatgpt.com "List of all SCIP parameters"

# 9) Presolve, propagation, heuristics, cuts, and branching — SCIP/Pyomo operational tuning

Dense technical reference for LLM programming agents. Style aligned with the uploaded advanced-doc pattern. 

---

## 9.0 Control-plane map

```text id="fu87ey"
Native SCIP C API:
  SCIPsetPresolving(scip, SCIP_PARAMSETTING_*, quiet)
  SCIPsetHeuristics(scip, SCIP_PARAMSETTING_*, quiet)
  SCIPsetSeparating(scip, SCIP_PARAMSETTING_*, quiet)
  plugin-specific parameters
  plugin priorities
  variable branch priorities
  custom branching rules / separators / heuristics / propagators

PySCIPOpt:
  model.setPresolve(SCIP_PARAMSETTING.*)
  model.setHeuristics(SCIP_PARAMSETTING.*)
  model.setSeparating(SCIP_PARAMSETTING.*)
  model.chgVarBranchPriority(var, priority)
  custom Branchrule / Heur / Sepa / Conshdlr classes

Pyomo SolverFactory("scip"):
  file-based external solve
  opt.options["slash/separated/key"] = value
  options -> temporary scip.set
  no direct SCIP callback/plugin API
  no direct Python SCIP object
```

SCIP exposes `SCIPsetHeuristics`, `SCIPsetPresolving`, and `SCIPsetSeparating` as parameter-setting methods taking `SCIP_PARAMSETTING`; PySCIPOpt exposes the analogous `setHeuristics`, `setPresolve`, and `setSeparating` calls with `SCIP_PARAMSETTING`. Pyomo’s SCIP plugin instead stringifies `opt.options`, writes them to a temporary `scip.set`, and runs the external `scip ... -AMPL` command. ([SCIP Optimization Library][1])

---

## 9.1 Meta-settings: default / fast / aggressive / off

### 9.1.1 Native C API

```c id="qsak6k"
SCIPsetPresolving(scip, SCIP_PARAMSETTING_DEFAULT, TRUE);
SCIPsetPresolving(scip, SCIP_PARAMSETTING_FAST, TRUE);
SCIPsetPresolving(scip, SCIP_PARAMSETTING_AGGRESSIVE, TRUE);
SCIPsetPresolving(scip, SCIP_PARAMSETTING_OFF, TRUE);

SCIPsetHeuristics(scip, SCIP_PARAMSETTING_DEFAULT, TRUE);
SCIPsetHeuristics(scip, SCIP_PARAMSETTING_FAST, TRUE);
SCIPsetHeuristics(scip, SCIP_PARAMSETTING_AGGRESSIVE, TRUE);
SCIPsetHeuristics(scip, SCIP_PARAMSETTING_OFF, TRUE);

SCIPsetSeparating(scip, SCIP_PARAMSETTING_DEFAULT, TRUE);
SCIPsetSeparating(scip, SCIP_PARAMSETTING_FAST, TRUE);
SCIPsetSeparating(scip, SCIP_PARAMSETTING_AGGRESSIVE, TRUE);
SCIPsetSeparating(scip, SCIP_PARAMSETTING_OFF, TRUE);
```

SCIP defines these four modes for presolving, heuristics, and separating: `DEFAULT`, `FAST`, `AGGRESSIVE`, and `OFF`; `FAST` reduces time spent in the subsystem, `AGGRESSIVE` increases effort, and `OFF` disables the subsystem. Aggressive heuristics/separators can enable sub-SCIP-based plugins regardless of `USESSUBSCIP`, which can matter inside sub-SCIPs. ([SCIP Optimization Library][1])

### 9.1.2 PySCIPOpt

```python id="58co2e"
from pyscipopt import Model, SCIP_PARAMSETTING

m = Model()

m.setPresolve(SCIP_PARAMSETTING.DEFAULT)
m.setPresolve(SCIP_PARAMSETTING.FAST)
m.setPresolve(SCIP_PARAMSETTING.AGGRESSIVE)
m.setPresolve(SCIP_PARAMSETTING.OFF)

m.setHeuristics(SCIP_PARAMSETTING.AGGRESSIVE)
m.setSeparating(SCIP_PARAMSETTING.FAST)
```

PySCIPOpt documents `SCIP_PARAMSETTING` as applicable to heuristics, presolvers, and separators through `setHeuristics`, `setPresolve`, and `setSeparating`. ([PySCIPOpt Documentation][2])

### 9.1.3 Pyomo

```text id="mhgzi7"
Pyomo cannot call:
  SCIPsetPresolving(...)
  SCIPsetHeuristics(...)
  SCIPsetSeparating(...)

Pyomo can:
  set concrete SCIP parameters:
    opt.options["presolving/maxrounds"] = ...
    opt.options["separating/maxcutsroot"] = ...
    opt.options["heuristics/rens/freq"] = ...

Recommended Pyomo workflow:
  1. tune in standalone SCIP / PySCIPOpt using meta-settings
  2. save changed settings:
       SCIP> set diffsave tuned.set
  3. port concrete key/value pairs into opt.options
```

The authoritative parameter list for the installed SCIP can be generated with `SCIP> set save <file name>`; use that installed-version list as the source of valid Pyomo option keys. ([SCIP Optimization Library][3])

---

## 9.2 Presolving

### 9.2.1 Purpose

```text id="rvasny"
Presolving goals:
  delete redundant variables/constraints
  fix variables
  tighten bounds
  aggregate variables
  multi-aggregate variables
  detect cliques
  upgrade constraints
  detect infeasibility before search
  detect implied integrality
  reduce LP/NLP size
  strengthen root relaxation
  shrink branch-and-bound tree
```

### 9.2.2 Core SCIP parameters reachable from Pyomo

```python id="7jldqo"
# master presolve controls
opt.options["presolving/maxrounds"] = -1       # -1 unlimited, 0 off
opt.options["presolving/abortfac"] = 0.0008
opt.options["presolving/maxrestarts"] = -1

# aggregation controls
opt.options["presolving/donotaggr"] = "FALSE"
opt.options["presolving/donotmultaggr"] = "FALSE"

# restart-after-root / root-fixing controls
opt.options["presolving/restartfac"] = 0.025
opt.options["presolving/immrestartfac"] = 0.05
opt.options["presolving/restartminred"] = 0.05

# implied-integrality presolver controls
opt.options["presolving/implint/maxrounds"] = 0
opt.options["presolving/implint/convertintegers"] = "FALSE"
opt.options["presolving/implint/numericslimit"] = 100000000
```

SCIP defines `presolving/maxrounds` with `-1` unlimited and `0` off, aggregation-disabling switches, restart thresholds based on integer variables fixed at the root, and an `implint` presolver with controls for implied-integrality detection. ([SCIP Optimization Library][3])

### 9.2.3 Presolving modes by intent

```text id="2y27b8"
DEFAULT:
  production baseline
  generally best first run

FAST:
  reduce presolve time
  useful for many short solves
  useful when presolve dominates runtime

AGGRESSIVE:
  higher presolve effort
  useful for large generated MILPs, GDP-transformed models, weak big-M models
  can reduce tree size but may increase front-loaded time

OFF:
  debugging only
  preserve closer raw model structure
  useful for diagnosing export/formulation issues
```

### 9.2.4 Pyomo preset: safe default

```python id="tkiuyu"
def scip_presolve_safe_default(opt):
    # Do not override SCIP defaults.
    # Add only time/gap/logging elsewhere.
    return opt
```

### 9.2.5 Pyomo preset: fast presolve

```python id="uk2t71"
def scip_presolve_fastish(opt):
    # Approximate "less presolve" behavior with explicit parameters.
    # Validate against installed SCIP's `set save` output.
    opt.options["presolving/maxrounds"] = 5
    opt.options["presolving/maxrestarts"] = 0
    return opt
```

### 9.2.6 Pyomo preset: debug infeasibility / raw export

```python id="ys2fpk"
def scip_presolve_debug_off(opt):
    opt.options["presolving/maxrounds"] = 0
    return opt

res = opt.solve(
    model,
    tee=True,
    logfile="debug-scip.log",
    keepfiles=True,
    symbolic_solver_labels=True,
    load_solutions=False,
)
```

### 9.2.7 Presolve diagnostics

```text id="swq6pn"
Read log for:
  presolving time
  variables deleted
  constraints deleted
  fixed variables
  bound changes
  upgraded constraints
  implications
  cliques
  restarts
  solved during presolve
```

```python id="eleryf"
opt.options["display/verblevel"] = 5
opt.options["display/relevantstats"] = "TRUE"
opt.options["table/presolver/active"] = "TRUE"
```

---

## 9.3 Propagation

### 9.3.1 Purpose

```text id="vqsx0d"
Propagation:
  domain tightening without full branching
  constraint-specific inference
  global/local bound tightening
  infeasibility detection
  implication propagation
  conflict-analysis support
  CP-like pruning inside CIP/MIP/MINLP search
```

### 9.3.2 Global propagation controls

```python id="x4ouzt"
opt.options["propagating/maxrounds"] = 100
opt.options["propagating/maxroundsroot"] = 1000
opt.options["propagating/abortoncutoff"] = "TRUE"
```

SCIP defines `propagating/maxrounds` and `propagating/maxroundsroot` as maximal propagation rounds per node/root; `propagating/abortoncutoff` controls whether propagation aborts immediately at cutoff, and SCIP notes setting it to `FALSE` can help conflict analysis produce more conflict constraints. ([SCIP Optimization Library][3])

### 9.3.3 Value cases

```text id="t06q9n"
High propagation value:
  binary logic
  indicator-like constraints
  cardinality constraints
  scheduling / assignment
  bound-heavy MINLP
  transformed GDP
  pseudo-Boolean structure
  tight finite variable domains

Low propagation value:
  mostly continuous LP-like model
  weak/unbounded variable domains
  huge model where propagation overhead dominates
```

### 9.3.4 Pyomo preset: stronger root propagation

```python id="m3b7zt"
def scip_propagation_root_heavy(opt):
    opt.options["propagating/maxroundsroot"] = 5000
    opt.options["propagating/maxrounds"] = 200
    return opt
```

### 9.3.5 Pyomo preset: conflict-oriented infeasibility debug

```python id="qtu8yd"
def scip_propagation_conflict_debug(opt):
    opt.options["propagating/abortoncutoff"] = "FALSE"
    opt.options["display/verblevel"] = 5
    opt.options["display/relevantstats"] = "TRUE"
    opt.options["table/conflict/active"] = "TRUE"
    opt.options["table/propagator/active"] = "TRUE"
    return opt
```

---

## 9.4 Heuristics

### 9.4.1 Purpose

```text id="9461kg"
Primal heuristics:
  find feasible incumbents
  improve primal bound
  enable pruning by cutoff
  provide usable solutions under time limits
  seed later large-neighborhood/local-search heuristics
```

### 9.4.2 Meta-settings

```text id="u3j09b"
SCIP_PARAMSETTING_DEFAULT:
  normal heuristic policy

SCIP_PARAMSETTING_FAST:
  less time spent in heuristics

SCIP_PARAMSETTING_AGGRESSIVE:
  heuristics called more aggressively

SCIP_PARAMSETTING_OFF:
  disable all heuristics
```

SCIP’s `SCIPsetHeuristics()` explicitly maps `FAST` to less heuristic time, `AGGRESSIVE` to more frequent/aggressive heuristic calls, and `OFF` to disabling heuristics. ([SCIP Optimization Library][1])

### 9.4.3 Pyomo option families

```text id="3xuq13"
heuristics/<name>/freq:
  call frequency
  -1 typically disables a heuristic
  higher positive values usually less frequent
  lower positive values usually more frequent

heuristics/<name>/maxdepth:
  depth limit

heuristics/<name>/maxnodes / nodesquot / nodesofs:
  subproblem budgets

Heuristic examples:
  rens
  rins
  alns
  localbranching
  feaspump
  proximity
  diving variants
```

### 9.4.4 Example: RENS tuning

```python id="91mg39"
opt.options["heuristics/rens/freq"] = 10
opt.options["heuristics/rens/maxnodes"] = 5000
opt.options["heuristics/rens/minfixingrate"] = 0.5
```

SCIP exposes RENS parameters such as frequency, subproblem node limits, and minimum fixing rate in its parameter list. ([SCIP Optimization Library][3])

### 9.4.5 Feasible-solution-first preset

```python id="9vrvkr"
def scip_faster_feasible_solution(opt):
    # Stop policy
    opt.options["limits/time"] = 300
    opt.options["limits/solutions"] = 1
    opt.options["limits/gap"] = 0.10

    # Keep presolve; reduce proof-heavy separation slightly
    opt.options["separating/maxroundsroot"] = 5
    opt.options["separating/maxrounds"] = 1

    # Encourage selected primal heuristics; validate keys against installed set save output
    opt.options["heuristics/rens/freq"] = 10
    opt.options["heuristics/rins/freq"] = 10
    opt.options["heuristics/alns/freq"] = 20
    opt.options["heuristics/localbranching/freq"] = 20

    opt.options["display/verblevel"] = 4
    opt.options["display/relevantstats"] = "TRUE"
    opt.options["table/heuristics/active"] = "TRUE"
    return opt
```

### 9.4.6 Heuristic diagnostics

```text id="i97j1l"
Read:
  first incumbent time
  number of incumbents
  heuristic table
  primal-bound trajectory
  final primal bound
  solution limit stops
  no-incumbent time-limit failures
```

```python id="i1fj5o"
opt.options["table/heuristics/active"] = "TRUE"
opt.options["table/solution/active"] = "TRUE"
```

### 9.4.7 Heuristic anti-patterns

```text id="29o8b7"
Do not:
  turn heuristics aggressive blindly inside sub-SCIP-heavy workflows
  increase all heuristic frequencies at once
  spend large subproblem budgets before obtaining baseline logs
  optimize proof speed and feasible-first behavior with the same preset
```

SCIP warns that aggressive heuristics can enable heuristics regardless of the `USESSUBSCIP` flag and can cause unintended recursion when applied to a sub-SCIP. ([SCIP Optimization Library][1])

---

## 9.5 Separating / cutting planes

### 9.5.1 Purpose

```text id="z05j1p"
Separation:
  inspect LP/NLP relaxation solution
  generate violated valid inequalities
  add cuts
  strengthen dual bound
  reduce integrality gap
  reduce branch-and-bound tree
```

### 9.5.2 Meta-settings

```text id="ee3in5"
SCIP_PARAMSETTING_DEFAULT:
  normal cut/separation policy

SCIP_PARAMSETTING_FAST:
  less separation effort

SCIP_PARAMSETTING_AGGRESSIVE:
  more aggressive separation

SCIP_PARAMSETTING_OFF:
  no separation
```

SCIP’s `SCIPsetSeparating()` defines the four modes and warns that aggressive separating can enable separators regardless of `USESSUBSCIP`, with potential sub-SCIP recursion implications. ([SCIP Optimization Library][1])

### 9.5.3 Global separation controls

```python id="3baxl7"
# rounds
opt.options["separating/maxroundsroot"] = -1
opt.options["separating/maxrounds"] = -1
opt.options["separating/maxstallroundsroot"] = 10
opt.options["separating/maxstallrounds"] = 1

# cut counts
opt.options["separating/maxcutsroot"] = 2000
opt.options["separating/maxcuts"] = 100
opt.options["separating/cutagelimit"] = 80
opt.options["separating/poolfreq"] = 10
```

SCIP defines root and non-root separation round limits, stall-round limits, per-round cut limits, cut age limits, and cut-pool frequency controls. ([SCIP Optimization Library][3])

### 9.5.4 Root vs tree separation

```text id="3o9ixg"
Root separation:
  before main tree exploration
  expensive cuts often worth it
  improves root dual bound
  can reduce total nodes dramatically
  controlled by maxroundsroot / maxcutsroot

Tree/local separation:
  at branch-and-bound nodes
  repeated many times
  overhead compounds
  controlled by maxrounds / maxcuts / maxstallrounds
```

### 9.5.5 Prove-optimality preset

```python id="3n4p9x"
def scip_prove_optimality(opt):
    opt.options["limits/time"] = 7200
    opt.options["limits/gap"] = 1e-6
    opt.options["limits/absgap"] = 1e-8

    # Stronger root proof effort
    opt.options["presolving/maxrounds"] = -1
    opt.options["separating/maxroundsroot"] = -1
    opt.options["separating/maxcutsroot"] = 5000
    opt.options["separating/maxstallroundsroot"] = 20

    # Moderate tree separation; avoid unbounded cut explosion
    opt.options["separating/maxrounds"] = 3
    opt.options["separating/maxcuts"] = 200

    opt.options["display/verblevel"] = 4
    opt.options["display/relevantstats"] = "TRUE"
    opt.options["table/separator/active"] = "TRUE"
    opt.options["table/lp/active"] = "TRUE"
    opt.options["table/tree/active"] = "TRUE"
    return opt
```

### 9.5.6 Cut-light / memory-light preset

```python id="jy8zz7"
def scip_cut_light_memory_reduction(opt):
    opt.options["separating/maxroundsroot"] = 3
    opt.options["separating/maxrounds"] = 0
    opt.options["separating/maxcutsroot"] = 300
    opt.options["separating/maxcuts"] = 0
    opt.options["separating/cutagelimit"] = 20
    opt.options["separating/poolfreq"] = -1
    return opt
```

`separating/maxcuts = 0` disables local separation, `separating/maxcutsroot = 0` disables root-node separation, and `separating/poolfreq = -1` disables the global cut pool separation frequency. ([SCIP Optimization Library][3])

### 9.5.7 Cut aggressiveness tradeoff

```text id="psak9w"
Aggressive cuts help when:
  root gap large
  dual bound stagnant
  LP solve time still modest
  branch-and-bound nodes exploding
  formulation weak but cuttable

Aggressive cuts hurt when:
  LP iterations explode
  root takes most runtime
  cuts age out quickly
  memory pressure rises
  primal bound already good and proof not needed
  nonlinear/MINLP relaxations become unstable
```

---

## 9.6 Branching

### 9.6.1 Purpose

```text id="9fuapt"
Branching:
  split current node into subproblems
  usually branch on fractional integer variable
  can create arbitrary children in native SCIP
  drives tree shape, dual-bound progress, and memory footprint
```

SCIP’s branching-rule documentation defines branching rules as the mechanism that splits the current node into smaller subproblems; PySCIPOpt’s branching tutorial notes that SCIP can create an arbitrary number of children and arbitrary constraints on created nodes. ([SCIP Optimization Library][4])

### 9.6.2 Branching score globals

```python id="tnhd9y"
opt.options["branching/scorefunc"] = "p"       # s=sum, p=product, q=quotient
opt.options["branching/scorefac"] = 0.167
opt.options["branching/preferbinary"] = "FALSE"
```

SCIP defines `branching/scorefunc` with choices `s`, `p`, and `q`, and `branching/preferbinary` as a boolean deciding whether branching on binary variables should be preferred. ([SCIP Optimization Library][3])

### 9.6.3 Reliability pseudo-cost branching

```text id="rbxk6n"
Reliability pseudo-cost branching:
  use historical pseudo-cost estimates when reliable
  use strong branching to initialize/refresh weak pseudo-cost estimates
  balance strong-branching accuracy vs LP iteration overhead
```

Relevant controls:

```python id="4y3762"
opt.options["branching/relpscost/priority"] = 10000
opt.options["branching/relpscost/minreliable"] = 1
opt.options["branching/relpscost/maxreliable"] = 5
opt.options["branching/relpscost/sbiterquot"] = 0.5
opt.options["branching/relpscost/sbiterofs"] = 100000
opt.options["branching/relpscost/initcand"] = 100
opt.options["branching/relpscost/inititer"] = 0
```

SCIP exposes reliability pseudo-cost controls including reliability thresholds, strong-branching LP iteration budget parameters, number of initialized candidates, and pseudo-cost score weights. ([SCIP Optimization Library][3])

### 9.6.4 Pseudo-cost branching

```python id="ajrh8d"
opt.options["branching/pscost/priority"] = 2000
opt.options["branching/pscost/strategy"] = "u"
opt.options["branching/pscost/nchildren"] = 2
opt.options["branching/pscost/discountfactor"] = 0.2
```

SCIP exposes pseudo-cost branching priority, strategy, number of children for n-ary branching, and a discount factor for ancestral pseudo-costs. ([SCIP Optimization Library][3])

### 9.6.5 Full strong branching

```python id="337tv8"
opt.options["branching/vanillafullstrong/priority"] = -2000
opt.options["branching/vanillafullstrong/maxdepth"] = -1
opt.options["branching/vanillafullstrong/integralcands"] = "FALSE"
opt.options["branching/vanillafullstrong/idempotent"] = "FALSE"
```

SCIP exposes a `vanillafullstrong` branching rule with priority, max-depth, whether to consider integral candidates, and side-effect/idempotency controls. ([SCIP Optimization Library][3])

### 9.6.6 Variable priorities

PySCIPOpt route:

```python id="c4otow"
from pyscipopt import Model

m = Model()
x = m.addVar(vtype="B", name="x")
y = m.addVar(vtype="B", name="y")

m.chgVarBranchPriority(x, 100)
m.chgVarBranchPriority(y, 10)
```

PySCIPOpt’s `chgVarBranchPriority(var, priority)` sets the variable’s branch priority; variables with higher branch priority are always preferred to variables with lower priority in branching-variable selection. ([PySCIPOpt Documentation][5])

Pyomo route:

```text id="vm1516"
Pyomo SolverFactory("scip"):
  no robust documented SCIP-native variable-priority API through the file-based SCIPAMPL interface.
  NL suffix experiments may be solver/version dependent.
  Use PySCIPOpt/native SCIP for reliable variable branch-priority control.
```

### 9.6.7 Branching tuning advisory

```text id="iwi7sy"
Do not tune branching first.

Order:
  1. fix formulation strength
  2. add finite bounds
  3. scale coefficients
  4. inspect presolve/root gap
  5. inspect incumbent timing
  6. tune separation/heuristics
  7. tune branching

Branching tuning value:
  difficult MILP/MINLP search tree
  wrong variables consistently branched early
  domain-specific high-priority strategic binaries
  proof time dominated by node count
```

---

## 9.7 Safe parameter presets for Pyomo

### 9.7.1 Base safe preset

```python id="8z744c"
def scip_preset_safe(opt):
    opt.options["limits/time"] = 1800
    opt.options["limits/gap"] = 1e-4
    opt.options["display/verblevel"] = 4
    opt.options["display/relevantstats"] = "TRUE"
    opt.options["table/timing/active"] = "TRUE"
    opt.options["table/tree/active"] = "TRUE"
    opt.options["table/lp/active"] = "TRUE"
    opt.options["table/solution/active"] = "TRUE"
    return opt
```

Use when:

```text id="e4go8t"
unknown model
first production run
need predictable behavior
avoid overfitting solver parameters
```

### 9.7.2 Faster feasible solution

```python id="srr89i"
def scip_preset_faster_feasible(opt):
    opt.options["limits/time"] = 300
    opt.options["limits/solutions"] = 1
    opt.options["limits/gap"] = 0.05

    # keep presolve, reduce proof-heavy tree cut effort
    opt.options["presolving/maxrounds"] = -1
    opt.options["separating/maxroundsroot"] = 5
    opt.options["separating/maxrounds"] = 1

    # heuristic nudges: validate names for installed SCIP
    opt.options["heuristics/rens/freq"] = 10
    opt.options["heuristics/rins/freq"] = 10
    opt.options["heuristics/alns/freq"] = 20

    opt.options["display/relevantstats"] = "TRUE"
    opt.options["table/heuristics/active"] = "TRUE"
    return opt
```

Use when:

```text id="b7bb9b"
planning / scheduling incumbent needed quickly
feasibility > proof
time-limited decision support
warm-start / candidate generation
```

Reject when:

```text id="4whss2"
regulatory proof
published optimal objective
needs proven gap below strict tolerance
```

### 9.7.3 Prove optimality

```python id="hccxrd"
def scip_preset_prove_optimality(opt):
    opt.options["limits/time"] = 7200
    opt.options["limits/gap"] = 1e-6
    opt.options["limits/absgap"] = 1e-8

    # presolve and root cut proof effort
    opt.options["presolving/maxrounds"] = -1
    opt.options["separating/maxroundsroot"] = -1
    opt.options["separating/maxcutsroot"] = 5000
    opt.options["separating/maxstallroundsroot"] = 20

    # controlled tree effort
    opt.options["separating/maxrounds"] = 3
    opt.options["separating/maxcuts"] = 200

    opt.options["display/relevantstats"] = "TRUE"
    opt.options["table/presolver/active"] = "TRUE"
    opt.options["table/separator/active"] = "TRUE"
    opt.options["table/lp/active"] = "TRUE"
    opt.options["table/tree/active"] = "TRUE"
    return opt
```

Use when:

```text id="4lvoui"
gap must close
dual bound progress poor
root gap large
proof dominates deliverable
```

Watch:

```text id="3relys"
root time
LP iterations
cut count
memory
dual-bound movement per cut round
```

### 9.7.4 Debug infeasibility

```python id="hcm7ef"
def scip_preset_debug_infeasibility(opt):
    opt.options["limits/time"] = 600

    # preserve model mapping; reduce presolve transformation if needed
    opt.options["presolving/maxrounds"] = 0

    # conflict-oriented propagation behavior
    opt.options["propagating/abortoncutoff"] = "FALSE"

    # diagnostics
    opt.options["display/verblevel"] = 5
    opt.options["display/allviols"] = "TRUE"
    opt.options["display/relevantstats"] = "TRUE"
    opt.options["table/conflict/active"] = "TRUE"
    opt.options["table/constraint/active"] = "TRUE"
    opt.options["table/propagator/active"] = "TRUE"
    return opt

res = opt.solve(
    model,
    tee=True,
    logfile="debug-infeasible.log",
    keepfiles=True,
    symbolic_solver_labels=True,
    load_solutions=False,
)
```

Use when:

```text id="8z3kce"
solver says infeasible
need map row/variable to Pyomo components
presolve hides original structure
conflict/propagator stats needed
```

### 9.7.5 Reduce memory

```python id="fnb725"
def scip_preset_reduce_memory(opt):
    opt.options["limits/memory"] = 8192

    # reduce cut accumulation and local separation
    opt.options["separating/maxroundsroot"] = 3
    opt.options["separating/maxrounds"] = 0
    opt.options["separating/maxcutsroot"] = 300
    opt.options["separating/maxcuts"] = 0
    opt.options["separating/cutagelimit"] = 20
    opt.options["separating/poolfreq"] = -1

    # reduce restart/presolve churn if memory pressure appears there
    opt.options["presolving/maxrestarts"] = 0

    # reduce verbosity/log size
    opt.options["display/verblevel"] = 3
    opt.options["display/freq"] = 1000
    return opt
```

Use when:

```text id="b85cl9"
memory limit reached
large cut pool
huge LP rows
many root cuts
HPC memory quotas
container memory cap
```

Tradeoff:

```text id="cll5if"
Less memory may mean:
  weaker relaxation
  more nodes
  worse proof time
  fewer primal improvements
```

---

## 9.8 Pyomo wrapper: profile selection

```python id="x0fzjl"
from pyomo.environ import SolverFactory
from pyomo.opt import SolverStatus, TerminationCondition

SCIP_PRESETS = {
    "safe": scip_preset_safe,
    "faster_feasible": scip_preset_faster_feasible,
    "prove_optimality": scip_preset_prove_optimality,
    "debug_infeasibility": scip_preset_debug_infeasibility,
    "reduce_memory": scip_preset_reduce_memory,
}

def make_scip_solver(profile="safe"):
    opt = SolverFactory("scip", solver_io="nl")
    if not opt.available(False):
        raise RuntimeError("SCIP unavailable to Pyomo")

    try:
        SCIP_PRESETS[profile](opt)
    except KeyError:
        raise ValueError(f"Unknown SCIP profile: {profile!r}")

    return opt

def solve_with_scip_profile(model, profile="safe", *, debug=False):
    opt = make_scip_solver(profile)

    res = opt.solve(
        model,
        tee=True,
        logfile=f"scip-{profile}.log",
        keepfiles=debug,
        symbolic_solver_labels=debug,
        load_solutions=False,
    )

    tc = res.solver.termination_condition
    if tc == TerminationCondition.optimal:
        model.solutions.load_from(res)
    elif profile == "faster_feasible" and len(res.solution) > 0:
        model.solutions.load_from(res)
    elif profile == "prove_optimality":
        raise RuntimeError(f"Expected proof, got {res.solver.status=} {tc=}")
    return res
```

---

## 9.9 Diagnostics-to-action matrix

| Symptom                    | Likely subsystem              | First checks                          | Candidate action                                                            |
| -------------------------- | ----------------------------- | ------------------------------------- | --------------------------------------------------------------------------- |
| no feasible solution found | heuristics / formulation      | incumbent time, heuristic table       | feasible-first preset, tighter bounds, seed/fix partial solution            |
| large root gap             | presolve / cuts / formulation | root bound, separator table           | stronger root separation, improve formulation, reduce big-M                 |
| many nodes, slow proof     | branching / cuts              | nodes, LP time, dual-bound trajectory | stronger root cuts, inspect branching priorities, formulation strengthening |
| root takes too long        | presolve / separation         | presolve time, root LP/cuts           | fast presolve, cut-light, lower maxcutsroot                                 |
| memory limit reached       | cuts / LP rows / tree         | memory log, cut count, node count     | reduce cuts, cut pool, separation, memory limit                             |
| infeasible after presolve  | formulation / data            | keepfiles, labels, presolve-off rerun | debug infeasibility preset                                                  |
| LP iteration explosion     | separating / numerics         | LP table, cut counts                  | reduce cuts, scale model, inspect coefficients                              |
| strong branching expensive | branching                     | LP time, relpscost sb params          | reduce `relpscost` strong-branching budgets                                 |
| poor binary branching      | branching                     | search tree, variable roles           | native PySCIPOpt branch priorities or custom branching                      |

---

## 9.10 Agent tuning order

```text id="p56tq7"
1. Classify model:
   MILP / MIQP / MINLP / GDP-transformed / piecewise / SOS

2. Validate formulation:
   finite bounds
   tight big-M
   scaling
   binary/integer domains
   no accidental nonlinear terms

3. Run safe baseline:
   logs + statistics + gap/bounds/nodes

4. Choose objective:
   faster feasible solution
   prove optimality
   debug infeasibility
   reduce memory

5. Tune one subsystem at a time:
   presolve
   propagation
   heuristics
   separating
   branching

6. Compare:
   time
   nodes
   primal bound
   dual bound
   gap
   memory
   first incumbent time
   root time
   LP iterations

7. Archive:
   model.nl
   model.row/.col
   scip.log
   opt.options JSON
   installed SCIP `set save` output
```

---

## 9.11 Compact mental model

```text id="s4t9ra"
Presolve:
  shrink and strengthen model before tree search
  Pyomo knobs: presolving/*

Propagation:
  domain tightening during presolve/search
  Pyomo knobs: propagating/*

Heuristics:
  find incumbents
  Pyomo knobs: heuristics/<name>/*

Separating:
  generate cuts, improve dual bound
  Pyomo knobs: separating/* and separator-specific keys

Branching:
  choose search splits
  Pyomo knobs: branching/*
  robust variable priorities/custom rules require PySCIPOpt/native SCIP

Native meta-modes:
  DEFAULT / FAST / AGGRESSIVE / OFF

Pyomo reality:
  no direct meta-mode call
  use concrete parameters
  generate installed-version parameter files with SCIP set save/diffsave
```

[1]: https://www.scipopt.org/doc/html/group__ParameterMethods.php "SCIP Doxygen Documentation: Parameter"
[2]: https://pyscipopt.readthedocs.io/en/latest/tutorials/model.html "Introduction (Model Object, Solution Information, Parameter Settings) — PySCIPOpt  documentation"
[3]: https://www.scipopt.org/doc/html/PARAMETERS.php "SCIP Doxygen Documentation: List of all SCIP parameters"
[4]: https://www.scipopt.org/doc/html/BRANCH.php "SCIP Doxygen Documentation: How to add branching rules"
[5]: https://pyscipopt.readthedocs.io/en/stable/api/model.html "Model API — PySCIPOpt  documentation"

# 10) Constraint handlers and native SCIP expressiveness — Pyomo-facing plugin boundary

Dense technical reference for LLM programming agents. Style aligned with the uploaded advanced-doc pattern. 

---

## 10.0 Native SCIP expressiveness map

```text id="oc6hci"
SCIP native architecture:
  plugin-extensible branch-cut-and-price / CIP framework
  C-callable library
  C++ wrapper classes for user plugins
  standalone executable
  Python interface through PySCIPOpt

Pyomo SolverFactory("scip"):
  file-based external process interface
  Pyomo model -> .nl -> scip -AMPL -> .sol
  no in-process SCIP object
  no callback/plugin registration surface
  access native behavior indirectly:
    model formulation
    SCIP parameters through opt.options
    exported files/logs
```

SCIP explicitly describes itself as a MIP/MINLP solver and a framework for constraint integer programming and branch-cut-and-price, with “total control of the solution process” and “detailed information down to the guts of the solver”; its feature list names constraint handlers, variable pricers, propagators, separators, relaxators, Benders plugins, heuristics, node selectors, branching rules, presolvers, file readers, and event handlers. ([SCIP Optimization Library][1])

Pyomo’s SCIP interface is `SCIPAMPL`, a `SystemCallSolver`; it registers as `SolverFactory("scip")`, uses only `ProblemFormat.nl`, and expects `ResultsFormat.sol`, confirming the external-file interface boundary. ([Pyomo Documentation][2])

---

## 10.1 SCIP plugin categories: native capability table

| Native SCIP category          | Native role                                    | Value case                                                               | Pyomo `SolverFactory("scip")` access                               | Correct advanced route                        |
| ----------------------------- | ---------------------------------------------- | ------------------------------------------------------------------------ | ------------------------------------------------------------------ | --------------------------------------------- |
| constraint handlers           | implement/enforce arbitrary constraint classes | lazy constraints, custom combinatorial constraints, semantic propagation | indirect via algebraic formulation; no custom handler registration | PySCIPOpt `Conshdlr` or C/C++                 |
| variable pricers              | dynamically create variables/columns           | column generation, branch-price                                          | no dynamic variable generation through static `.nl`                | SCIP/GCG/PySCIPOpt/native pricer              |
| domain propagators            | constraint-independent domain tightening       | bound tightening, CP-like inference                                      | indirect via formulation + parameters                              | native propagator or constraint handler       |
| separators                    | generate cutting planes                        | stronger dual bounds                                                     | tune built-in separators via parameters                            | PySCIPOpt separator or C/C++                  |
| cut selectors                 | select/filter generated cuts                   | cut quality/memory tradeoff                                              | parameter-only, no custom selector                                 | PySCIPOpt/C                                   |
| relaxators                    | provide custom relaxations/dual bounds         | SDP/Lagrangian/custom relaxation                                         | not exposed                                                        | C/C++ plugin path                             |
| Benders plugins               | decomposition master/subproblem framework      | structured decomposition                                                 | not directly exposed                                               | SCIP native / PySCIPOpt where supported / GCG |
| primal heuristics             | find feasible incumbents                       | feasible-first, repair, diving, LNS                                      | tune built-ins via parameters                                      | PySCIPOpt heuristic or C/C++                  |
| node selectors                | choose open node                               | search strategy                                                          | tune built-ins only                                                | PySCIPOpt/C                                   |
| branching rules               | choose branching disjunction                   | search-tree control                                                      | tune built-ins; no reliable custom rule                            | PySCIPOpt/C                                   |
| presolvers                    | model reductions before solve                  | shrink/strengthen model                                                  | tune built-ins via parameters                                      | C/C++ for custom presolver                    |
| file readers                  | parse model formats                            | custom file ingestion                                                    | Pyomo writes `.nl`; no custom reader                               | standalone SCIP/native                        |
| event handlers                | react to solve events                          | monitoring, callbacks, incumbents, bound changes                         | no callback surface                                                | PySCIPOpt/C                                   |
| display/table/dialog handlers | custom UI/statistics/shell behavior            | custom logs/tables/shell commands                                        | use log/table parameters only                                      | C/C++                                         |

SCIP’s plugin-management documentation lists modules for Benders decomposition, Benders cuts, branching rules, conflict analysis, constraint handlers, cut selectors, dialogs, displays, event handlers, expression handlers, heuristics, IIS finders, node selectors, nonlinear handlers, presolvers, pricers, propagators, readers, relaxation handlers, separators, tables, concurrent solver types, and NLP solver interfaces. ([SCIP Optimization Library][3])

---

## 10.2 Constraint handlers

### 10.2.1 Native role

```text id="77idp4"
Constraint handler:
  owns semantic meaning of a constraint class
  checks feasibility of candidate solutions
  enforces violated constraints
  propagates variable domains
  separates cuts where applicable
  locks variables
  participates in presolve
  supports lazy-constraint-like behavior
```

SCIP’s feature list says constraint handlers implement arbitrary constraints; PySCIPOpt’s lazy-constraint tutorial states SCIP has no separate lazy-constraint plug-in because the broad constraint-handler concept naturally encompasses lazy constraints. ([SCIP Optimization Library][1])

### 10.2.2 Pyomo-facing implication

```text id="31vkum"
Pyomo path:
  cannot register a SCIP constraint handler
  cannot run custom separation/enforcement callback
  can only export algebraic constraints to .nl
  can sometimes model the same semantics through:
    linearization
    GDP transformation
    SOS
    Piecewise
    explicit finite constraint pool
    user-generated cut loop outside solver
```

### 10.2.3 Pyomo alternative: static formulation

```python id="8k60p5"
# Example: model all constraints explicitly when count is manageable
m.subtour = Constraint(m.S, rule=subtour_rule)
```

### 10.2.4 Pyomo alternative: external cut loop

```python id="vemk4i"
while True:
    res = opt.solve(m, load_solutions=False)
    if len(res.solution) == 0:
        raise RuntimeError("No incumbent")

    m.solutions.load_from(res)
    violated = find_violated_constraints_from_solution(m)

    if not violated:
        break

    for k, expr in enumerate(violated, start=len(m.lazy_cuts) + 1):
        m.lazy_cuts.add(expr)
```

This is not native lazy enforcement; it is a solve–inspect–augment loop. Use only when the number of outer iterations is acceptable.

### 10.2.5 PySCIPOpt route: lazy constraints via handler

```python id="rlepd0"
from pyscipopt import Model, Conshdlr, SCIP_RESULT

class MyLazyConshdlr(Conshdlr):
    def conscheck(self, constraints, solution, checkintegrality, checklprows, printreason, completely):
        if solution_is_feasible(solution):
            return {"result": SCIP_RESULT.FEASIBLE}
        return {"result": SCIP_RESULT.INFEASIBLE}

    def consenfolp(self, constraints, nusefulconss, solinfeasible):
        cuts_added = add_violated_constraints(self.model)
        return {"result": SCIP_RESULT.CONSADDED if cuts_added else SCIP_RESULT.FEASIBLE}

m = Model()
handler = MyLazyConshdlr()
m.includeConshdlr(
    handler,
    "my_lazy_handler",
    "custom lazy constraint handler",
    enfopriority=1,
    chckpriority=1,
    needscons=False,
)
```

PySCIPOpt’s lazy-constraint tutorial imports `Conshdlr` and explains that a constraint handler for lazy constraints must determine whether a solution is feasible and add something to forbid infeasible solutions. ([PySCIPOpt Documentation][4])

---

## 10.3 Variable pricers

### 10.3.1 Native role

```text id="snl7zb"
Variable pricer:
  dynamically create variables during optimization
  solve pricing subproblem
  add negative reduced-cost columns
  enables column generation
  enables branch-and-price / branch-cut-and-price
```

SCIP’s feature list describes variable pricers as plugins that dynamically create problem variables, and SCIP as a branch-cut-and-price framework. ([SCIP Optimization Library][1])

### 10.3.2 Pyomo-facing implication

```text id="o1wwcm"
Pyomo .nl path:
  static model snapshot
  all variables must exist before export
  no pricing callback
  no dynamic variable creation inside SCIP search
```

### 10.3.3 Pyomo workaround

```text id="ghu4z7"
If column count is moderate:
  generate all columns in Pyomo

If columns are huge/implicit:
  implement external column-generation master loop
  or use native SCIP/GCG/PySCIPOpt route
```

External master loop sketch:

```python id="9g8nco"
while True:
    res = opt.solve(master, load_solutions=False)
    master.solutions.load_from(res)

    new_cols = solve_pricing_problem(master)

    if not new_cols:
        break

    add_columns_to_pyomo_master(master, new_cols)
```

### 10.3.4 Correct advanced route

```text id="4q35dk"
Use:
  GCG for generic branch-cut-and-price
  SCIP native pricer plugin for custom pricing
  PySCIPOpt only if required pricer/plugin surface is sufficient for your SCIP/PySCIPOpt version
```

---

## 10.4 Domain propagators

### 10.4.1 Native role

```text id="bblxfj"
Domain propagator:
  tighten variable bounds independent of a single constraint handler
  infer fixings
  detect infeasibility
  run in presolve and/or search
  strengthen CP-like reasoning
```

SCIP’s feature list defines domain propagators as plugins that apply constraint-independent propagations on variable domains. ([SCIP Optimization Library][1])

### 10.4.2 Pyomo-facing implication

```text id="e0ijkc"
Pyomo can:
  provide tight variable bounds
  write explicit implied constraints
  tune built-in propagation parameters
  inspect propagation statistics

Pyomo cannot:
  register a custom propagator
  inspect each propagation callback
  inject dynamic propagation logic during search
```

### 10.4.3 Pyomo tuning

```python id="dtb634"
opt.options["propagating/maxroundsroot"] = 1000
opt.options["propagating/maxrounds"] = 100
opt.options["propagating/abortoncutoff"] = "FALSE"

opt.options["display/relevantstats"] = "TRUE"
opt.options["table/propagator/active"] = "TRUE"
```

### 10.4.4 Modeling alternative

```python id="vey991"
# Add explicit domain-tightening constraints when known
m.tight_bound = Constraint(m.I, rule=lambda m, i: m.x[i] <= derived_upper_bound[i])
```

---

## 10.5 Separators and cut selectors

### 10.5.1 Native separator role

```text id="w88ra3"
Separator:
  inspect LP relaxation
  identify violated valid inequalities
  add cutting planes
  improve dual bound
  reduce search tree
```

SCIP’s feature list defines separators as cutting-plane plugins based on the LP relaxation and notes dynamic cut-pool management. ([SCIP Optimization Library][1])

### 10.5.2 Native cut selector role

```text id="kut0p7"
Cut selector:
  rank/filter generated cuts
  control cut quality vs LP size
  manage cut parallelism, efficacy, support, numerical safety
```

SCIP’s plugin-management docs list cut selector plugins as a plugin-management module. ([SCIP Optimization Library][3])

### 10.5.3 Pyomo-facing implication

```text id="cpfsb6"
Pyomo can:
  tune global separation effort
  tune built-in separator parameters
  provide stronger formulations so separators work better

Pyomo cannot:
  implement a custom separator
  inspect every LP solution and add SCIP-local cuts
  implement custom cut selector
```

### 10.5.4 Pyomo tuning

```python id="ah2e4x"
opt.options["separating/maxroundsroot"] = -1
opt.options["separating/maxcutsroot"] = 2000
opt.options["separating/maxrounds"] = 3
opt.options["separating/maxcuts"] = 200

opt.options["display/relevantstats"] = "TRUE"
opt.options["table/separator/active"] = "TRUE"
opt.options["table/cutsel/active"] = "TRUE"
```

### 10.5.5 Correct advanced route

```text id="799sef"
Need custom cut generation:
  PySCIPOpt Separator tutorial path
  or native C/C++ separator plugin

Need custom cut filtering:
  PySCIPOpt Cut Selector path if supported
  or native C/C++ cut selector
```

PySCIPOpt’s documentation index includes tutorials for “Cut Selector” and “Separator (Cutting Planes),” reflecting Python-level extension paths beyond Pyomo’s file-based interface. ([PySCIPOpt Documentation][5])

---

## 10.6 Relaxators

### 10.6.1 Native role

```text id="cm7957"
Relaxator:
  provide a relaxation beyond/in addition to LP relaxation
  compute dual bounds
  run interleaved or parallel with LP-based processing
  examples:
    Lagrangian relaxation
    semidefinite relaxation
    custom combinatorial relaxation
```

SCIP’s feature list says relaxators can provide relaxations such as semidefinite or Lagrangian relaxations and dual bounds in addition to the LP relaxation, working in parallel or interleaved. ([SCIP Optimization Library][1])

### 10.6.2 Pyomo-facing implication

```text id="t5ujxn"
Pyomo can:
  reformulate model manually
  add valid inequalities
  solve relaxation as a separate Pyomo model
  compare relaxation bounds externally

Pyomo cannot:
  register a SCIP relaxator plugin
  inject custom dual-bound routines into SCIP search
```

### 10.6.3 Pyomo workaround pattern

```python id="b9kknz"
# Solve relaxation separately
relaxed = build_relaxed_pyomo_model(data)
relaxed_res = SolverFactory("scip").solve(relaxed)

# Use relaxation insight to add cuts/bounds to main model
main = build_main_pyomo_model(data)
add_relaxation_derived_valid_inequalities(main, relaxed)
main_res = SolverFactory("scip").solve(main)
```

---

## 10.7 Benders plugins

### 10.7.1 Native role

```text id="6l5s7u"
Benders plugin:
  define decomposition
  manage master problem
  manage subproblems
  generate Benders cuts
  iterate master/subproblem solve process
```

SCIP’s feature list names plugins for Benders’ decomposition and Benders’ cuts; the plugin-management API also has modules for Benders decomposition and Benders decomposition cuts. ([SCIP Optimization Library][1])

### 10.7.2 Pyomo-facing implication

```text id="8pp9oo"
Pyomo SolverFactory("scip"):
  no direct Benders plugin registration
  no master/subproblem callback API inside SCIP
```

### 10.7.3 Pyomo alternative: outer decomposition loop

```python id="ifc0lw"
while True:
    master_res = opt.solve(master, load_solutions=False)
    master.solutions.load_from(master_res)

    subproblem_results = solve_subproblems(master)

    if all_subproblems_ok(subproblem_results):
        break

    add_benders_cuts(master, subproblem_results)
```

### 10.7.4 Correct advanced route

```text id="bdxdqy"
Use native SCIP/GCG/PySCIPOpt route when:
  cuts depend on SCIP internal state
  subproblem callbacks must run inside search
  decomposition must interact with branching
  branch-cut-and-price/decomposition research code is required
```

---

## 10.8 Primal heuristics

### 10.8.1 Native role

```text id="56qxtt"
Primal heuristic:
  construct feasible solutions
  repair infeasible candidates
  dive/probe/neighborhood-search
  improve incumbent
  reduce primal bound early
```

SCIP’s feature list describes primal heuristics as plugins to search for feasible solutions, including support for probing and diving. ([SCIP Optimization Library][1])

### 10.8.2 Pyomo-facing implication

```text id="nnuk46"
Pyomo can:
  tune built-in heuristics
  provide initial values in model variables where supported by writer/solver path
  run external incumbent-generation models/scripts
  add constraints to favor known feasible structures

Pyomo cannot:
  register a custom SCIP heuristic
  call into search tree to propose incumbents dynamically
```

### 10.8.3 Pyomo tuning

```python id="pv8r5m"
opt.options["heuristics/rens/freq"] = 10
opt.options["heuristics/rins/freq"] = 10
opt.options["heuristics/alns/freq"] = 20
opt.options["limits/solutions"] = 1

opt.options["display/relevantstats"] = "TRUE"
opt.options["table/heuristics/active"] = "TRUE"
```

### 10.8.4 Correct advanced route

```text id="fi4xaj"
Need domain-specific incumbent construction:
  PySCIPOpt Heur tutorial path
  native SCIP primal heuristic plugin
```

PySCIPOpt’s documentation index includes a “Heuristics” tutorial. ([PySCIPOpt Documentation][5])

---

## 10.9 Node selectors

### 10.9.1 Native role

```text id="nv2xqg"
Node selector:
  choose next open node
  shape tree traversal
  trade best-bound vs depth-first vs hybrid search
  affects memory, incumbent discovery, proof trajectory
```

SCIP’s feature list says node selectors guide the search; the plugin-management API lists node selector plugin management. ([SCIP Optimization Library][1])

### 10.9.2 Pyomo-facing implication

```text id="lrg8x9"
Pyomo can:
  tune built-in node selector parameters if known
  alter formulation to affect tree behavior
  set priorities only via solver-supported exported mechanisms, not robustly through SCIPAMPL

Pyomo cannot:
  implement a custom node selector
```

### 10.9.3 Correct advanced route

```text id="gd5a9n"
Need custom search strategy:
  PySCIPOpt Node Selector tutorial path
  native SCIP node selector plugin
```

PySCIPOpt’s documentation index includes a “Node Selector” tutorial and node API. ([PySCIPOpt Documentation][5])

---

## 10.10 Branching rules

### 10.10.1 Native role

```text id="7pb3i4"
Branching rule:
  choose branching variable/disjunction
  create child nodes
  may create arbitrary number of children
  may add arbitrary local constraints/bounds
  controls tree structure
```

SCIP’s feature list describes branching rules as splitting the problem into subproblems, with arbitrarily many children per node and arbitrarily defined children. ([SCIP Optimization Library][1])

### 10.10.2 Pyomo-facing implication

```text id="uo7lgr"
Pyomo can:
  tune built-in branching parameters
  reformulate to expose better branching variables
  sometimes use solver-supported suffixes only if documented and tested

Pyomo cannot:
  implement custom branching rule
  inspect candidate branching variables in callback
  create custom child nodes
```

### 10.10.3 Pyomo tuning

```python id="d8frik"
opt.options["branching/preferbinary"] = "TRUE"
opt.options["branching/scorefunc"] = "p"
opt.options["branching/relpscost/minreliable"] = 1
opt.options["branching/relpscost/maxreliable"] = 5
```

### 10.10.4 PySCIPOpt route

```python id="s8z419"
from pyscipopt import Branchrule, SCIP_RESULT

class MyBranchRule(Branchrule):
    def branchexeclp(self, allowaddcons):
        # inspect LP solution, choose variable/disjunction, create branches
        return {"result": SCIP_RESULT.BRANCHED}
```

PySCIPOpt’s documentation index includes tutorials for branching rules, node API, variables, rows, columns, and model APIs, which are the relevant Python-level surfaces for branch-rule work. ([PySCIPOpt Documentation][5])

---

## 10.11 Presolvers

### 10.11.1 Native role

```text id="thvfbm"
Presolver:
  simplify model before solving
  delete variables/constraints
  aggregate variables
  tighten bounds
  upgrade constraints
  detect infeasibility
  detect implied integrality
```

SCIP’s feature list says presolvers simplify the solved problem; plugin-management docs list presolver plugins. ([SCIP Optimization Library][1])

### 10.11.2 Pyomo-facing implication

```text id="rtb6sz"
Pyomo can:
  tune built-in presolving parameters
  transform/simplify model before export
  add preprocessing in Python model-build stage

Pyomo cannot:
  register native SCIP presolver
```

### 10.11.3 Pyomo-side preprocessing

```python id="cealvq"
def preprocess_pyomo_model(m):
    # remove deactivated blocks/constraints
    # compute tighter bounds
    # eliminate fixed variables where safe
    # add implied constraints
    return m
```

### 10.11.4 Native route

```text id="gv87ha"
Need custom presolve reductions:
  C/C++ SCIP presolver plugin
  PySCIPOpt only if required presolver plugin surface exists in target version
```

---

## 10.12 File readers

### 10.12.1 Native role

```text id="gdatxz"
File reader:
  parse input format
  create SCIP problem
  write/export problem/solution formats
```

SCIP’s feature list says file readers parse different input file formats, and SCIP can be used standalone to solve files in formats such as MPS, LP, FlatZinc, CNF, OPB, WBO, PIP, and others. ([SCIP Optimization Library][1])

### 10.12.2 Pyomo-facing implication

```text id="qqgvxq"
Pyomo path:
  Pyomo writer determines exported format
  SCIPAMPL uses .nl
  native SCIP reader choice is mostly irrelevant unless running standalone SCIP
```

### 10.12.3 Native route

```bash id="74d3p9"
scip model.lp
scip model.mps
scip model.opb
scip model.wbo
```

### 10.12.4 Pyomo debug export

```python id="y3hhry"
model.write(
    "debug_model.nl",
    format="nl",
    io_options={"symbolic_solver_labels": True},
)
```

---

## 10.13 Event handlers

### 10.13.1 Native role

```text id="uuz6kg"
Event handler:
  subscribe to solve events
  react when:
    node solved
    variable bound changes
    new primal solution found
    LP solved
    incumbent changes
    best bound changes
```

SCIP’s feature list says event handlers can be informed on specific events, such as after a node is solved, when a variable changes bounds, or when a new primal solution is found. ([SCIP Optimization Library][1])

### 10.13.2 Pyomo-facing implication

```text id="vb9gan"
Pyomo can:
  inspect final results
  parse logs
  run multiple solves
  monitor external process output coarsely

Pyomo cannot:
  catch SCIP events during search
  inject Python logic when a new incumbent appears
  terminate dynamically based on custom event state except through solver limits
```

### 10.13.3 PySCIPOpt route

```python id="cpxpd0"
from pyscipopt import Eventhdlr

class IncumbentLogger(Eventhdlr):
    def eventexec(self, event):
        # read event, query model, log incumbent/bounds
        pass
```

PySCIPOpt’s documentation index includes an “Event Handlers” tutorial and event API. ([PySCIPOpt Documentation][5])

---

## 10.14 Display, table, and dialog handlers

### 10.14.1 Native role

```text id="z6frrl"
Display handler:
  progress columns / solver display

Table handler:
  final statistics table

Dialog handler:
  interactive shell commands and UI behavior
```

SCIP plugin-management docs list dialogs, displays, and tables as plugin-management modules. ([SCIP Optimization Library][3])

### 10.14.2 Pyomo-facing implication

```text id="syscga"
Pyomo can:
  set display parameters
  activate/deactivate statistics tables
  capture logfile
  parse output externally

Pyomo cannot:
  define new SCIP display columns
  define new statistics table plugin
  define new shell dialog command
```

### 10.14.3 Pyomo logging/statistics tuning

```python id="ff7z1f"
opt.options["display/verblevel"] = 5
opt.options["display/freq"] = 10
opt.options["display/relevantstats"] = "TRUE"

opt.options["table/timing/active"] = "TRUE"
opt.options["table/lp/active"] = "TRUE"
opt.options["table/tree/active"] = "TRUE"
opt.options["table/heuristics/active"] = "TRUE"
opt.options["table/separator/active"] = "TRUE"
```

---

## 10.15 C/C++ plugin inclusion mental model

### 10.15.1 C API separation

```text id="r6dipi"
SCIP C API:
  Core API:
    plugin-independent functions from scip.h
  Plugin API:
    methods provided by default plugins from scipdefplugins.h
```

SCIP’s C-API documentation states the public API is separated into a Core API accessible via `scip.h` and a Plugin API provided by default plugins via `scipdefplugins.h`. ([SCIP Optimization Library][6])

### 10.15.2 Native skeleton

```c id="6jnfu3"
#include "scip/scip.h"
#include "scip/scipdefplugins.h"

int main(int argc, char** argv)
{
    SCIP* scip = NULL;

    SCIPcreate(&scip);
    SCIPincludeDefaultPlugins(scip);

    /* Include user plugin here, e.g. */
    /* SCIPincludeConshdlrMyConstraint(scip); */
    /* SCIPincludeSepaMyCuts(scip); */
    /* SCIPincludeHeurMyHeuristic(scip); */
    /* SCIPincludeBranchruleMyRule(scip); */

    SCIPreadProb(scip, "model.lp", NULL);
    SCIPsolve(scip);
    SCIPfree(&scip);
    return 0;
}
```

### 10.15.3 Deployment consequence

```text id="eyqvf5"
If custom native plugin required:
  Pyomo alone is insufficient
  build SCIP plugin binary/application
  decide data exchange path:
    Pyomo writes .lp/.mps/.nl-like artifact
    native app reads supported format
    or rebuild model directly in native code/PySCIPOpt
```

---

## 10.16 Pyomo-facing design patterns

### 10.16.1 Pattern A: express semantics as algebra

```text id="t0e4xn"
Use when:
  constraint count manageable
  formulation known
  solver-native callback not required

Tools:
  linear constraints
  quadratic constraints
  SOS1/SOS2
  Piecewise
  GDP transformations
  manual big-M/hull
```

```python id="eogc1s"
from pyomo.environ import *
from pyomo.gdp import Disjunct, Disjunction

# Build logical/disjunctive model
TransformationFactory("gdp.bigm").apply_to(model)
SolverFactory("scip").solve(model)
```

### 10.16.2 Pattern B: tune native built-ins through parameters

```python id="2g1t0i"
opt = SolverFactory("scip")
opt.options["presolving/maxrounds"] = -1
opt.options["separating/maxroundsroot"] = -1
opt.options["heuristics/rens/freq"] = 10
opt.options["branching/preferbinary"] = "TRUE"
opt.options["display/relevantstats"] = "TRUE"
```

### 10.16.3 Pattern C: external iterative algorithm

```text id="sjgzyq"
Use when:
  callback can be emulated by solve-inspect-augment
  latency acceptable
  cuts/columns added between solves
```

```python id="k56n5q"
for iteration in range(max_iter):
    res = opt.solve(model, load_solutions=False)
    if len(res.solution) == 0:
        raise RuntimeError("No incumbent")
    model.solutions.load_from(res)

    updates = generate_cuts_or_columns(model)
    if not updates:
        break

    apply_updates(model, updates)
```

### 10.16.4 Pattern D: switch to PySCIPOpt/native

```text id="dbtli7"
Switch when:
  dynamic separation needed inside tree
  lazy constraints required at candidate-solution checks
  custom branching/node selection needed
  column generation must happen inside solver
  solve-event callbacks needed
  plugin performance research needed
```

PySCIPOpt is explicitly the Python interface to SCIP and its documentation includes tutorials for branching rules, cut selectors, separators, heuristics, node selectors, lazy constraints through constraint handlers, and event handlers. ([PySCIPOpt Documentation][5])

---

## 10.17 Decision procedure for LLM agents

```text id="ok7rnx"
User asks for custom lazy constraints:
  if Pyomo:
    propose explicit constraints or outer cut loop
    warn no native SCIP lazy callback through SolverFactory("scip")
  if native callback required:
    route to PySCIPOpt Conshdlr

User asks for column generation:
  if small finite columns:
    generate all in Pyomo
  if huge implicit columns:
    route to GCG / SCIP pricer / native branch-price

User asks for custom cuts:
  if cuts can be generated before/after solves:
    Pyomo cut loop
  if cuts must be generated at LP nodes:
    PySCIPOpt Separator or C/C++

User asks for custom branching:
  PySCIPOpt Branchrule / native SCIP
  Pyomo can only tune built-in branching parameters

User asks for node progress callback:
  PySCIPOpt Eventhdlr / native SCIP
  Pyomo can only parse logs after/during process

User asks for performance tuning:
  stay in Pyomo
  use opt.options
  inspect logs/stats
```

---

## 10.18 Feature-to-route matrix

| Desired capability            | Stay in Pyomo? | Pyomo mechanism                           | Native route trigger                     |
| ----------------------------- | -------------: | ----------------------------------------- | ---------------------------------------- |
| static MILP/MINLP solve       |            yes | algebraic formulation                     | no                                       |
| tune cuts/heuristics/presolve |            yes | `opt.options[...]`                        | only if built-ins insufficient           |
| inspect final gap/bounds/log  |            yes | `SolverResults`, logfile                  | no                                       |
| custom lazy constraints       |          maybe | outer solve-add loop                      | if must be inside search                 |
| custom separator              |             no | none                                      | PySCIPOpt/C                              |
| custom branch rule            |             no | none                                      | PySCIPOpt/C                              |
| custom node selector          |             no | none                                      | PySCIPOpt/C                              |
| event callback                |             no | log parsing only                          | PySCIPOpt/C                              |
| column generation             |          maybe | external loop                             | native pricer/GCG if branch-price needed |
| custom file format reader     |             no | convert to Pyomo or SCIP-supported format | native reader                            |
| custom display/statistics     |             no | table/display params only                 | native display/table plugin              |
| custom Benders plugin         |             no | external decomposition loop               | native SCIP/GCG/PySCIPOpt                |

---

## 10.19 Anti-patterns

```text id="zf9vxj"
Anti-pattern:
  “Use SolverFactory("scip") and add a callback.”
Reason:
  SCIPAMPL is external .nl/.sol system-call interface.

Anti-pattern:
  “Use Pyomo opt.options to register a plugin.”
Reason:
  opt.options writes scip.set parameters; it does not load Python callbacks.

Anti-pattern:
  “Implement lazy constraints by adding constraints after final solve only.”
Reason:
  valid only as outer loop if repeated until no violation.

Anti-pattern:
  “Use Pyomo for branch-and-price.”
Reason:
  static NL export cannot dynamically price variables inside branch-and-bound.

Anti-pattern:
  “Treat SCIP native plugin docs as Pyomo API.”
Reason:
  native SCIP and Pyomo SCIPAMPL have different control planes.
```

---

## 10.20 Compact mental model

```text id="9cafpl"
Native SCIP:
  solver framework
  plugins are first-class:
    constraints
    pricers
    propagators
    separators
    relaxators
    Benders
    heuristics
    node selectors
    branching
    presolvers
    readers
    events
    displays/dialogs/tables

PySCIPOpt:
  Python access to selected native SCIP extension surfaces:
    Branchrule
    Separator
    Heur
    Node Selector
    Conshdlr
    Eventhdlr
    etc.

Pyomo SolverFactory("scip"):
  algebraic model export
  external scip executable
  parameters through scip.set
  final results/log parsing
  no plugin/callback registration

Rule:
  formulation + parameters -> Pyomo
  callbacks/plugins/dynamic search control -> PySCIPOpt or C/C++
```

[1]: https://www.scipopt.org/ "SCIP"
[2]: https://pyomo.readthedocs.io/en/6.8.2/_modules/pyomo/solvers/plugins/solvers/SCIPAMPL.html "pyomo.solvers.plugins.solvers.SCIPAMPL — Pyomo 6.8.2 documentation"
[3]: https://scipopt.org/doc/html/group__PluginManagementMethods.php "SCIP Doxygen Documentation: Methods for managing plugins"
[4]: https://pyscipopt.readthedocs.io/en/latest/tutorials/lazycons.html "Lazy Constraints (via Constraint Handler) — PySCIPOpt  documentation"
[5]: https://pyscipopt.readthedocs.io/ "PySCIPOpt Documentation — PySCIPOpt  documentation"
[6]: https://scipopt.org/doc/html/modules.php "SCIP Doxygen Documentation: SCIP C-API"

# 11) File formats and standalone SCIP usage — Pyomo export, shell workflows, and artifact debugging

Dense technical reference for LLM programming agents. Style aligned with the uploaded advanced-doc pattern. 

---

## 11.0 Mental model

```text id="cxqh3q"
SCIP-native standalone path:
  model file
    -> scip shell / scip executable
    -> read
    -> set parameters
    -> optimize
    -> display/write solution/statistics/problem

Pyomo-generated SCIP path:
  Pyomo model
    -> NL writer
    -> .nl (+ optional .row/.col)
    -> external scip executable in AMPL mode
    -> .sol
    -> Pyomo SolverResults

Debugging bridge:
  use Pyomo keepfiles=True + symbolic_solver_labels=True
  capture .nl/.row/.col/.sol/.log/scip.set-equivalent
  replay or inspect in standalone SCIP where possible
```

SCIP is usable as a standalone solver for MIP/MINLP and as a CIP/branch-cut-and-price framework; its website states it can solve mixed-integer linear and nonlinear programs from formats such as MPS, LP, FlatZinc, CNF, OPB, WBO, PIP, and can directly read ZIMPL models. ([scipopt.org](https://www.scipopt.org/))

---

## 11.1 SCIP file-reader capability inventory

### 11.1.1 Native reader list

SCIP’s file-reader documentation states that the interactive shell and callable library can read/parse multiple formats, including:

```text id="f802og"
BND   variable bounds
CIP   SCIP constraint integer programming format
CNF   DIMACS CNF, e.g. SAT problems
DIFF  new objective function for MIPs
FZN   FlatZinc / MiniZinc target language
LP    mixed-integer quadratically constrained quadratic programs, CPLEX LP style
MPS   mixed-integer quadratically constrained quadratic programs
NL    AMPL .nl files, e.g. mixed-integer linear and nonlinear
OPB   pseudo-Boolean optimization instances
OSiL  mixed-integer nonlinear programs
PIP   mixed-integer polynomial programming problems
SOL   solution files; XML read-only or raw SCIP format
WBO   weighted pseudo-Boolean optimization instances
ZPL   ZIMPL mixed-integer linear and nonlinear models, read-only
```

SCIP’s file-reader page lists these formats and explicitly says the interactive shell and callable library can read/parse several file formats. ([scipopt.org](https://www.scipopt.org/doc/html/group__FILEREADERS.php))

### 11.1.2 Interface selection table

| Source artifact              | Best SCIP path                               | Why                                                                 |
| ---------------------------- | -------------------------------------------- | ------------------------------------------------------------------- |
| Pyomo algebraic MINLP/MILP   | `SolverFactory("scip")` → `.nl`              | Pyomo’s SCIP plugin is NL/SOL based                                 |
| Hand-written MILP            | standalone `.lp` / `.mps`                    | human-readable or standard exchange                                 |
| Quadratic MIP/QCP            | `.lp` / `.mps` if supported by writer/source | SCIP LP/MPS readers cover quadratically constrained quadratic forms |
| Pseudo-Boolean               | `.opb` / `.wbo`                              | native pseudo-Boolean readers                                       |
| SAT-like CNF                 | `.cnf`                                       | native DIMACS CNF reader                                            |
| ZIMPL model                  | `.zpl`                                       | SCIP can directly read ZIMPL                                        |
| General nonlinear exchange   | `.nl` / `.osil`                              | SCIP readers support AMPL NL and OSiL                               |
| SCIP-native constraint model | `.cip`                                       | closest to SCIP’s native constraint-programming model               |
| Incumbent transfer           | `.sol`                                       | SCIP solution reader/writer path                                    |

---

## 11.2 Standalone SCIP shell workflow

### 11.2.1 Interactive shell

```bash id="3grbsp"
scip
```

Core commands:

```text id="5rwbhp"
SCIP> help
SCIP> read model.lp
SCIP> optimize
SCIP> display solution
SCIP> display statistics
SCIP> write solution solution.sol
SCIP> write genproblem model.lp
SCIP> set save scip.set
SCIP> set diffsave tuned.set
SCIP> set load tuned.set
SCIP> quit
```

SCIP’s shell help includes `read`, `optimize`, `display`, `set`, `write`, and `quit`; the tutorial explicitly says to use `read <file>` to parse an instance, `optimize` to solve it, and `display solution` to show nonzero variables of the best solution. ([scipopt.org](https://www.scipopt.org/doc/html/SHELL.php))

### 11.2.2 Minimal standalone solve

```text id="1ul9vp"
SCIP> read model.lp
SCIP> optimize
SCIP> display solution
```

The SCIP tutorial demonstrates `SCIP> read ...`, `SCIP> optimize`, final fields such as `SCIP Status`, `Solving Time`, `Solving Nodes`, `Primal Bound`, `Dual Bound`, and `Gap`, then `SCIP> display solution`. ([scipopt.org](https://www.scipopt.org/doc/html/SHELL.php))

### 11.2.3 Standalone solve with settings

```text id="l8ov0j"
SCIP> set load tuned.set
SCIP> read model.lp
SCIP> optimize
SCIP> display statistics
SCIP> write solution model.sol
```

SCIP settings are not saved through ordinary `write`/`read`; the shell provides `set save`, `set diffsave`, and `set load` for settings files. ([scipopt.org](https://www.scipopt.org/doc/html/SHELL.php))

### 11.2.4 Noninteractive shell script

```bash id="vh1m4f"
cat > solve.scip <<'EOF'
set load tuned.set
read model.lp
optimize
display solution
display statistics
write solution solution.sol
quit
EOF

scip < solve.scip > scip-standalone.log 2>&1
```

### 11.2.5 Batch command file generator

```python id="y53g1b"
from pathlib import Path

def write_scip_batch(
    path: str,
    model_file: str,
    *,
    settings_file: str | None = None,
    solution_file: str = "solution.sol",
    stats: bool = True,
):
    lines = []
    if settings_file:
        lines.append(f"set load {settings_file}")
    lines.extend([
        f"read {model_file}",
        "optimize",
        "display solution",
    ])
    if stats:
        lines.append("display statistics")
    lines.extend([
        f"write solution {solution_file}",
        "quit",
    ])
    Path(path).write_text("\n".join(lines) + "\n")
```

---

## 11.3 `scip.set` usage

### 11.3.1 Save full parameter file

```text id="cgfeao"
SCIP> set save scip.set
```

### 11.3.2 Save only non-default parameters

```text id="29kfxs"
SCIP> set diffsave tuned.set
```

### 11.3.3 Load settings

```text id="z8x3u1"
SCIP> set load tuned.set
```

### 11.3.4 Reserved filename behavior

```text id="bk0fh2"
If standalone SCIP starts in a working directory containing:
  scip.set

Then:
  SCIP automatically replaces default settings with that file.
```

SCIP’s shell documentation calls special attention to the reserved name `scip.set`: when the interactive shell starts in a working directory containing a settings file with that name, SCIP automatically uses it instead of default settings. ([scipopt.org](https://www.scipopt.org/doc/html/SHELL.php))

### 11.3.5 Pyomo caveat

```text id="q1jbgc"
Pyomo opt.options nonempty:
  Pyomo writes its own temporary scip.set
  Pyomo runs SCIP with cwd=temp_options_dir
  current-directory ./scip.set is ignored and Pyomo warns
```

Pyomo’s SCIP plugin writes option lines into a temporary `scip.set`; if a current-working-directory `scip.set` exists, Pyomo warns it will be ignored because options are being set through a separate options file. ([pyomo.readthedocs.io](https://pyomo.readthedocs.io/en/6.8.2/_modules/pyomo/solvers/plugins/solvers/SCIPAMPL.html))

### 11.3.6 Safe split-brain rule

```text id="ps7cql"
Standalone SCIP:
  use scip.set / tuned.set directly

Pyomo SCIP:
  use opt.options[...] or solve(..., options={...})
  archive opt.options as scip-from-pyomo-options.set

Do not:
  rely on ambient scip.set while also using Pyomo opt.options
```

---

## 11.4 Pyomo-generated path: `.nl` via AMPL interface

### 11.4.1 Pyomo SCIP plugin contract

```text id="3w9bxi"
SolverFactory("scip"):
  valid problem format: NL
  valid result format: SOL
  command:
    scip <problem-without-.nl-if-SCIP>=8> -AMPL
```

Pyomo’s SCIP plugin registers the solver as `scip`, sets valid problem formats to `[ProblemFormat.nl]`, valid result format for NL to `[ResultsFormat.sol]`, derives a `.sol` filename, and constructs the command list `[executable, problem_file, "-AMPL"]`; for SCIP version 8 or newer, it strips the `.nl` extension before passing the problem path. ([pyomo.readthedocs.io](https://pyomo.readthedocs.io/en/6.8.2/_modules/pyomo/solvers/plugins/solvers/SCIPAMPL.html))

### 11.4.2 Main solve

```python id="9ki15k"
from pyomo.environ import *

opt = SolverFactory("scip", solver_io="nl")
res = opt.solve(model, tee=True)
```

### 11.4.3 Debug solve

```python id="cg00cq"
res = opt.solve(
    model,
    tee=True,
    logfile="scip.log",
    keepfiles=True,
    symbolic_solver_labels=True,
    load_solutions=False,
)
```

Pyomo’s command-line documentation says `--keepfiles` keeps generated solver files and outputs their names, and that `--symbolic-solver-labels` should usually be specified with it so meaningful names are used in those files. ([pyomo.readthedocs.io](https://pyomo.readthedocs.io/en/6.8.0/working_abstractmodels/pyomo_command.html))

### 11.4.4 Generated file meaning

```text id="c7q1ya"
*.nl:
  AMPL Solver Library NL representation
  supports linear + nonlinear expressions
  primary Pyomo->SCIP transport

*.row:
  ASL row file: objective/constraint names
  generated only when symbolic_solver_labels=True

*.col:
  ASL col file: variable names
  generated only when symbolic_solver_labels=True

*.sol:
  SCIP/AMPL solution file
  parsed by Pyomo

*_scip.log or provided logfile:
  solver command line + SCIP log
```

Pyomo’s NL writer writes a model in NL format and, when `symbolic_solver_labels=True`, can also write ASL row and col streams: the row file contains constraint/objective names, and the col file contains variable names. ([pyomo.readthedocs.io](https://pyomo.readthedocs.io/en/stable/api/pyomo.repn.plugins.nl_writer.NLWriter.html))

---

## 11.5 Exporting Pyomo models manually

### 11.5.1 Export `.nl`

```python id="q132i7"
model.write(
    "model.nl",
    format="nl",
    io_options={
        "symbolic_solver_labels": True,
        "file_determinism": 30,  # SORT_SYMBOLS
    },
)
```

Pyomo’s NL writer documents `write(model, ostream, rowstream=None, colstream=None, **options)`, supports `symbolic_solver_labels`, and defines file-determinism levels including `ORDERED`, `SORT_INDICES`, and `SORT_SYMBOLS`. ([pyomo.readthedocs.io](https://pyomo.readthedocs.io/en/stable/api/pyomo.repn.plugins.nl_writer.NLWriter.html))

### 11.5.2 Export `.lp`

```python id="c7pa4t"
model.write(
    "model.lp",
    format="lp",
    io_options={
        "symbolic_solver_labels": True,
        "file_determinism": 30,
    },
)
```

Pyomo’s LP writer writes models in LP format, accepts an output stream, supports `symbolic_solver_labels`, and has deterministic writer controls. ([pyomo.readthedocs.io](https://pyomo.readthedocs.io/en/6.8.1/api/pyomo.repn.plugins.lp_writer.LPWriter.html))

### 11.5.3 Export caveats

```text id="p3kgpr"
NL:
  best Pyomo export for general nonlinear expressions
  native Pyomo SCIP transport
  less human-readable

LP:
  human-readable
  useful for linear/quadratic debugging
  not the right target for arbitrary nonlinear Pyomo expressions

MPS:
  standard exchange for linear/quadratic MIP workflows
  less readable than LP
  strong interoperability format when available

CIP:
  SCIP-native semantic format
  normally produced by SCIP, not Pyomo’s standard solve path
```

SCIP’s file-reader docs describe LP and MPS as formats for mixed-integer quadratically constrained quadratic programs, and NL as the AMPL `.nl` format for mixed-integer linear and nonlinear problems. ([scipopt.org](https://www.scipopt.org/doc/html/group__FILEREADERS.php))

---

## 11.6 Running Pyomo-generated `.nl` in standalone SCIP

### 11.6.1 Direct replay shape

For SCIP 8+:

```bash id="a1ytzj"
scip model -AMPL
```

where the physical file is:

```text id="85vagw"
model.nl
```

Pyomo’s SCIP plugin strips `.nl` from the command argument for SCIP version 8 or newer, so the command form is `scip model -AMPL` while the file on disk is `model.nl`. ([pyomo.readthedocs.io](https://pyomo.readthedocs.io/en/6.8.2/_modules/pyomo/solvers/plugins/solvers/SCIPAMPL.html))

### 11.6.2 Replay script from Pyomo keepfiles output

```bash id="pit88l"
# Suppose keepfiles printed /tmp/tmpabc123.pyomo.nl
# For SCIP >= 8:
scip /tmp/tmpabc123.pyomo -AMPL > replay.log 2>&1
```

### 11.6.3 Replay with settings

```bash id="mbw962"
mkdir -p replay
cp /tmp/tmpabc123.pyomo.nl replay/model.nl
cp tuned.set replay/scip.set

(
  cd replay
  scip model -AMPL > replay.log 2>&1
)
```

### 11.6.4 Why replay matters

```text id="9obcqo"
Replay .nl when:
  Pyomo result unexpected
  solver executable behavior needs isolation
  options need testing outside Python
  SCIP support/debugging requires raw instance
  agent must distinguish model-export issue from solver issue
```

---

## 11.7 Comparing Pyomo `.nl` vs hand-written `.lp`

### 11.7.1 What comparison can answer

```text id="nsjgca"
Compare .nl vs .lp to determine:
  Did Pyomo export the intended algebra?
  Is the nonlinear writer introducing auxiliary/defined variables?
  Did symbolic labels preserve component mapping?
  Does a simpler human-readable LP equivalent solve the same way?
  Is the issue in formulation, writer, SCIP reader, or solver options?
```

### 11.7.2 Valid comparison cases

```text id="blbja3"
Good comparison:
  Pyomo MILP exported to LP
  hand-written LP with same variables/constraints/objective
  same SCIP settings
  same objective sense
  same bounds/domains
  compare objective, solution, status

Weak comparison:
  nonlinear Pyomo .nl vs linearized hand LP
  different formulations
  different bounds
  different scaling
  different parameters
```

### 11.7.3 Export and solve both

```python id="jj5iof"
from pyomo.environ import *

# Export Pyomo LP if representable
model.write(
    "pyomo_model.lp",
    format="lp",
    io_options={"symbolic_solver_labels": True, "file_determinism": 30},
)

# Export Pyomo NL
model.write(
    "pyomo_model.nl",
    format="nl",
    io_options={"symbolic_solver_labels": True, "file_determinism": 30},
)
```

```bash id="caarxn"
# Solve LP through standalone SCIP
scip < solve_lp.scip > lp.log 2>&1

# solve_lp.scip:
# set load tuned.set
# read pyomo_model.lp
# optimize
# display solution
# display statistics
# write solution pyomo_model_lp.sol
# quit

# Solve NL through AMPL mode
scip pyomo_model -AMPL > nl.log 2>&1
```

### 11.7.4 Comparison checklist

```text id="na2cnb"
Compare:
  status
  objective value
  primal bound
  dual bound
  gap
  variable values
  variable bounds
  integer declarations
  objective sense
  fixed variables
  presolve reductions
  constraint count
  coefficient signs/scales
```

---

## 11.8 Debugging with `keepfiles=True`

### 11.8.1 Pyomo solve

```python id="qrwn1s"
res = opt.solve(
    model,
    tee=True,
    logfile="debug/scip.log",
    keepfiles=True,
    symbolic_solver_labels=True,
    load_solutions=False,
)
```

### 11.8.2 Artifact triage

```text id="vqbvwb"
If infeasible:
  inspect .row for constraint names
  inspect .col for variable names
  inspect .nl with labels if readable enough
  rerun standalone with presolve off
  run Pyomo infeasibility utilities on original model

If unbounded:
  inspect variable bounds in .lp/.nl export
  export LP when possible
  solve feasibility-only variant
  add physical bounds

If result differs from expectation:
  compare hand-written LP
  compare Pyomo LP export
  enable deterministic writer
  archive data used to build model

If SCIP option behavior unexpected:
  write opt.options to scip-from-pyomo-options.set
  check whether local scip.set was ignored
  replay standalone with same scip.set
```

### 11.8.3 Save Pyomo options as `scip.set` equivalent

```python id="lmhsdw"
from pathlib import Path

def write_pyomo_scip_set(opt, path):
    lines = []
    for k, v in sorted(opt.options.items()):
        if k == "solver":
            continue
        lines.append(f"{k} = {v}")
    Path(path).write_text("\n".join(lines) + "\n")

write_pyomo_scip_set(opt, "debug/scip-from-pyomo-options.set")
```

Pyomo’s SCIP plugin writes each option as `key = value` into its generated temporary `scip.set`, so this reproduces the option file shape for archiving or standalone replay. ([pyomo.readthedocs.io](https://pyomo.readthedocs.io/en/6.8.2/_modules/pyomo/solvers/plugins/solvers/SCIPAMPL.html))

---

## 11.9 Standalone SCIP output files

### 11.9.1 Write solution

```text id="bgbgf4"
SCIP> write solution model.sol
```

### 11.9.2 Write problem in another format

```text id="n2hxc8"
SCIP> write genproblem model.lp
```

SCIP’s shell tutorial demonstrates writing the incumbent solution with `write solution stein27.sol` and writing the original problem in LP format with `write genproblem stein27.lp`; it notes LP is more human-readable than MPS in that example. ([scipopt.org](https://www.scipopt.org/doc/html/SHELL.php))

### 11.9.3 Display statistics

```text id="oixdqs"
SCIP> display statistics
```

The shell tutorial states `display statistics` shows solution-process information and demonstrates detailed statistics tables such as presolvers, constraints, propagators, conflict analysis, and timing. ([scipopt.org](https://www.scipopt.org/doc/html/SHELL.php))

---

## 11.10 File-format decision matrix

| Format  | Human-readable |                     General nonlinear | Integer support | Best use                          |
| ------- | -------------: | ------------------------------------: | --------------: | --------------------------------- |
| `.nl`   |             no |                                   yes |             yes | Pyomo/AMPL transport to SCIP      |
| `.lp`   |            yes |      limited to LP/QP/QCP-style forms |             yes | human-readable MILP/QP debug      |
| `.mps`  |      partly/no | limited to supported MIP/QP/QCP forms |             yes | solver interoperability           |
| `.cip`  |         partly |               SCIP-native constraints |             yes | SCIP-native debugging/interchange |
| `.osil` |            XML |                                   yes |             yes | nonlinear exchange                |
| `.opb`  |        yes-ish |                        pseudo-Boolean |          binary | pseudo-Boolean optimization       |
| `.wbo`  |        yes-ish |               weighted pseudo-Boolean |          binary | MaxSAT/WBO-like workflows         |
| `.cnf`  |        yes-ish |                           SAT clauses |         Boolean | SAT-like input                    |
| `.zpl`  |            yes |                        model language |             yes | ZIMPL input                       |
| `.sol`  |        yes-ish |                                   n/a |             n/a | solution transfer                 |

SCIP’s file-reader list documents the supported formats and associates them with their model classes: LP/MPS for mixed-integer quadratically constrained quadratic programs, NL for AMPL linear/nonlinear problems, OPB/WBO for pseudo-Boolean optimization, CNF for SAT-style files, OSiL/PIP for nonlinear/polynomial problems, and SOL for solution files. ([scipopt.org](https://www.scipopt.org/doc/html/group__FILEREADERS.php))

---

## 11.11 PySCIPOpt file I/O side path

### 11.11.1 Read model

```python id="sb6tkh"
from pyscipopt import Model

m = Model()
m.readProblem("model.lp")
m.optimize()
```

### 11.11.2 Write model

```python id="r9pab9"
m.writeProblem("model.lp")
m.writeProblem("model.mps")
```

PySCIPOpt’s read/write tutorial says SCIP has extensive file-format support and recommends `.mps` for sharing files when possible, `.lp` for more human-readable equivalent problems, and `.osil` for general nonlinearities shared with others. ([pyscipopt.readthedocs.io](https://pyscipopt.readthedocs.io/en/latest/tutorials/readwrite.html))

### 11.11.3 When PySCIPOpt file I/O is superior

```text id="5ufmhx"
Use PySCIPOpt file I/O when:
  need native SCIP object after reading file
  need to inspect variables/constraints programmatically
  need to set callbacks/plugins after reading
  need to write transformed problems from SCIP state
```

---

## 11.12 Reproducible debug bundle

### 11.12.1 Directory layout

```text id="sx0grd"
debug_bundle/
  pyomo/
    model.py
    data.json
    model.lp              # if exportable
    model.nl
    model.row
    model.col
  scip/
    scip.log
    replay.log
    scip-from-pyomo-options.set
    tuned.set
    scip-all.set
    solution.sol
  metadata/
    pyomo-version.txt
    scip-version.txt
    environment.yml
    conda-lock.yml
    solve-summary.json
```

### 11.12.2 Capture script

```python id="5ph6or"
from pathlib import Path
from pyomo.environ import SolverFactory

def solve_and_capture(model, run_dir="debug_bundle"):
    run = Path(run_dir)
    (run / "pyomo").mkdir(parents=True, exist_ok=True)
    (run / "scip").mkdir(parents=True, exist_ok=True)

    opt = SolverFactory("scip", solver_io="nl")
    opt.options["limits/time"] = 300
    opt.options["display/verblevel"] = 5
    opt.options["display/relevantstats"] = "TRUE"

    write_pyomo_scip_set(opt, run / "scip" / "scip-from-pyomo-options.set")

    # Direct exports
    model.write(
        str(run / "pyomo" / "model.nl"),
        format="nl",
        io_options={"symbolic_solver_labels": True, "file_determinism": 30},
    )

    try:
        model.write(
            str(run / "pyomo" / "model.lp"),
            format="lp",
            io_options={"symbolic_solver_labels": True, "file_determinism": 30},
        )
    except Exception as e:
        (run / "pyomo" / "model.lp.export_failed.txt").write_text(repr(e))

    res = opt.solve(
        model,
        tee=True,
        logfile=str(run / "scip" / "scip.log"),
        keepfiles=True,
        symbolic_solver_labels=True,
        load_solutions=False,
    )
    return res
```

---

## 11.13 Standalone replay generator for Pyomo `.nl`

```python id="lit5ll"
from pathlib import Path

def write_nl_replay_script(
    nl_file: str,
    script_path: str,
    *,
    settings_file: str | None = None,
    solution_file: str = "replay.sol",
):
    nl_path = Path(nl_file)
    stem_for_scip8 = str(nl_path.with_suffix(""))  # physical file remains .nl

    lines = []
    if settings_file:
        lines.append(f"set load {settings_file}")
    lines.extend([
        # In SCIP 8+, AMPL/NL reader expects the path without ".nl" when using -AMPL,
        # matching Pyomo SCIPAMPL command construction.
        f"read {nl_file}",
        # Normal shell `read model.nl` can also work through the NL reader;
        # Pyomo's subprocess path uses: scip model -AMPL.
        "optimize",
        "display solution",
        "display statistics",
        f"write solution {solution_file}",
        "quit",
    ])

    Path(script_path).write_text("\n".join(lines) + "\n")
    return stem_for_scip8
```

Practical replay choices:

```bash id="ku350y"
# Pyomo-faithful AMPL mode, SCIP >= 8
scip path/to/model -AMPL > replay-ampl.log 2>&1

# Shell reader mode
scip < replay.scip > replay-shell.log 2>&1
```

Use both only when diagnosing reader differences. Prefer the Pyomo-faithful `-AMPL` mode when reproducing Pyomo behavior.

---

## 11.14 Comparing Pyomo `.nl` and `.lp`: automated harness

```python id="6mrj1r"
import subprocess
from pathlib import Path

def run_cmd(cmd, cwd=None):
    return subprocess.run(
        cmd,
        cwd=cwd,
        shell=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )

def solve_lp_standalone(lp_file, settings_file=None):
    script = Path("solve_lp.scip")
    lines = []
    if settings_file:
        lines.append(f"set load {settings_file}")
    lines.extend([
        f"read {lp_file}",
        "optimize",
        "display solution",
        "display statistics",
        "write solution lp.sol",
        "quit",
    ])
    script.write_text("\n".join(lines) + "\n")
    return run_cmd("scip < solve_lp.scip")

def solve_nl_ampl(nl_file, settings_file=None):
    nl = Path(nl_file)
    work = Path("nl_replay")
    work.mkdir(exist_ok=True)
    target = work / nl.name
    target.write_bytes(nl.read_bytes())

    if settings_file:
        (work / "scip.set").write_text(Path(settings_file).read_text())

    stem = target.with_suffix("").name
    return run_cmd(f"scip {stem} -AMPL", cwd=work)
```

---

## 11.15 Agent routing rules

```text id="781jbj"
If user asks “solve a Pyomo model with SCIP”:
  use SolverFactory("scip")
  solver_io="nl"
  opt.solve(...)

If user asks “debug what Pyomo sent to SCIP”:
  use keepfiles=True
  symbolic_solver_labels=True
  logfile
  inspect .nl/.row/.col/.sol

If user asks “solve this LP/MPS/OPB/WBO/CNF/ZPL file”:
  use standalone scip shell
  read file
  optimize

If user asks “use scip.set”:
  standalone SCIP: put scip.set in cwd or set load file
  Pyomo: translate settings to opt.options or archive generated options file

If user asks “compare Pyomo .nl with hand .lp”:
  export LP if representable
  keep same settings
  compare objective/status/solution/bounds
  do not expect arbitrary nonlinear .nl to equal LP

If user asks “custom SCIP file reader”:
  Pyomo is wrong layer
  use native SCIP C/C++ plugin path
```

---

## 11.16 Failure-mode diagnostics

| Symptom                                        | Likely cause                                         | Probe                            | Fix                                                          |
| ---------------------------------------------- | ---------------------------------------------------- | -------------------------------- | ------------------------------------------------------------ |
| standalone `read model.lp` fails               | unsupported syntax or writer issue                   | `scip` shell error               | export `.mps` or `.nl`; simplify model                       |
| Pyomo solve works but standalone `.lp` differs | `.lp` export not equivalent to `.nl` nonlinear model | compare expressions/bounds       | use `.nl` replay; restrict LP comparison to linear/quadratic |
| `scip model.nl -AMPL` fails for SCIP 8+        | wrong AMPL invocation path                           | Pyomo source command             | use `scip model -AMPL`                                       |
| missing `.row/.col`                            | labels not enabled                                   | solve kwargs                     | `symbolic_solver_labels=True`                                |
| hard-to-map variables in LP                    | symbolic labels off                                  | LP variable names                | export with labels                                           |
| ambient `scip.set` ignored in Pyomo            | Pyomo temp option file                               | Pyomo warning/log                | put options in `opt.options`                                 |
| no `.sol` after solve                          | SCIP failed before solution write                    | inspect log                      | fix model/options; use debug artifacts                       |
| file names disappear                           | keepfiles off                                        | Pyomo temp cleanup               | `keepfiles=True`                                             |
| replay differs from Pyomo                      | missing options/env/external funcs                   | compare command/log/env/scip.set | use Pyomo log command line and option file                   |

---

## 11.17 Compact mental model

```text id="hl0em8"
SCIP standalone:
  scip
  read model.lp
  optimize
  display solution
  display statistics
  write solution model.sol
  set save scip.set

SCIP file formats:
  LP/MPS/CIP/NL/OPB/WBO/CNF/FZN/OSiL/PIP/ZPL/SOL/etc.

Pyomo SCIP:
  always NL/SOL through SCIPAMPL
  scip <problem> -AMPL
  SCIP >= 8 uses path without .nl suffix

Debug Pyomo:
  opt.solve(
      model,
      tee=True,
      logfile="scip.log",
      keepfiles=True,
      symbolic_solver_labels=True,
      load_solutions=False,
  )

Compare formats:
  .nl = faithful Pyomo nonlinear transport
  .lp = human-readable when representable
  .mps = exchange-friendly when representable
  .cip = SCIP-native, usually produced/consumed in native SCIP workflows

Golden rule:
  Use Pyomo .nl for faithful reproduction; use LP/MPS for human-readable or interoperability debugging only when the exported model class is equivalent.
```

# 12) PySCIPOpt side path: when Pyomo is not enough

Dense technical reference for LLM programming agents. Style aligned with the uploaded advanced-doc pattern. 

---

## 12.0 Interface boundary

```text id="w8m8m0"
Pyomo + SCIP:
  algebraic modeling layer
  SolverFactory("scip")
  file-based .nl -> scip -AMPL -> .sol
  portable across solvers
  no native SCIP callback/plugin object

PySCIPOpt:
  Python interface to SCIP
  in-process SCIP Model object
  direct variables/constraints/expressions
  direct parameter API
  direct solution and solver-state queries
  Python callback/plugin extension surface
```

PySCIPOpt is explicitly the Python interface to SCIP, and its tutorials include model objects, variables, constraints, nonlinear expressions, parameter settings, file I/O, SCIP logs, branching rules, cut selectors, separators, heuristics, node selectors, lazy constraints via constraint handlers, event handlers, and IIS tooling. ([PySCIPOpt Documentation][1])

---

## 12.1 Installation and deployment

### 12.1.1 Conda/micromamba

```bash id="u0qouk"
micromamba install -c conda-forge pyscipopt
# or
conda install -c conda-forge pyscipopt
```

The PySCIPOpt installation guide states that conda installs SCIP automatically with PySCIPOpt, and the conda-forge package page lists `pyscipopt` as version 6.1.0 with summary “Interface from Python to the SCIP Optimization Suite.” ([PySCIPOpt Documentation][2])

### 12.1.2 Environment rule

```text id="py57ex"
Do:
  create isolated env
  pin pyscipopt + scip versions together
  use conda-forge channel consistently
  avoid base env

Do not:
  install PySCIPOpt into conda base
  mix PyPI PySCIPOpt with unrelated system SCIP unless intentionally building against custom SCIP
```

The PySCIPOpt installation guide explicitly warns not to install PySCIPOpt into the conda base environment and notes that package-manager installs come with their own SCIP versions. ([PySCIPOpt Documentation][2])

### 12.1.3 PyPI caveats

```bash id="fhpukb"
python -m venv .venv
source .venv/bin/activate
pip install pyscipopt
```

Prebuilt PyPI wheels are available for Linux x86_64, Windows x86_64, and macOS x86_64/Apple Silicon; the PySCIPOpt docs note glibc and macOS minimum-version caveats for newer wheels. ([PySCIPOpt Documentation][2])

### 12.1.4 Verification

```python id="fvz6e9"
from pyscipopt import Model

m = Model("verify")
x = m.addVar("x", vtype="B")
m.setObjective(x, "maximize")
m.optimize()

print("status:", m.getStatus())
print("x:", m.getVal(x))
```

PySCIPOpt’s own README shows the canonical steps: `from pyscipopt import Model`, create a `Model`, add variables, set objective, add constraints, optimize, obtain the best solution, and read variable values. ([GitHub][3])

---

## 12.2 What PySCIPOpt provides

### 12.2.1 Direct Python SCIP model object

```python id="kxem30"
from pyscipopt import Model, quicksum

m = Model("direct-scip-model")

x = {i: m.addVar(vtype="B", name=f"x_{i}") for i in range(5)}
y = m.addVar(vtype="C", lb=0.0, ub=10.0, name="y")

m.addCons(quicksum(x[i] for i in range(5)) >= 2)
m.addCons(y <= 3 + 7 * x[0])

m.setObjective(quicksum(i * x[i] for i in range(5)) + y, "minimize")

m.optimize()

print(m.getStatus())
for i in range(5):
    print(i, m.getVal(x[i]))
print("y", m.getVal(y))
```

PySCIPOpt’s README demonstrates direct variable creation, nonlinear/linear constraint construction, objective setting, optimization, and best-solution value access through the `Model` instance. ([GitHub][3])

### 12.2.2 Direct parameter setting

```python id="djo7c7"
from pyscipopt import Model, SCIP_PARAMSETTING

m = Model("params")

# scalar parameters
m.setRealParam("limits/time", 300.0)
m.setRealParam("limits/gap", 1e-4)
m.setIntParam("display/verblevel", 4)
m.setBoolParam("display/relevantstats", True)

# subsystem meta-settings
m.setPresolve(SCIP_PARAMSETTING.DEFAULT)
m.setHeuristics(SCIP_PARAMSETTING.AGGRESSIVE)
m.setSeparating(SCIP_PARAMSETTING.FAST)
```

PySCIPOpt tutorials include parameter settings as a first-class topic, and PySCIPOpt’s tutorial index names “Introduction (Model Object, Solution Information, Parameter Settings)” as the starting point. ([PySCIPOpt Documentation][4])

### 12.2.3 Direct solve-state and solution access

```python id="gqgtlz"
m.optimize()

status = m.getStatus()
best = m.getBestSol()

if best is not None:
    obj = m.getObjVal()
    xval = m.getVal(x[0])
```

The README example uses `model.optimize()`, `model.getBestSol()`, and `sol[x]` / `sol[y]` to read solution values. ([GitHub][3])

### 12.2.4 Native plugin/callback surface

```text id="x33oo1"
PySCIPOpt extension surfaces:
  Branchrule
  Cut selector
  Separator
  Heuristic
  Node selector
  Constraint handler
  Event handler
  plugin-like pure-Python callback classes
```

PySCIPOpt’s official tutorial index includes branching rules, cut selectors, separators, heuristics, node selectors, lazy constraints via constraint handlers, and event handlers; the README states that the Python interface can define custom plugins such as pricers, heuristics, and constraint handlers in pure Python, with SCIP calling their methods through callbacks. ([PySCIPOpt Documentation][4])

---

## 12.3 Minimal PySCIPOpt model-construction syntax

### 12.3.1 MILP

```python id="z5zern"
from pyscipopt import Model, quicksum

m = Model("milp")

I = range(4)
x = {i: m.addVar(vtype="B", name=f"x[{i}]") for i in I}
y = {i: m.addVar(vtype="I", lb=0, ub=10, name=f"y[{i}]") for i in I}
z = m.addVar(vtype="C", lb=0.0, name="z")

m.addCons(quicksum([3, 5, 2, 6][i] * x[i] for i in I) + z <= 12)
for i in I:
    m.addCons(y[i] <= 10 * x[i])

m.setObjective(
    quicksum([4, 7, 2, 9][i] * x[i] for i in I)
    + quicksum(0.5 * y[i] for i in I)
    + 3.0 * z,
    "maximize",
)

m.optimize()
```

### 12.3.2 Nonlinear / quadratic style

```python id="lfbr3o"
from pyscipopt import Model

m = Model("nonlinear")

x = m.addVar("x", lb=0.1, ub=10.0)
y = m.addVar("y", lb=-5.0, ub=5.0)
b = m.addVar("b", vtype="B")

m.addCons(x * y <= 3.0 + 10.0 * b)
m.setObjective((y - 2.0) * (y - 2.0) + 5.0 * b, "minimize")

m.optimize()
```

The PySCIPOpt tutorial index includes nonlinear expressions, variables, and constraints as first-class topics. ([PySCIPOpt Documentation][4])

---

## 12.4 Parameter-setting comparison: Pyomo vs PySCIPOpt

### 12.4.1 Pyomo

```python id="tvhenw"
opt = SolverFactory("scip")
opt.options["limits/time"] = 300
opt.options["limits/gap"] = 1e-4
res = opt.solve(model, tee=True)
```

```text id="eo5h9q"
Effect:
  options -> temporary scip.set
  external scip process
  no direct Model object
```

### 12.4.2 PySCIPOpt

```python id="o850e6"
m = Model()
m.setRealParam("limits/time", 300.0)
m.setRealParam("limits/gap", 1e-4)
m.optimize()
```

```text id="ulzxik"
Effect:
  in-process SCIP object
  direct parameter API
  direct solve-state access
  plugin/callback registration possible
```

---

## 12.5 Event handlers

### 12.5.1 Callback form

```python id="e6zuqt"
from pyscipopt import Model, SCIP_EVENTTYPE

def on_best_solution(model, event):
    print("new incumbent objective:", model.getObjVal())

m = Model("event-callback")
m.attachEventHandlerCallback(on_best_solution, [SCIP_EVENTTYPE.BESTSOLFOUND])

# build model...
m.optimize()
```

PySCIPOpt’s event-handler docs state that SCIP events describe model-state changes before or during solving, such as a new best solution, and show `Model.attachEventHandlerCallback(callback, [SCIP_EVENTTYPE.BESTSOLFOUND])` with callback signature `def callback(model, event)`. ([PySCIPOpt Documentation][5])

### 12.5.2 Class form

```python id="x3idp2"
from pyscipopt import Model, Eventhdlr, SCIP_EVENTTYPE

class BestSolCounter(Eventhdlr):
    def __init__(self):
        self.count = 0

    def eventinit(self):
        self.model.catchEvent(SCIP_EVENTTYPE.BESTSOLFOUND, self)

    def eventexit(self):
        self.model.dropEvent(SCIP_EVENTTYPE.BESTSOLFOUND, self)

    def eventexec(self, event):
        self.count += 1
        print("best solutions found:", self.count)

m = Model("event-class")
handler = BestSolCounter()
m.includeEventhdlr(handler, "best_sol_counter", "count best-solution events")

# build model...
m.optimize()
```

PySCIPOpt’s event-handler docs show an `Eventhdlr` subclass with `eventinit`, `eventexit`, and `eventexec`, included through `Model.includeEventhdlr`. ([PySCIPOpt Documentation][5])

### 12.5.3 Value case

```text id="npo8xi"
Use event handlers when:
  log every incumbent
  terminate based on custom incumbent properties
  record bound progress
  stream solve telemetry
  collect node/solution events
  implement interactive solve monitoring
```

Pyomo’s external file solve cannot expose SCIP event callbacks; use PySCIPOpt or native SCIP for event-driven behavior.

---

## 12.6 Lazy constraints via constraint handlers

### 12.6.1 Use case

```text id="zllaww"
Lazy-constraint path:
  constraints too numerous to enumerate
  violations detected from candidate solutions
  cuts must be enforced during SCIP search
  examples:
    subtour elimination
    connectivity cuts
    combinatorial feasibility cuts
    application-specific no-good cuts
```

PySCIPOpt’s tutorials include “Lazy Constraints (via Constraint Handler),” reflecting SCIP’s broad constraint-handler mechanism rather than a separate Pyomo-style postsolve loop. ([PySCIPOpt Documentation][4])

### 12.6.2 Skeleton

```python id="slba47"
from pyscipopt import Model, Conshdlr, SCIP_RESULT

class LazyCuts(Conshdlr):
    def conscheck(
        self,
        constraints,
        solution,
        checkintegrality,
        checklprows,
        printreason,
        completely,
    ):
        if candidate_solution_is_valid(self.model, solution):
            return {"result": SCIP_RESULT.FEASIBLE}
        return {"result": SCIP_RESULT.INFEASIBLE}

    def consenfolp(self, constraints, nusefulconss, solinfeasible):
        cuts_added = add_violated_cuts_to_model(self.model)
        if cuts_added:
            return {"result": SCIP_RESULT.CONSADDED}
        return {"result": SCIP_RESULT.FEASIBLE}

m = Model("lazy")
lazy = LazyCuts()
m.includeConshdlr(
    lazy,
    "lazycuts",
    "application-specific lazy constraints",
    enfopriority=1,
    chckpriority=1,
    needscons=False,
)

# build model...
m.optimize()
```

### 12.6.3 Pyomo contrast

```text id="mc7cj2"
Pyomo alternative:
  solve
  inspect incumbent
  add violated constraints
  solve again

Limitation:
  not inside SCIP branch-and-bound
  no candidate-solution callbacks
  no node-local enforcement
```

---

## 12.7 Branching rules

### 12.7.1 Use case

```text id="kg3xwr"
Custom branching required when:
  domain-specific variable hierarchy
  nonstandard branching disjunction
  branch priorities insufficient
  strong structure not visible to generic branching
  decomposition/search research
```

PySCIPOpt’s tutorial index contains “Branching Rules,” and its docs list Node/Variable/Row/Column APIs relevant to branching work. ([PySCIPOpt Documentation][4])

### 12.7.2 Skeleton

```python id="p9tqss"
from pyscipopt import Model, Branchrule, SCIP_RESULT

class MyBranchRule(Branchrule):
    def branchexeclp(self, allowaddcons):
        # 1. query candidate variables / LP solution
        # 2. select variable/disjunction
        # 3. create child nodes or call model branching helpers
        return {"result": SCIP_RESULT.DIDNOTRUN}

m = Model("branching")
br = MyBranchRule()
m.includeBranchrule(
    br,
    "my_branching",
    "domain-specific branching rule",
    priority=100000,
    maxdepth=-1,
    maxbounddist=1.0,
)
```

### 12.7.3 Pyomo contrast

```text id="viobyp"
Pyomo can:
  tune built-in branching parameters
  reformulate model
  possibly use solver-supported suffixes only when tested

Pyomo cannot:
  register custom Branchrule
  inspect LP candidates
  create child nodes
```

---

## 12.8 Separators and cut selectors

### 12.8.1 Separator use case

```text id="0lmro3"
Custom separator required when:
  valid inequalities are problem-specific
  cuts depend on LP relaxation solution
  cuts should be generated at root and/or tree nodes
  outer cut loop is too slow or too weak
```

PySCIPOpt’s tutorials include “Separator (Cutting Planes)” and “Cut Selector,” which are exactly the solver-native extension points for generated cuts and cut filtering. ([PySCIPOpt Documentation][4])

### 12.8.2 Separator skeleton

```python id="evcrwn"
from pyscipopt import Model, Sepa, SCIP_RESULT

class MySeparator(Sepa):
    def sepaexeclp(self):
        # 1. inspect LP relaxation
        # 2. identify violated inequality
        # 3. add cut/row through model methods
        return {"result": SCIP_RESULT.DIDNOTFIND}

m = Model("separator")
sep = MySeparator()
m.includeSepa(
    sep,
    "my_separator",
    "application-specific separator",
    priority=100000,
    freq=1,
)
```

### 12.8.3 Pyomo contrast

```text id="ivbxfz"
Pyomo can:
  add static valid inequalities
  run solve-inspect-add-cut loop
  tune built-in separators

Pyomo cannot:
  add cuts at SCIP LP nodes
  implement cut selectors
  access SCIP row/LP callback state through SolverFactory("scip")
```

---

## 12.9 Heuristics

### 12.9.1 Use case

```text id="w688bv"
Custom heuristic required when:
  domain-specific construction/repair method known
  feasible incumbent hard to find
  warm-start logic depends on SCIP state
  local-search neighborhoods are application-specific
  solve objective = find good feasible quickly
```

PySCIPOpt’s tutorial list includes “Heuristics,” and its README says custom heuristics can be written in pure Python as plugins with callbacks. ([PySCIPOpt Documentation][4])

### 12.9.2 Skeleton

```python id="ca0h8u"
from pyscipopt import Model, Heur, SCIP_RESULT, SCIP_HEURTIMING

class MyHeuristic(Heur):
    def heurexec(self, heurtiming, nodeinfeasible):
        # 1. build candidate solution
        # 2. try solution through SCIP
        # 3. report whether found
        return {"result": SCIP_RESULT.DIDNOTFIND}

m = Model("heuristic")
heur = MyHeuristic()
m.includeHeur(
    heur,
    "my_heuristic",
    "domain-specific primal heuristic",
    dispchar="M",
    priority=100000,
    freq=10,
    freqofs=0,
    maxdepth=-1,
    timingmask=SCIP_HEURTIMING.DURINGLPLOOP,
    usessubscip=False,
)
```

### 12.9.3 Pyomo contrast

```text id="p6le4b"
Pyomo can:
  set initial variable values
  tune built-in heuristics
  solve auxiliary heuristic models
  load accepted solution after solve

Pyomo cannot:
  propose heuristic incumbents during branch-and-bound
  access node-local solve state
```

---

## 12.10 Node selectors

### 12.10.1 Use case

```text id="rjfrle"
Custom node selector required when:
  depth-first vs best-bound policy must be domain-specific
  memory pressure requires special traversal
  incumbent-search strategy differs from proof strategy
  search must prioritize application-specific scenario tree regions
```

PySCIPOpt’s tutorial list includes “Node Selector,” which is the native route for changing open-node selection. ([PySCIPOpt Documentation][4])

### 12.10.2 Skeleton

```python id="yzvk0l"
from pyscipopt import Model, Nodesel

class MyNodeSelector(Nodesel):
    def nodeselect(self):
        # choose next open node
        return {"selnode": None}

    def nodecomp(self, node1, node2):
        # ordering comparison for node priority
        return 0

m = Model("nodesel")
ns = MyNodeSelector()
m.includeNodesel(
    ns,
    "my_nodesel",
    "application-specific node selector",
    stdpriority=100000,
    memsavepriority=100000,
)
```

---

## 12.11 Direct solution-pool / solution-state manipulation

### 12.11.1 Query solutions

```python id="rkc2gf"
m.optimize()

best = m.getBestSol()
if best is not None:
    print("best objective:", m.getObjVal())
    for var in m.getVars():
        print(var.name, best[var])
```

The PySCIPOpt README shows `model.getBestSol()` and reading `sol[x]`/`sol[y]` after optimization. ([GitHub][3])

### 12.11.2 Use case

```text id="20c7t8"
Direct solution control useful for:
  enumerating/inspecting multiple solutions
  incumbent callbacks
  custom primal heuristics
  warm-start generation
  solution repair
  application-specific acceptance/rejection
```

### 12.11.3 Pyomo contrast

```text id="b0e7b0"
Pyomo result object:
  final parsed solution(s)
  no direct SCIP incumbent pool object
  no live incumbent callback
```

---

## 12.12 File I/O and native model inspection

### 12.12.1 Read file

```python id="qxrsrv"
from pyscipopt import Model

m = Model()
m.readProblem("model.lp")
m.setRealParam("limits/time", 300.0)
m.optimize()
```

### 12.12.2 Write file

```python id="czr7yr"
m.writeProblem("debug.lp")
m.writeProblem("debug.mps")
```

PySCIPOpt tutorials include “Read and Write Files,” and the docs describe PySCIPOpt as a wrapper around SCIP, with SCIP’s detailed native file/model behavior available through the SCIP documentation. ([PySCIPOpt Documentation][4])

---

## 12.13 When to choose PySCIPOpt instead of Pyomo

### 12.13.1 Hard triggers

```text id="14lq44"
Choose PySCIPOpt when requirement includes:
  custom constraint handler
  lazy constraints inside branch-and-bound
  custom branching rule
  custom separator / cutting plane generation
  custom cut selector
  custom primal heuristic
  custom node selector
  event handling
  direct solution-pool manipulation
  direct SCIP model state queries
  native parameter meta-settings
  branch-cut-and-price / pricer work
  solving process instrumentation
  fine-grained termination/monitoring
```

PySCIPOpt’s README states that Python plugins such as pricers, heuristics, and constraint handlers can be written in pure Python, with SCIP calling callback methods; the tutorial index enumerates branching rules, cut selectors, separators, heuristics, node selectors, lazy constraints via constraint handlers, and event handlers. ([GitHub][3])

### 12.13.2 Soft triggers

```text id="q6y0is"
Prefer PySCIPOpt when:
  one solver only: SCIP
  model build needs in-process SCIP objects
  repeated solves can reuse model state manually
  advanced log/solve telemetry needed
  Python callback overhead acceptable
  performance debugging requires SCIP internals
```

### 12.13.3 Native C/C++ instead of PySCIPOpt

```text id="p87c7w"
Choose C/C++ native SCIP when:
  plugin must be production-fast
  callback overhead matters
  plugin API not exposed by PySCIPOpt
  exact control over memory/lifecycle needed
  custom compiled SCIP build required
  deployment forbids Python callback overhead
```

SCIP describes itself as a C-callable library with C++ wrapper classes for user plugins; PySCIPOpt covers many but not necessarily all SCIP C API/plugin surfaces. ([SCIP Optimization Library][6])

---

## 12.14 When to stay in Pyomo

### 12.14.1 Strong Pyomo reasons

```text id="kjrx53"
Stay in Pyomo when:
  algebraic modeling clarity matters
  solver portability matters
  multiple solvers compared
  model transformations required
  GDP/logical transformations required
  data/model separation important
  existing codebase uses Pyomo Blocks/Sets/Params
  model is generated from Pyomo-friendly data pipelines
  no solver-native callbacks required
  file-based solve overhead acceptable
```

Pyomo is a Python-based open-source optimization modeling language with diverse capabilities, and Pyomo.GDP documents transformations such as `core.logical_to_linear`, `gdp.bigm`, and `gdp.hull` for converting logical/disjunctive models to algebraic MILP/MINLP forms. ([Pyomo][7])

### 12.14.2 Pyomo-first syntax

```python id="qz9wse"
from pyomo.environ import *
from pyomo.gdp import Disjunct, Disjunction

m = ConcreteModel()
m.x = Var(bounds=(0, 10))
m.y = Var(bounds=(0, 10))

m.d1 = Disjunct()
m.d1.c = Constraint(expr=m.x + m.y <= 3)

m.d2 = Disjunct()
m.d2.c = Constraint(expr=m.x - m.y >= 2)

m.disj = Disjunction(expr=[m.d1, m.d2])

TransformationFactory("gdp.bigm").apply_to(m)

opt = SolverFactory("scip")
res = opt.solve(m, tee=True)
```

### 12.14.3 Stay-Pyomo decision rule

```text id="yr1eio"
If the request can be solved by:
  better formulation
  Pyomo transformation
  SCIP parameter tuning
  outer solve loop
  static cuts/constraints
  standard MILP/MINLP solve

Then:
  stay in Pyomo.

If the request requires:
  callbacks during search
  plugin registration
  SCIP node/LP/solution events
  dynamic variable/cut/constraint generation inside SCIP

Then:
  switch to PySCIPOpt/native SCIP.
```

---

## 12.15 Migration pattern: Pyomo formulation → PySCIPOpt implementation

### 12.15.1 Keep data/model separation

```python id="unauwy"
from dataclasses import dataclass

@dataclass(frozen=True)
class ProblemData:
    I: list[int]
    profit: dict[int, float]
    weight: dict[int, float]
    capacity: float
```

### 12.15.2 Pyomo builder

```python id="3be1vs"
from pyomo.environ import *

def build_pyomo(data: ProblemData):
    m = ConcreteModel()
    m.I = Set(initialize=data.I)
    m.x = Var(m.I, domain=Binary)
    m.cap = Constraint(expr=sum(data.weight[i] * m.x[i] for i in m.I) <= data.capacity)
    m.obj = Objective(expr=sum(data.profit[i] * m.x[i] for i in m.I), sense=maximize)
    return m
```

### 12.15.3 PySCIPOpt builder

```python id="kvmqg5"
from pyscipopt import Model, quicksum

def build_pyscipopt(data: ProblemData):
    m = Model("knapsack")
    x = {i: m.addVar(vtype="B", name=f"x[{i}]") for i in data.I}
    m.addCons(quicksum(data.weight[i] * x[i] for i in data.I) <= data.capacity)
    m.setObjective(quicksum(data.profit[i] * x[i] for i in data.I), "maximize")
    return m, x
```

### 12.15.4 Agent migration rules

```text id="budj86"
Preserve:
  data classes
  index sets
  units
  bounds
  objective sense
  domain semantics
  validation tests

Rewrite:
  Var -> addVar
  Constraint -> addCons
  Objective -> setObjective
  Param values -> Python dict/scalars
  Set loops -> Python iterable loops
  TransformationFactory -> manual formulation or native plugin logic
```

---

## 12.16 Hybrid architecture patterns

### 12.16.1 Pyomo for baseline + PySCIPOpt for advanced solver control

```text id="a8pc5c"
Workflow:
  1. formulate model in Pyomo
  2. validate data/model equations
  3. export LP/MPS/NL when possible
  4. rebuild critical production model in PySCIPOpt
  5. add callbacks/plugins/events
  6. compare objectives/solutions on small test instances
```

### 12.16.2 Pyomo outer loop + PySCIPOpt subproblem

```python id="dh84i2"
# Pyomo master solve
master_res = SolverFactory("scip").solve(master, load_solutions=False)

# PySCIPOpt custom callback-heavy subproblem
sub, sub_vars = build_pyscipopt_subproblem(data, master_solution)
sub.includeSepa(...)
sub.optimize()
```

### 12.16.3 PySCIPOpt incumbent generator + Pyomo production solve

```text id="km7xba"
Use PySCIPOpt:
  custom heuristic generates good incumbent

Use Pyomo:
  canonical algebraic model solves with standard settings

Need:
  solution transfer mechanism
  variable-name mapping
  feasibility validation
```

---

## 12.17 Testing and equivalence validation

### 12.17.1 Cross-interface golden tests

```text id="rhq1z3"
For each migrated model:
  tiny instance
  medium instance
  edge infeasible instance
  edge unbounded/bounds instance
  nonlinear/domain edge instance if applicable

Compare:
  objective value
  variable values
  feasibility residuals
  termination status
  gap
  model counts
```

### 12.17.2 Objective comparison helper

```python id="um7rs0"
def assert_close(a, b, tol=1e-7):
    if abs(a - b) > tol:
        raise AssertionError(f"{a=} {b=} differ by > {tol}")
```

### 12.17.3 Variable-name mapping rule

```text id="eqmx31"
Use deterministic names:
  Pyomo: symbolic_solver_labels=True
  PySCIPOpt: name=f"x[{i}]"

Avoid:
  anonymous variables
  generated names that change with Python dict order
```

---

## 12.18 Performance and deployment caveats

### 12.18.1 Python callback overhead

```text id="2w96kg"
PySCIPOpt callback/plugin code runs through Python.
Use care when:
  callback invoked at every LP node
  separator scans many rows
  event handler catches high-frequency events
  branching rule called repeatedly
  heuristic loops over huge candidate sets

Mitigate:
  low callback frequency
  precomputed data structures
  vectorized/numpy preprocessing outside callback
  C/C++ plugin for hot path
```

### 12.18.2 Version compatibility

```text id="78crmw"
Pin:
  pyscipopt
  scip
  python
  platform

Reason:
  PySCIPOpt wraps SCIP APIs
  latest PySCIPOpt is usually compatible with latest major SCIP
  plugin callback signatures may shift across major versions
```

The PySCIPOpt install information notes that package-manager installs include their own SCIP versions, and the PyPI/GitHub install guidance notes major-version compatibility between PySCIPOpt and SCIP. ([PySCIPOpt Documentation][2])

### 12.18.3 Packaging

```yaml id="vjowxc"
name: scip-native
channels:
  - conda-forge
channel_priority: strict
dependencies:
  - python=3.11
  - pyscipopt=6.1.0
  - scip=10.0.2
  - pytest
```

Use conda-forge-only strict channel priority for binary solver stacks; use lockfiles for production.

---

## 12.19 Common anti-patterns

```text id="8w6e6v"
Anti-pattern:
  use PySCIPOpt because Pyomo solve is slow without first profiling formulation.
Fix:
  inspect bounds, big-M, scaling, root gap, cuts, heuristics.

Anti-pattern:
  rewrite Pyomo model to PySCIPOpt and lose transformations.
Fix:
  preserve Pyomo if GDP/logical/piecewise transformations are central.

Anti-pattern:
  implement a Python separator that scans millions of variables at every node.
Fix:
  reduce frequency, precompute, or use C/C++.

Anti-pattern:
  expect PySCIPOpt model to be solver-portable.
Fix:
  PySCIPOpt is SCIP-specific; keep Pyomo model for portability.

Anti-pattern:
  mix Pyomo and PySCIPOpt variables in same expression.
Fix:
  build separate model objects; transfer only data/solutions.
```

---

## 12.20 Decision matrix

| Requirement                  | Stay Pyomo |        Switch PySCIPOpt | Native C/C++ |
| ---------------------------- | ---------: | ----------------------: | -----------: |
| algebraic clarity            |        yes |                   maybe |           no |
| solver portability           |        yes |                      no |           no |
| GDP/logical transformations  |        yes |                  manual |       manual |
| SCIP parameter tuning        |        yes |                     yes |          yes |
| read final gap/bounds        |        yes |                     yes |          yes |
| event handlers               |         no |                     yes |          yes |
| custom branching             |         no |                     yes |          yes |
| custom separator             |         no |                     yes |          yes |
| custom heuristic             |         no |                     yes |          yes |
| lazy constraints inside tree |         no |                     yes |          yes |
| direct solution pool         |         no |                     yes |          yes |
| column generation/pricer     |         no | maybe/version-dependent |          yes |
| highest callback performance |         no |                   maybe |          yes |
| existing Pyomo codebase      |        yes |      migration required | full rewrite |

---

## 12.21 Agent routing procedure

```text id="fxlg3o"
Given user request:

1. Identify needed control level.

2. If request only needs:
   model formulation
   solver choice
   Pyomo transformations
   SCIP options
   final results
   keepfiles/logging
   repeated external solves
   -> choose Pyomo.

3. If request needs:
   in-search callbacks
   event handlers
   custom branching
   custom cuts/separators
   lazy constraints
   custom heuristic
   direct solution pool
   direct SCIP model state
   -> choose PySCIPOpt.

4. If request needs:
   maximum callback performance
   plugin API not exposed by PySCIPOpt
   production compiled solver extension
   -> choose native SCIP C/C++.

5. Preserve a Pyomo reference model when:
   correctness validation
   solver comparison
   transformations
   documentation
   data/model separation
   long-term maintainability
```

---

## 12.22 Compact mental model

```text id="rymooz"
Pyomo:
  best modeling language layer
  solver-portable
  transformations
  data/model separation
  external SCIP solve via .nl

PySCIPOpt:
  best Python SCIP-control layer
  in-process Model
  direct params
  direct solution queries
  callbacks/plugins/events
  SCIP-specific

Native SCIP:
  best maximum-control/performance layer
  C/C++ plugins
  production-hot callbacks

Rule:
  Use Pyomo until you need SCIP internals.
  Use PySCIPOpt when you need SCIP internals from Python.
  Use C/C++ when Python callback overhead or API coverage is insufficient.
```

[1]: https://pyscipopt.readthedocs.io/?utm_source=chatgpt.com "PySCIPOpt Documentation — PySCIPOpt documentation"
[2]: https://pyscipopt.readthedocs.io/en/stable/install.html "Installation Guide — PySCIPOpt  documentation"
[3]: https://github.com/scipopt/PySCIPOpt "GitHub - scipopt/PySCIPOpt: Python interface for the SCIP Optimization Suite · GitHub"
[4]: https://pyscipopt.readthedocs.io/en/stable/tutorials/ "User Guide (Tutorials) — PySCIPOpt  documentation"
[5]: https://pyscipopt.readthedocs.io/en/latest/tutorials/eventhandler.html "Event Handlers — PySCIPOpt  documentation"
[6]: https://www.scipopt.org/?utm_source=chatgpt.com "SCIP"
[7]: https://www.pyomo.org/ "Pyomo"

# 13) Advanced SCIP 10 capabilities — exact MILP mode, new SCIP 10 features, and Pyomo access boundaries

Dense technical reference for LLM programming agents. Style aligned with the uploaded advanced-doc pattern. 

---

## 13.0 Capability boundary

```text id="ixx42w"
SCIP 10 advanced capability classes:
  exact MILP solving
  proof/certificate logging
  exact LP relaxation infrastructure
  rational instance readers
  implied-integrality presolving
  cut-based conflict analysis
  flower inequality separator
  infeasibility explanation tooling
  new nonlinear solver interface
  improved symmetry handling
  improved branching strategies
  improved Benders decomposition framework

Pyomo-facing access classes:
  A. accessible through normal Pyomo opt.options
  B. accessible only if conda/build exposes parameter and file path supports it
  C. accessible indirectly through formulation/logs/statistics
  D. requires PySCIPOpt or C/C++ native SCIP API
  E. not safely reachable through Pyomo’s .nl/AMPL path
```

SCIP 10’s headline additions include exact solving for rational MILPs, implied-integrality presolving, cut-based conflict analysis, a flower-inequality separator, infeasibility explanation tooling, a new nonlinear solver interface, and improvements in symmetry handling, branching, and Benders’ decomposition. ([optimization-online.org](https://optimization-online.org/2025/11/the-scip-optimization-suite-10-0/))

---

## 13.1 SCIP 10 exact MILP mode: purpose and mathematical contract

### 13.1.1 What exact mode is

```text id="rvhy53"
Exact mode:
  target problem class:
    rational MILP

  arithmetic:
    rational arithmetic
    extended precision
    safe floating-point with directed rounding where used

  objective:
    eliminate unsafe floating-point roundoff influence
    solve without numerical tolerances
    optionally emit independently checkable proof/certificate
```

SCIP’s exact-mode documentation says exact mode solves mixed-integer linear programs using rational, extended-precision, and safe floating-point computation so results are not affected by unsafe floating-point roundoff; the SCIP 10 report states exact mode targets MILPs with rational input data and no numerical tolerances. ([scipopt.org](https://www.scipopt.org/doc-10.0.0/html/EXACT.php))

### 13.1.2 What exact mode is not

```text id="bg6yfu"
Not a general exact MINLP mode.
Not a general exact nonlinear mode.
Not a guarantee that every file reader path is exact.
Not a guarantee that every plugin/cut/heuristic is usable.
Not automatically active just because SCIP version is 10.
Not automatically certifying unless certificate logging is enabled.
```

The SCIP 10 report explicitly says exact solving mode is restricted to mixed-integer linear programs. ([arxiv.org](https://arxiv.org/html/2511.18580v1))

---

## 13.2 Exact mode build-time dependencies

### 13.2.1 Required components

```text id="m2x651"
Exact mode build requirements:
  GMP:
    rational arithmetic in ZIMPL, SoPlex, SCIP, PaPILO

  Boost multiprecision:
    rationals in SCIP and optionally PaPILO

  MPFR:
    rational-to-floating approximations in SCIP

  exact LP solver:
    e.g. SoPlex
```

SCIP’s exact-mode how-to lists GMP, Boost multiprecision, MPFR, and an exact LP solver such as SoPlex as requirements. ([scipopt.org](https://www.scipopt.org/doc-10.0.0/html/EXACT.php))

### 13.2.2 Conda binary implication

```text id="fy3kk9"
conda-forge::scip gives:
  SCIP executable/package
  current package version 10.0.2
  platform binaries for Linux, Windows, macOS Intel, macOS ARM, Linux ARM

conda-forge package metadata alone does not prove:
  exact mode enabled
  certificate logging usable
  exact reader behavior for your file path
  proof checker installed
```

The conda-forge `scip` package page lists version 10.0.2, install command, license expression, and supported platforms, but not a per-build exact-mode feature matrix. ([anaconda.org](https://anaconda.org/conda-forge/scip))

### 13.2.3 Runtime verification required

```bash id="tvxd3y"
scip --version

# Save installed parameter list and search exact/certificate settings
scip <<'EOF'
set save scip-all.set
quit
EOF

grep -i '^exact/' scip-all.set || true
grep -i '^certificate/' scip-all.set || true
```

Authoritative rule:

```text id="lvvija"
If exact/certificate parameters are absent or rejected:
  installed binary/build does not expose the feature as expected,
  or exact parameters are hidden behind build/runtime conditions,
  or parameter spelling differs across docs/build.

Do not claim exact mode works until a tiny exact-mode solve succeeds.
```

---

## 13.3 Exact mode activation syntax

### 13.3.1 Standalone SCIP

```text id="8du4k9"
SCIP> set exact enable TRUE
SCIP> read model.lp
SCIP> optimize
```

SCIP’s exact-mode how-to says exact solving is enabled by setting `exact/enable = TRUE` or calling `SCIPenableExactSolving()`, and it must be done before reading or creating the problem. ([scipopt.org](https://www.scipopt.org/doc-10.0.0/html/EXACT.php))

### 13.3.2 Settings file

```text id="h1v9ne"
# scip-exact.set
exact/enable = TRUE
certificate/filename = proof.vipr
```

Certificate logging is enabled by specifying `certificate/filename`; SCIP produces a VIPR certificate that can be checked by VIPR or a formally verified CakeML checker, with the caveat that certificates are incomplete if cutting-plane separation is enabled by default and must be completed with `viprcomp` before verification. ([scipopt.org](https://www.scipopt.org/doc-10.0.0/html/EXACT.php))

### 13.3.3 Pyomo option attempt

```python id="lcq4f9"
from pyomo.environ import SolverFactory

opt = SolverFactory("scip", solver_io="nl")
opt.options["exact/enable"] = "TRUE"
opt.options["certificate/filename"] = "proof.vipr"

res = opt.solve(
    model,
    tee=True,
    logfile="scip-exact-attempt.log",
    keepfiles=True,
    symbolic_solver_labels=True,
    load_solutions=False,
)
```

Critical caveat:

```text id="vo93dp"
Pyomo passes these options by writing them into a temporary scip.set.
This can set SCIP parameters before SCIP reads the .nl problem.
But exact mode is still not guaranteed through Pyomo because:
  Pyomo transport is AMPL .nl
  SCIP 10 report lists exact readers for MPS, LP, CIP, OPB/WBO, and ZIMPL, not AMPL .nl
  exact mode is MILP-only
  Pyomo model may contain nonlinear/quadratic/general expressions
  certificate path is relative to SCIP working directory unless absolute
```

Pyomo’s SCIP plugin writes `opt.options` to a temporary `scip.set`, warns that a local `scip.set` will be ignored, and launches `scip <problem> -AMPL`; the SCIP 10 report says exact reader extensions exist for MPS, LP, CIP, OPB/WBO, and ZIMPL, and it does not list AMPL `.nl` in that exact-reader list. ([pyomo.readthedocs.io](https://pyomo.readthedocs.io/en/6.8.2/_modules/pyomo/solvers/plugins/solvers/SCIPAMPL.html))

---

## 13.4 Exact instance readers and Pyomo `.nl` caveat

### 13.4.1 Exact-supported readers named in SCIP 10 report

```text id="6xczdl"
Exact readers extended in SCIP 10:
  MPS
  LP
  CIP
  OPB/WBO
  ZIMPL
```

The SCIP 10 report says these readers were extended to read problem instances in exact arithmetic and parse bounds/coefficients as rational numbers. ([arxiv.org](https://arxiv.org/html/2511.18580v1))

### 13.4.2 Pyomo `.nl` status

```text id="h95zm1"
Pyomo SolverFactory("scip"):
  default/only problem format: .nl
  execution mode: scip model -AMPL

Exact-reader list from SCIP 10 report:
  does not include .nl / AMPL NL in the exact-reader sentence

Agent conclusion:
  exact MILP verification workflows should prefer standalone SCIP with LP/MPS/CIP/OPB/WBO/ZIMPL input,
  not Pyomo .nl, unless explicitly validated on the installed SCIP build and target model.
```

---

## 13.5 Exact LP relaxation infrastructure

### 13.5.1 Native mechanics

```text id="vxhbrd"
SCIP 10 exact LP infrastructure:
  floating-point LP approximation maintained
  rational exact LP structure maintained
  exact LP solver interface
  SoPlex default exact LP solver
  QSopt_ex possible exact LP solver
  exact LP solver called as fallback or at selected situations
```

The SCIP 10 report says SCIP 10 adds an exact LP structure managing a rational version of the LP relaxation; the exact LP solver interface can use SoPlex or QSopt_ex, and SoPlex is the default exact LP solver in SCIP 10. ([arxiv.org](https://arxiv.org/html/2511.18580v1))

### 13.5.2 Why this matters

```text id="ttevfm"
Normal floating-point branch-and-bound:
  LP bound is approximate
  feasibility/integrality use tolerances
  proof is not independently certifiable

Exact MILP branch-and-bound:
  rational problem data
  safe dual bounding
  exact or safely certified LP relaxation bounds
  exact zero gap proof target
```

### 13.5.3 Performance implication

```text id="ksj68l"
Expect exact mode to be slower.
Use exact mode for:
  audit
  certification
  numerical fragility
  solver correctness research
  proof artifacts

Do not use exact mode for:
  routine production throughput
  general MINLP
  approximate planning decisions
  huge models without proof requirements
```

The SCIP 10 report notes exact solving introduces significant overhead and gives computational comparisons showing exact mode solves fewer instances and is slower than floating-point settings on benchmark subsets. ([arxiv.org](https://arxiv.org/html/2511.18580v1))

---

## 13.6 Certificate / proof concepts

### 13.6.1 Certificate meaning

```text id="4pwbeh"
Certificate:
  exact problem statement
  optimal solution
  claimed primal and dual bounds
  derivation proving optimality
  branch-and-bound reasoning encoded in VIPR format
```

The SCIP 10 report states certificate files contain the exact problem statement, an optimal solution with claimed primal/dual bounds, and a derivation section certifying optimality. ([arxiv.org](https://arxiv.org/html/2511.18580v1))

### 13.6.2 Native syntax

```text id="vhp4ms"
SCIP> set exact enable TRUE
SCIP> set certificate filename proof.vipr
SCIP> read model.lp
SCIP> optimize
```

or:

```text id="gyskk4"
# scip.set
exact/enable = TRUE
certificate/filename = /absolute/path/proof.vipr
```

### 13.6.3 Certificate caveats

```text id="bzgwxa"
Certificates:
  certify LP-based branch-and-cut process after presolving
  may require completion if cutting-plane separation enabled
  require external proof checker for independent verification
  are incomplete if not all relevant proof components are logged/completed
```

SCIP’s exact-mode how-to notes certificate files are incomplete if cutting-plane separation is enabled by default and must be completed with `viprcomp` prior to verification. ([scipopt.org](https://www.scipopt.org/doc-10.0.0/html/EXACT.php))

---

## 13.7 Pyomo exact-mode access matrix

| Feature                      |                 Through conda binary? |         Through Pyomo `opt.options`? |        Through Pyomo `.nl` reliably? |              Native/PySCIPOpt/C needed? | Agent verdict                              |
| ---------------------------- | ------------------------------------: | -----------------------------------: | -----------------------------------: | --------------------------------------: | ------------------------------------------ |
| SCIP 10 executable           |       yes, `conda-forge::scip=10.0.2` |                                  n/a |               yes as external solver |                                      no | normal Pyomo solve OK                      |
| exact-mode parameter setting |                   maybe; verify build |    yes, string option can be written |                            uncertain | no for setting, yes for robust workflow | test on tiny instance                      |
| exact rational MILP solving  |        maybe; verify exact build/deps |                                maybe |           not recommended as default |             standalone/native preferred | use LP/MPS/CIP/OPB/WBO/ZIMPL               |
| certificate output           | maybe; verify parameter/file creation |                                maybe |            uncertain path/cwd issues |             standalone/native preferred | use absolute paths and verify file         |
| exact readers                |                 yes if build supports |                                  n/a | `.nl` not listed in exact-reader set |             standalone/native preferred | avoid Pyomo `.nl` for certified exact runs |
| exact LP solver selection    |                       build-dependent | maybe via exact/lp params if present |                            uncertain |               native for robust control | inspect `set save`                         |
| plugin exact-safety flags    |                     build/API concept |                                   no |                                   no |                                     yes | C/C++ native/plugin path                   |
| proof checker                |   not necessarily installed by `scip` |                                   no |                                   no |                    external VIPR/CakeML | install/check separately                   |

---

## 13.8 Runtime exact-mode smoke test

### 13.8.1 Tiny rational MILP file

```bash id="d7sd07"
cat > tiny_exact.lp <<'EOF'
Maximize
 obj: x + y
Subject To
 c1: 2 x + 3 y <= 4
Bounds
 0 <= x <= 1
 0 <= y <= 1
Binary
 x y
End
EOF
```

### 13.8.2 Standalone exact run

```bash id="jiyufv"
cat > run_exact.scip <<'EOF'
set exact enable TRUE
set certificate filename proof.vipr
read tiny_exact.lp
optimize
display solution
display statistics
quit
EOF

scip < run_exact.scip > exact.log 2>&1

grep -i exact exact.log || true
grep -i certificate exact.log || true
ls -l proof.vipr || true
```

### 13.8.3 Pass/fail criteria

```text id="dpc8cy"
Pass:
  exact mode accepted
  model read after exact enable
  solve terminates
  certificate file exists if requested
  log does not contain unsupported exact mode warning

Fail:
  unknown parameter exact/enable
  exact mode unsupported by build
  certificate parameter rejected
  certificate path not created
  file reader not exact-compatible
```

---

## 13.9 Pyomo exact-mode smoke test: cautious

```python id="42i2zb"
from pyomo.environ import *

m = ConcreteModel()
m.x = Var(domain=Binary)
m.y = Var(domain=Binary)
m.obj = Objective(expr=m.x + m.y, sense=maximize)
m.c1 = Constraint(expr=2*m.x + 3*m.y <= 4)

opt = SolverFactory("scip", solver_io="nl")
opt.options["exact/enable"] = "TRUE"
opt.options["certificate/filename"] = "/absolute/path/proof-pyomo.vipr"

res = opt.solve(
    m,
    tee=True,
    logfile="pyomo-exact-attempt.log",
    keepfiles=True,
    symbolic_solver_labels=True,
    load_solutions=False,
)
```

Agent interpretation:

```text id="4fe2ew"
If this succeeds:
  exact parameter accepted through Pyomo option transport
  SCIP handled Pyomo-generated .nl in this run

Still verify:
  log says exact mode was active
  generated file was a MILP
  certificate file exists and verifies
  result matches standalone LP/MPS exact run

Do not generalize to all Pyomo models.
```

---

## 13.10 Implied-integrality presolver

### 13.10.1 Concept

```text id="wsw62y"
Implied integrality:
  a variable declared continuous is forced integral by constraints + other integer variables
  solver can exploit this to strengthen model/search
  may reduce branching burden
  may improve presolve and relaxation handling
```

SCIP 10 added a new presolver for detecting implied integral variables; the parameter list exposes `presolving/implint/*` controls such as priority, maxrounds, timing, convertintegers, and numericslimit. ([optimization-online.org](https://optimization-online.org/2025/11/the-scip-optimization-suite-10-0/))

### 13.10.2 Pyomo access

```python id="nr2aub"
opt.options["presolving/implint/maxrounds"] = -1
opt.options["presolving/implint/convertintegers"] = "FALSE"
opt.options["presolving/implint/numericslimit"] = 100000000
```

The SCIP 10.0.2 parameter list shows `presolving/implint/maxrounds` defaulting to `0`, `convertintegers` defaulting to `FALSE`, and `numericslimit` defaulting to `100000000`. ([scipopt.org](https://www.scipopt.org/doc/html/PARAMETERS.php))

### 13.10.3 Pyomo value case

```text id="3esozz"
Use/experiment when:
  model has network matrices
  continuous flow variables become integral through structure
  integer declarations may be redundant
  root relaxation unexpectedly integral
  MIP model generated by transformations

Stay cautious:
  default maxrounds=0 in parameter list
  enabling can add presolve time
  numerics/scale matter
```

---

## 13.11 Cut-based conflict analysis

### 13.11.1 Concept

```text id="waz42j"
Conflict analysis:
  learn from infeasible subproblems
  derive constraints/clauses/cuts preventing repeated infeasible search
  improve pruning
```

SCIP 10’s report summary lists cut-based conflict analysis as a novel SCIP 10 feature. ([optimization-online.org](https://optimization-online.org/2025/11/the-scip-optimization-suite-10-0/))

### 13.11.2 Pyomo access class

```text id="bidq21"
Pyomo:
  indirect only through SCIP default behavior and conflict-related parameters
  no callback/control surface for conflict analysis internals
  inspect table/conflict statistics in log

Native/PySCIPOpt/C:
  needed for custom conflict analysis plugins or event-level inspection
```

### 13.11.3 Logging

```python id="go9vmc"
opt.options["display/relevantstats"] = "TRUE"
opt.options["table/conflict/active"] = "TRUE"
opt.options["display/verblevel"] = 5
```

---

## 13.12 Flower inequalities

### 13.12.1 Concept

```text id="m8r9zh"
Flower inequalities:
  separator plugin introduced in SCIP 10
  derived from multilinear/product-structure problems
  targeted at strengthening relaxations involving AND/product hypergraph structures
```

SCIP 10’s report summary lists a new separator for flower inequalities, and the SCIP 10.0.2 parameter list exposes `separating/flower/*` parameters including priority, frequency, scan options, and maximum numbers of flower inequalities per cut round. ([optimization-online.org](https://optimization-online.org/2025/11/the-scip-optimization-suite-10-0/))

### 13.12.2 Pyomo access

```python id="0qzlfz"
opt.options["separating/flower/freq"] = 1
opt.options["separating/flower/scanand"] = "TRUE"
opt.options["separating/flower/scanproduct"] = "FALSE"
opt.options["separating/flower/maxoneflower"] = 10000000
opt.options["separating/flower/maxtwoflower"] = 10000000
```

The parameter list shows `separating/flower/freq`, `scanand`, `scanproduct`, `maxoneflower`, and `maxtwoflower`, with `freq=1`, `scanand=TRUE`, `scanproduct=FALSE`, and large max-one/two-flower defaults. ([scipopt.org](https://www.scipopt.org/doc/html/PARAMETERS.php))

### 13.12.3 Pyomo value case

```text id="76of4f"
Potentially useful when:
  Pyomo model contains binary-product structure
  nonlinear binary products reformulated by SCIP
  AND-constraint-like structure exists
  multilinear terms occur in transformed MINLP

Need evidence:
  enable separator table
  inspect cuts generated
  compare root bound/gap/nodes
```

Logging:

```python id="rv35op"
opt.options["display/relevantstats"] = "TRUE"
opt.options["table/separator/active"] = "TRUE"
opt.options["table/cutsel/active"] = "TRUE"
```

---

## 13.13 Infeasibility explanation tooling

### 13.13.1 Concept

```text id="ndiu0w"
Infeasibility explanation:
  identify/explain infeasibility
  IIS-style or irreducible infeasible subsystem tooling
  debugging aid, not just optimization solve result
```

The SCIP 10 summary states SCIP 10 adds a novel tool for explaining infeasibility. ([optimization-online.org](https://optimization-online.org/2025/11/the-scip-optimization-suite-10-0/))

### 13.13.2 Pyomo-facing status

```text id="qcuwhk"
Pyomo SolverFactory("scip"):
  returns infeasible termination and log
  can keep .nl/.row/.col for mapping
  does not expose SCIP infeasibility explanation API as a Pyomo method

Use:
  Pyomo infeasibility utilities for model-level diagnostics
  standalone SCIP or native API for SCIP 10 explanation tooling
  PySCIPOpt/C if API exposure is needed
```

PySCIPOpt’s tutorial index includes an “Irreducible Infeasible Subsets” tutorial, making PySCIPOpt the more appropriate Python side path for solver-native infeasibility explanation work. ([pyscipopt.readthedocs.io](https://pyscipopt.readthedocs.io/en/stable/tutorials/))

### 13.13.3 Pyomo debug scaffold

```python id="a2o7k8"
res = opt.solve(
    model,
    tee=True,
    logfile="infeasible-scip.log",
    keepfiles=True,
    symbolic_solver_labels=True,
    load_solutions=False,
)

from pyomo.util.infeasible import log_infeasible_constraints
log_infeasible_constraints(model, log_expression=True, log_variables=True)
```

---

## 13.14 New nonlinear solver interface

### 13.14.1 Concept

```text id="4am84j"
SCIP 10 nonlinear solver interface:
  native SCIP-side interface for nonlinear solvers
  relevant to MINLP/NLP relaxation handling
  plugin/interface-level improvement
```

SCIP 10’s summary lists a new interface for nonlinear solvers among major SCIP 10 updates. ([optimization-online.org](https://optimization-online.org/2025/11/the-scip-optimization-suite-10-0/))

### 13.14.2 Pyomo access

```text id="x1l87h"
Pyomo can:
  send nonlinear model through .nl to SCIP
  tune nonlinear constraint-handler parameters
  read final log/result fields

Pyomo cannot:
  select/implement native nonlinear solver interface components directly
  inspect nonlinear solver callback state
  attach custom nonlinear solver interface plugin
```

Relevant Pyomo-tunable native keys:

```python id="ngcwzy"
opt.options["constraints/nonlinear/maxproprounds"] = 10
opt.options["constraints/nonlinear/reformbinprods"] = "TRUE"
opt.options["constraints/nonlinear/reformbinprodsand"] = "TRUE"
opt.options["constraints/nonlinear/weakcutthreshold"] = 0.2
opt.options["constraints/nonlinear/branching/external"] = "FALSE"
```

SCIP’s parameter list exposes many `constraints/nonlinear/*` settings, including propagation rounds, binary-product reformulation, weak-cut threshold, and nonlinear branching controls. ([scipopt.org](https://www.scipopt.org/doc/html/PARAMETERS.php))

---

## 13.15 Symmetry improvements

### 13.15.1 Concept

```text id="3aljzc"
Symmetry handling:
  detect symmetric variables/constraints
  add symmetry-breaking constraints
  reduce equivalent branch-and-bound subtrees
  improve memory and node count
```

The SCIP 10 summary names improvements in symmetry handling; the SCIP homepage also lists symmetry-handling dependencies/build flags such as dejavu/sassy/nauty/bliss under SCIP dependencies. ([optimization-online.org](https://optimization-online.org/2025/11/the-scip-optimization-suite-10-0/))

### 13.15.2 Pyomo access

```text id="ib164s"
Pyomo:
  indirect via built-in SCIP symmetry handling
  expose symmetry by clean variable/index structure
  avoid arbitrary naming/order nondeterminism where possible
  inspect presolve/statistics/logs
```

Potential parameters are build/version-specific; use:

```bash id="l8ius3"
scip <<'EOF'
set save scip-all.set
quit
EOF

grep -i symmetry scip-all.set
grep -i sym scip-all.set
```

### 13.15.3 Modeling guidance

```text id="nvr4ip"
If symmetry is harming search:
  add domain-specific symmetry-breaking constraints manually
  sort interchangeable objects
  fix representative variable/order
  use Pyomo constraints for lexicographic/ordering symmetry breaks
```

---

## 13.16 Branching improvements

### 13.16.1 Concept

```text id="x08k7n"
SCIP 10 branching improvements:
  improved default tree behavior
  branching strategy upgrades
  exact-mode reliability pseudocost path
  nonlinear branching controls
```

The SCIP 10 summary lists branching-strategy improvements, and the exact-mode section states reliability pseudocost branching is the exact branching rule made exact in SCIP 10. ([optimization-online.org](https://optimization-online.org/2025/11/the-scip-optimization-suite-10-0/))

### 13.16.2 Pyomo access

```python id="dcr8wm"
opt.options["branching/preferbinary"] = "TRUE"
opt.options["branching/scorefunc"] = "p"

# reliability pseudocost controls
opt.options["branching/relpscost/minreliable"] = 1
opt.options["branching/relpscost/maxreliable"] = 5

# nonlinear branching controls
opt.options["constraints/nonlinear/branching/fracweight"] = 1
opt.options["constraints/nonlinear/branching/pscostweight"] = 1
opt.options["constraints/nonlinear/branching/domainweight"] = 0
```

### 13.16.3 Native-only boundary

```text id="r9zq93"
Custom branching rule:
  requires PySCIPOpt or C/C++
  not Pyomo SolverFactory("scip")
```

---

## 13.17 Benders improvements

### 13.17.1 Concept

```text id="lyjdv5"
Benders decomposition:
  master problem
  subproblems
  Benders cuts
  decomposition-aware solve process
```

The SCIP 10 summary lists improvements in SCIP’s Benders’ decomposition framework. ([optimization-online.org](https://optimization-online.org/2025/11/the-scip-optimization-suite-10-0/))

### 13.17.2 Pyomo access

```text id="z7ffwd"
Pyomo SolverFactory("scip"):
  no direct Benders plugin registration
  no subproblem callback inside SCIP
  can implement outer-loop Benders manually in Pyomo
  can tune SCIP parameters for the resulting master MILP/MINLP

Native/PySCIPOpt/C:
  needed for SCIP-native Benders framework control
```

Outer-loop Pyomo sketch:

```python id="1b90lu"
while True:
    res = master_opt.solve(master, load_solutions=False)
    master.solutions.load_from(res)

    sub_results = solve_subproblems_from_master(master)

    if all_ok(sub_results):
        break

    add_benders_cuts(master, sub_results)
```

---

## 13.18 Conda binary accessibility: what to verify

### 13.18.1 Package-level facts

```text id="f3wwex"
conda-forge::scip:
  version: 10.0.2
  install: conda install conda-forge::scip
  supported platforms:
    linux-aarch64
    win-64
    macOS-64
    macOS-arm64
    linux-64
```

The conda-forge page provides these package facts and license metadata. ([anaconda.org](https://anaconda.org/conda-forge/scip))

### 13.18.2 Feature probes

```bash id="fbge4i"
# 1. Version
scip --version

# 2. Installed parameter inventory
scip <<'EOF'
set save scip-all.set
quit
EOF

# 3. Exact/certificate search
grep -i '^exact/' scip-all.set || true
grep -i '^certificate/' scip-all.set || true

# 4. SCIP 10 feature parameter probes
grep -i '^presolving/implint/' scip-all.set || true
grep -i '^separating/flower/' scip-all.set || true
grep -i '^constraints/nonlinear/' scip-all.set | head -50 || true
grep -i 'benders' scip-all.set || true
grep -i 'sym' scip-all.set || true
```

### 13.18.3 Runtime probe via Python

```python id="d7c4bp"
import subprocess
from pathlib import Path

def scip_parameter_dump(path="scip-all.set"):
    script = "set save {}\nquit\n".format(path)
    p = subprocess.run(
        ["scip"],
        input=script,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return p.returncode, p.stdout, Path(path).read_text(errors="replace")

code, out, params = scip_parameter_dump()
for token in ["presolving/implint/", "separating/flower/", "constraints/nonlinear/"]:
    print(token, token in params)
```

---

## 13.19 Pyomo access matrix for SCIP 10 features

| SCIP 10 feature               |            Pyomo via `opt.options` |                            Pyomo via formulation |         Pyomo via logs |                 PySCIPOpt/native needed | Notes                                       |
| ----------------------------- | ---------------------------------: | -----------------------------------------------: | ---------------------: | --------------------------------------: | ------------------------------------------- |
| exact MILP mode               |              maybe: `exact/enable` | only if model exports exact-compatible MILP path |        yes, verify log |   recommended for robust exact workflow | `.nl` exact-reader caveat                   |
| certificate output            |      maybe: `certificate/filename` |                                               no |        file/log verify |                             recommended | use absolute certificate path               |
| implied-integrality presolver |        yes: `presolving/implint/*` |                            model structure helps |         presolve stats |                        no unless custom | parameter default may be off                |
| cut-based conflict analysis   |            limited/conflict params |                    formulation affects conflicts |         conflict table |           yes for custom conflict logic | indirect in Pyomo                           |
| flower inequalities           |         yes: `separating/flower/*` |               binary/multilinear structure helps |        separator table |              no unless custom separator | useful to benchmark                         |
| infeasibility explanations    |             no direct Pyomo method |               Pyomo IIS-style utilities separate |          log/artifacts | yes for native SCIP explanation tooling | PySCIPOpt IIS path likely better            |
| nonlinear solver interface    | limited: `constraints/nonlinear/*` |                        nonlinear modeling/bounds |    NLP/nonlinear stats |               yes for interface plugins | Pyomo cannot attach nonlinear solver plugin |
| symmetry improvements         |                parameter-dependent |                add symmetry-breaking constraints | presolve/symmetry logs |                 native for deep control | use `set save` to find sym params           |
| branching improvements        |              yes: branching params |                          expose better variables |             tree stats | custom branch rule requires PySCIPOpt/C | Pyomo cannot implement branch rule          |
| Benders improvements          |                   no direct plugin |                      outer-loop Benders in Pyomo |               log only |          yes for SCIP Benders framework | Pyomo loop != native SCIP Benders           |

---

## 13.20 Recommended exact-mode workflow

### 13.20.1 Preferred certified exact workflow

```text id="m6sbyh"
1. Build/obtain MILP in exact-supported file format:
   LP, MPS, CIP, OPB/WBO, or ZIMPL.

2. Verify SCIP exact mode exists:
   scip --version
   set save scip-all.set
   test exact/enable on tiny MILP.

3. Run standalone SCIP:
   set exact enable TRUE
   set certificate filename /abs/path/proof.vipr
   read model.lp
   optimize

4. Verify:
   exact mode active in log
   optimality proven
   certificate created
   certificate completed if needed
   proof checker accepts certificate

5. Archive:
   input file
   scip.set
   scip.log
   proof.vipr
   proof-checker output
   SCIP version
   package lockfile
```

### 13.20.2 Pyomo-assisted exact workflow

```text id="vfb01w"
Use Pyomo only to generate an LP/MPS-like MILP artifact if equivalent and exact-reader-compatible.

Avoid relying on .nl for certification unless validated.

Workflow:
  Pyomo model -> export LP/MPS if representable
  standalone exact SCIP -> certificate
```

Pyomo export:

```python id="9fbnia"
model.write(
    "model.lp",
    format="lp",
    io_options={"symbolic_solver_labels": True, "file_determinism": 30},
)
```

Standalone exact SCIP:

```text id="2y4x4e"
SCIP> set exact enable TRUE
SCIP> set certificate filename proof.vipr
SCIP> read model.lp
SCIP> optimize
```

---

## 13.21 Advanced SCIP 10 feature presets through Pyomo

### 13.21.1 Implied-integrality exploration preset

```python id="kvv09a"
def scip10_profile_implint(opt):
    opt.options["presolving/implint/maxrounds"] = -1
    opt.options["presolving/implint/convertintegers"] = "FALSE"
    opt.options["presolving/implint/numericslimit"] = 100000000

    opt.options["display/verblevel"] = 5
    opt.options["display/relevantstats"] = "TRUE"
    opt.options["table/presolver/active"] = "TRUE"
    return opt
```

### 13.21.2 Flower separator exploration preset

```python id="wz9koc"
def scip10_profile_flower(opt):
    opt.options["separating/flower/freq"] = 1
    opt.options["separating/flower/scanand"] = "TRUE"
    opt.options["separating/flower/scanproduct"] = "TRUE"
    opt.options["separating/flower/maxoneflower"] = 10000000
    opt.options["separating/flower/maxtwoflower"] = 10000000

    opt.options["display/relevantstats"] = "TRUE"
    opt.options["table/separator/active"] = "TRUE"
    opt.options["table/cutsel/active"] = "TRUE"
    return opt
```

### 13.21.3 Nonlinear SCIP 10 debug preset

```python id="n0ykd6"
def scip10_profile_nonlinear_debug(opt):
    opt.options["constraints/nonlinear/maxproprounds"] = 20
    opt.options["constraints/nonlinear/reformbinprods"] = "TRUE"
    opt.options["constraints/nonlinear/reformbinprodsand"] = "TRUE"
    opt.options["constraints/nonlinear/weakcutthreshold"] = 0.1
    opt.options["constraints/nonlinear/branching/external"] = "FALSE"

    opt.options["display/verblevel"] = 5
    opt.options["display/relevantstats"] = "TRUE"
    opt.options["table/nlp/active"] = "TRUE"
    opt.options["table/constraint/active"] = "TRUE"
    return opt
```

---

## 13.22 Version and spelling guardrails

```text id="ghgrof"
Parameter spelling must be checked against installed SCIP:
  official exact how-to uses:
    exact/enable

  SCIP 10 report text mentions:
    exact/enabled

Agent rule:
  use official exact-mode how-to spelling first:
    exact/enable
  if rejected:
    search installed parameter dump:
      grep -i exact scip-all.set
    or use shell completion/menu:
      SCIP> set exact
```

The official exact-mode how-to says `exact/enable = TRUE`; the SCIP 10 report text uses `exact/enabled` in prose, so installed-binary verification is mandatory for robust agents. ([scipopt.org](https://www.scipopt.org/doc-10.0.0/html/EXACT.php))

---

## 13.23 When normal floating-point SCIP remains appropriate

```text id="eh7xm8"
Use normal SCIP for:
  most Pyomo MILP/MINLP runs
  routine production optimization
  time-limited planning
  heuristic/incumbent workflows
  general nonlinear models
  large MIPs where proof certificate not required
  models with non-rational or generated floating data

Use exact SCIP for:
  rational MILP
  audit/certification
  numerical fragility
  independently checkable proof requirement
  solver research / correctness benchmarks
```

SCIP exact mode is designed to solve rational MILPs without numerical tolerances and optionally provide certificates; floating-point SCIP remains the primary performance-oriented mode. ([arxiv.org](https://arxiv.org/html/2511.18580v1))

---

## 13.24 Failure modes and diagnostics

| Symptom                                             | Likely cause                                                | Probe                           | Fix                                                         |
| --------------------------------------------------- | ----------------------------------------------------------- | ------------------------------- | ----------------------------------------------------------- |
| `unknown parameter exact/enable`                    | binary lacks exact feature or spelling mismatch             | `set save`, `grep exact`        | verify build; try official docs; use source build if needed |
| certificate file absent                             | parameter rejected, relative path in temp cwd, solve failed | log search, absolute path       | use absolute `certificate/filename`, standalone run         |
| exact Pyomo run succeeds but not certifiable        | `.nl` exact-reader caveat                                   | compare standalone LP/MPS exact | export LP/MPS and run standalone                            |
| exact run rejects model                             | not MILP or unsupported reader                              | model degree/export check       | simplify to MILP, use supported reader                      |
| exact run very slow                                 | expected overhead                                           | compare floating run            | use exact only for audit/proof                              |
| flower separator no effect                          | no relevant structure or scan options                       | separator table                 | enable scanproduct; compare root bound                      |
| implint no effect                                   | structure absent or presolver off/default maxrounds=0       | presolver table                 | enable maxrounds and inspect presolve log                   |
| infeasibility explanation unavailable through Pyomo | no Pyomo API                                                | Pyomo docs/API                  | use standalone/PySCIPOpt/native                             |
| Benders improvements not visible                    | Pyomo not using native Benders framework                    | model/log                       | implement native/PySCIPOpt/GCG route                        |

---

## 13.25 Compact mental model

```text id="xjwwcb"
SCIP 10 exact mode:
  rational MILP only
  exact/enable before reading
  needs GMP + Boost + MPFR + exact LP solver
  SoPlex is default exact LP solver
  certificate/filename writes VIPR proof
  exact readers include MPS, LP, CIP, OPB/WBO, ZIMPL
  Pyomo .nl exact certification is not the safe default path

SCIP 10 new features:
  implint presolver -> presolving/implint/*
  flower separator -> separating/flower/*
  nonlinear improvements -> constraints/nonlinear/*
  conflict/infeasibility/symmetry/branching/Benders improvements mostly indirect in Pyomo

Pyomo access:
  opt.options can set exposed SCIP parameters
  Pyomo writes temporary scip.set before SCIP reads model
  Pyomo cannot expose SCIP-native plugin APIs
  use PySCIPOpt/C for callbacks, Benders framework, custom plugins, event-level control

Conda access:
  conda-forge::scip gives SCIP 10.0.2 binary
  verify advanced feature availability at runtime
  do not infer exact/certificate readiness from version number alone
```

# 14) Performance tuning playbook — SCIP through Pyomo

Dense technical reference for LLM programming agents. Style aligned with the uploaded advanced-doc pattern. 

---

## 14.0 Tuning control plane

```text id="w6ur12"
Pyomo control surface:
  opt = SolverFactory("scip", solver_io="nl")
  opt.options["limits/time"] = ...
  opt.options["limits/gap"] = ...
  res = opt.solve(model, tee=True, logfile="scip.log", load_solutions=False)

SCIP control surface:
  slash-separated parameters:
    limits/*
    presolving/*
    separating/*
    heuristics/*
    branching/*
    constraints/*
    lp/*
    numerics/*
    randomization/*
    parallel/*

Native SCIP meta-settings:
  SCIPsetPresolving(DEFAULT | FAST | AGGRESSIVE | OFF)
  SCIPsetHeuristics(DEFAULT | FAST | AGGRESSIVE | OFF)
  SCIPsetSeparating(DEFAULT | FAST | AGGRESSIVE | OFF)

Pyomo limitation:
  cannot call SCIPsetPresolving / SCIPsetHeuristics / SCIPsetSeparating directly;
  must use concrete SCIP parameter keys or tune in standalone SCIP/PySCIPOpt and port diff settings.
```

Pyomo’s SCIP interface writes `opt.options` as `key = value` lines into a temporary `scip.set`, maps `timelimit` to `limits/time` only when `limits/time` is absent, and launches SCIP as an external `scip ... -AMPL` process. ([Pyomo Documentation][1]) SCIP’s native `SCIPsetPresolving`, `SCIPsetHeuristics`, and `SCIPsetSeparating` support `DEFAULT`, `FAST`, `AGGRESSIVE`, and `OFF` modes; Pyomo does not expose these C calls directly. ([SCIP Optimization Library][2])

---

## 14.1 Tuning objectives: choose one primary target

```text id="ewyox5"
Primary objective classes:
  A. fast feasible solution
  B. strong proof of optimality
  C. memory reduction
  D. aggressive presolve / model reduction
  E. numerical stability
  F. nonlinear robustness

Anti-pattern:
  tune for all objectives simultaneously.
```

| Objective              | Optimize for                                              | Typical tradeoff                                      |
| ---------------------- | --------------------------------------------------------- | ----------------------------------------------------- |
| fast feasible solution | incumbent speed, solution count, heuristic effort         | weaker proof, larger gap                              |
| strong proof           | root bound, cuts, presolve, dual bound, node reduction    | slower first incumbent, larger root time              |
| memory reduction       | cut pool size, LP row count, tree size, log size          | weaker relaxation, more nodes                         |
| aggressive presolve    | reductions, tightening, aggregation                       | more front-loaded time, harder original-row mapping   |
| numerical stability    | scaling, bounds, tolerances, coefficient ranges           | may require reformulation, not just parameter changes |
| nonlinear robustness   | finite domains, reformulation, nonlinear handler settings | slower presolve/search, tighter modeling burden       |

---

## 14.2 First baseline run: never tune blind

### 14.2.1 Baseline solve

```python id="wl9xmu"
from pyomo.environ import SolverFactory
from pyomo.opt import SolverStatus, TerminationCondition

opt = SolverFactory("scip", solver_io="nl")

opt.options["limits/time"] = 600
opt.options["display/verblevel"] = 4
opt.options["display/relevantstats"] = "TRUE"
opt.options["table/timing/active"] = "TRUE"
opt.options["table/presolver/active"] = "TRUE"
opt.options["table/separator/active"] = "TRUE"
opt.options["table/heuristics/active"] = "TRUE"
opt.options["table/lp/active"] = "TRUE"
opt.options["table/tree/active"] = "TRUE"
opt.options["table/solution/active"] = "TRUE"

res = opt.solve(
    model,
    tee=True,
    logfile="baseline-scip.log",
    keepfiles=True,
    symbolic_solver_labels=True,
    load_solutions=False,
)
```

SCIP exposes `display/verblevel`, `display/relevantstats`, and statistics table controls; Pyomo’s SCIP plugin parses solving time, gap, primal bound, and dual bound from the SCIP log when the expected final summary fields are present. ([SCIP Optimization Library][3])

### 14.2.2 Baseline facts to capture

```text id="kas7pr"
Required baseline metrics:
  termination_condition
  solver.message
  wall time
  SCIP solving time
  nodes
  gap
  primal_bound
  dual_bound
  first incumbent time, if visible in log
  root time, if visible in log
  presolve reductions
  cut counts / separator table
  heuristic table
  LP iterations/time
  peak memory, if visible
```

### 14.2.3 Baseline extractor

```python id="tsk251"
from dataclasses import dataclass, asdict
import json
from pathlib import Path

@dataclass(frozen=True)
class ScipMetrics:
    status: str
    termination_condition: str
    message: str
    time: float | None
    gap: float | str | None
    primal_bound: float | None
    dual_bound: float | None
    n_solutions: int

def extract_scip_metrics(results) -> ScipMetrics:
    solver = results.solver
    return ScipMetrics(
        status=str(getattr(solver, "status", "")),
        termination_condition=str(getattr(solver, "termination_condition", "")),
        message=str(getattr(solver, "message", "")),
        time=getattr(solver, "time", None),
        gap=getattr(solver, "gap", None),
        primal_bound=getattr(solver, "primal_bound", None),
        dual_bound=getattr(solver, "dual_bound", None),
        n_solutions=len(results.solution),
    )

metrics = extract_scip_metrics(res)
Path("baseline-metrics.json").write_text(json.dumps(asdict(metrics), indent=2))
```

---

## 14.3 Core stopping recipes: time, gap, node, memory, solution limits

### 14.3.1 Parameter syntax

```python id="fh9gya"
opt.options["limits/time"] = 300          # seconds
opt.options["limits/gap"] = 1e-4          # relative primal-dual gap
opt.options["limits/absgap"] = 1e-6       # absolute primal-dual gap
opt.options["limits/nodes"] = 100000      # branch-and-bound node cap
opt.options["limits/totalnodes"] = 200000 # includes restarts
opt.options["limits/memory"] = 8192       # MB
opt.options["limits/solutions"] = 1       # stop after N solutions
```

SCIP defines `limits/time` as maximum run time in seconds, `limits/nodes` and `limits/totalnodes` as node budgets, and `limits/gap` / `limits/absgap` as relative and absolute primal-dual gap stopping rules. ([SCIP Optimization Library][3])

### 14.3.2 Objective-specific stopping policies

```text id="om5qmw"
Fast feasible:
  limits/time = short
  limits/solutions = 1 or small N
  limits/gap = loose

Strong proof:
  limits/time = long
  limits/gap = tight
  limits/absgap = objective-unit tolerance
  no solution-count stop

Memory reduction:
  limits/memory = deployment cap
  cut/LP settings reduced
  node limit optional

Benchmark:
  fixed limits/time
  fixed limits/nodes
  fixed randomization
  fixed threads
```

### 14.3.3 Recommended policy object

```python id="04dfdf"
from dataclasses import dataclass

@dataclass(frozen=True)
class ScipStopPolicy:
    time_limit: float | None = None
    rel_gap: float | None = None
    abs_gap: float | None = None
    node_limit: int | None = None
    memory_mb: float | None = None
    solution_limit: int | None = None

def apply_stop_policy(opt, p: ScipStopPolicy):
    if p.time_limit is not None:
        opt.options["limits/time"] = float(p.time_limit)
    if p.rel_gap is not None:
        opt.options["limits/gap"] = float(p.rel_gap)
    if p.abs_gap is not None:
        opt.options["limits/absgap"] = float(p.abs_gap)
    if p.node_limit is not None:
        opt.options["limits/nodes"] = int(p.node_limit)
    if p.memory_mb is not None:
        opt.options["limits/memory"] = float(p.memory_mb)
    if p.solution_limit is not None:
        opt.options["limits/solutions"] = int(p.solution_limit)
```

---

## 14.4 Emphasis settings: native vs Pyomo reality

### 14.4.1 Native SCIP C API

```c id="jxqs9y"
SCIPsetPresolving(scip, SCIP_PARAMSETTING_FAST, TRUE);
SCIPsetHeuristics(scip, SCIP_PARAMSETTING_AGGRESSIVE, TRUE);
SCIPsetSeparating(scip, SCIP_PARAMSETTING_OFF, TRUE);
```

SCIP documents `FAST`, `AGGRESSIVE`, `DEFAULT`, and `OFF` for presolving, heuristics, and separating; aggressive heuristics/separators can enable plugins regardless of `USESSUBSCIP`, which can matter in sub-SCIP recursion scenarios. ([SCIP Optimization Library][2])

### 14.4.2 Pyomo-safe workflow

```text id="wck6do"
1. Run standalone SCIP:
   SCIP> set heuristics emphasis aggressive
   SCIP> set separating emphasis fast
   SCIP> set presolving emphasis aggressive
   SCIP> set diffsave tuned.set

2. Convert tuned.set into Pyomo opt.options.

3. Run Pyomo with those concrete key/value settings.

Reason:
  Pyomo option transport accepts concrete parameter keys, not native C meta-setting calls.
```

The official parameter page states the installed parameter list can be generated with `SCIP> set save <file name>`; use installed-version `set save` / `set diffsave` output as the authoritative source of Pyomo option keys. ([SCIP Optimization Library][3])

### 14.4.3 `tuned.set` loader

```python id="hoqjla"
from pathlib import Path

def parse_scip_set(path: str | Path) -> dict[str, str]:
    out = {}
    for raw in Path(path).read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip()
    return out

def apply_scip_set(opt, path: str | Path):
    for k, v in parse_scip_set(path).items():
        opt.options[k] = v
```

---

## 14.5 Objective A: fast feasible solution

### 14.5.1 Use when

```text id="qmbo9l"
Use fast-feasible tuning when:
  no incumbent before time limit
  planning/scheduling needs any valid plan
  gap proof is secondary
  solve is used as warm-start/candidate generator
  time budget is strict
```

### 14.5.2 Parameter recipe

```python id="zagmdw"
def scip_profile_fast_feasible(opt):
    # stopping
    opt.options["limits/time"] = 300
    opt.options["limits/solutions"] = 1
    opt.options["limits/gap"] = 0.05

    # keep presolve; avoid excessive proof-only cut work
    opt.options["presolving/maxrounds"] = -1
    opt.options["separating/maxroundsroot"] = 5
    opt.options["separating/maxrounds"] = 1
    opt.options["separating/maxcutsroot"] = 500
    opt.options["separating/maxcuts"] = 50

    # nudge major primal heuristics; validate keys with installed SCIP set-save file
    opt.options["heuristics/rens/freq"] = 10
    opt.options["heuristics/rens/maxnodes"] = 5000
    opt.options["heuristics/rens/minfixingrate"] = 0.5
    opt.options["heuristics/alns/freq"] = 20

    # diagnostics
    opt.options["display/verblevel"] = 4
    opt.options["display/relevantstats"] = "TRUE"
    opt.options["table/heuristics/active"] = "TRUE"
    opt.options["table/solution/active"] = "TRUE"
```

SCIP’s RENS parameters include call frequency, maximum subproblem node budget, and minimum fixing rate; ALNS also has a heuristic frequency parameter. ([SCIP Optimization Library][3])

### 14.5.3 Model-side actions

```text id="ladawx"
Improve feasible-solution speed:
  tighten all variable bounds
  provide feasible or near-feasible initial values where supported
  remove accidental infeasibility
  split huge disjunctions if possible
  linearize binary-continuous products when exact and cheap
  add valid constraints that guide feasibility
  avoid enormous big-M values
```

### 14.5.4 Acceptance policy

```python id="wb9t4v"
res = opt.solve(model, tee=True, logfile="fast-feasible.log", load_solutions=False)

if len(res.solution) > 0:
    model.solutions.load_from(res)
else:
    raise RuntimeError("Fast-feasible profile found no incumbent")
```

---

## 14.6 Objective B: strong proof of optimality

### 14.6.1 Use when

```text id="n64z0x"
Use proof-focused tuning when:
  incumbent exists but gap closes slowly
  root gap is large
  dual bound barely moves
  final deliverable requires optimality certificate/gap
  objective value must be defensible
```

### 14.6.2 Parameter recipe

```python id="26ko6z"
def scip_profile_proof(opt):
    # strict stopping
    opt.options["limits/time"] = 7200
    opt.options["limits/gap"] = 1e-6
    opt.options["limits/absgap"] = 1e-8

    # aggressive presolve/root proof effort
    opt.options["presolving/maxrounds"] = -1
    opt.options["presolving/maxrestarts"] = -1

    # stronger root separation; controlled tree separation
    opt.options["separating/maxroundsroot"] = -1
    opt.options["separating/maxcutsroot"] = 5000
    opt.options["separating/maxstallroundsroot"] = 20
    opt.options["separating/maxrounds"] = 3
    opt.options["separating/maxcuts"] = 200

    # diagnostics
    opt.options["display/verblevel"] = 4
    opt.options["display/relevantstats"] = "TRUE"
    opt.options["table/presolver/active"] = "TRUE"
    opt.options["table/separator/active"] = "TRUE"
    opt.options["table/lp/active"] = "TRUE"
    opt.options["table/tree/active"] = "TRUE"
```

SCIP’s `presolving/maxrounds` uses `-1` for unlimited and `0` for off; cut controls include local and root cut limits, where `separating/maxcutsroot` controls cuts separated per round at the root. ([SCIP Optimization Library][3])

### 14.6.3 Model-side actions

```text id="1yjy9u"
Improve proof:
  strengthen formulation
  tighten big-M
  add implied bounds
  add valid inequalities
  exploit SOS2/piecewise representations carefully
  use convex-hull formulations for disjunctions when size acceptable
  remove weak redundant variables/constraints
  reduce coefficient scaling pathologies
```

### 14.6.4 Proof diagnostics

```text id="n0fi6a"
If proof profile is slower:
  root time too high -> reduce maxcutsroot / maxroundsroot
  LP time too high -> inspect LP table, reduce cuts
  nodes still huge -> strengthen formulation / branching variables
  primal bound poor -> add heuristic effort
  dual bound stagnant -> stronger cuts or formulation
```

---

## 14.7 Objective C: memory reduction

### 14.7.1 Use when

```text id="fel4gj"
Use memory-focused tuning when:
  memory limit reached
  LP row count explodes
  cut pool grows
  tree grows too large
  container/HPC memory quota binding
```

### 14.7.2 Parameter recipe

```python id="8p7c3v"
def scip_profile_memory_light(opt):
    opt.options["limits/memory"] = 8192

    # reduce local separation and cut accumulation
    opt.options["separating/maxroundsroot"] = 3
    opt.options["separating/maxrounds"] = 0
    opt.options["separating/maxcutsroot"] = 300
    opt.options["separating/maxcuts"] = 0
    opt.options["separating/cutagelimit"] = 20
    opt.options["separating/poolfreq"] = -1

    # avoid excessive restart/presolve churn
    opt.options["presolving/maxrestarts"] = 0

    # deterministic, low-thread baseline
    opt.options["parallel/minnthreads"] = 1
    opt.options["parallel/maxnthreads"] = 1

    # reduced log volume
    opt.options["display/verblevel"] = 3
    opt.options["display/freq"] = 1000
```

SCIP’s separation parameters include local/root cut limits, cut age limit, and global cut pool separation frequency; `poolfreq = -1` disables global cut-pool separation frequency. ([SCIP Optimization Library][3]) SCIP’s parallel parameters include deterministic/opportunistic mode and minimum/maximum thread counts. ([SCIP Optimization Library][3])

### 14.7.3 Model-side actions

```text id="ea8nk6"
Reduce memory at model level:
  remove duplicate constraints
  use sparse indexed constraints
  avoid dense all-pairs constraints unless necessary
  decompose scenario models
  avoid huge piecewise formulations when SOS2/log forms suffice
  avoid expanding all columns if pricing/column generation is natural
  aggregate variables where exact and safe
```

---

## 14.8 Objective D: aggressive presolve

### 14.8.1 Use when

```text id="6y6a8k"
Use aggressive presolve when:
  generated model has redundancy
  GDP / piecewise / big-M expansion is large
  presolve deletes many variables/constraints already
  root model is much smaller after presolve
  implied bounds/integrality likely present
```

### 14.8.2 Parameter recipe

```python id="btcth1"
def scip_profile_aggressive_presolve(opt):
    opt.options["presolving/maxrounds"] = -1
    opt.options["presolving/maxrestarts"] = -1
    opt.options["presolving/abortfac"] = 0.0001

    # keep aggregation enabled
    opt.options["presolving/donotaggr"] = "FALSE"
    opt.options["presolving/donotmultaggr"] = "FALSE"

    # SCIP 10 implied-integrality presolver exploration; verify installed params
    opt.options["presolving/implint/maxrounds"] = -1
    opt.options["presolving/implint/convertintegers"] = "FALSE"

    opt.options["display/verblevel"] = 5
    opt.options["display/relevantstats"] = "TRUE"
    opt.options["table/presolver/active"] = "TRUE"
```

### 14.8.3 Risk control

```text id="6d0zka"
Aggressive presolve risks:
  high front-loaded time
  harder row/column mapping
  numerical issues if model badly scaled
  different transformed model complicates debugging

Debug fallback:
  presolving/maxrounds = 0
  keepfiles=True
  symbolic_solver_labels=True
```

---

## 14.9 Objective E: numerical stability

### 14.9.1 Do not start with tolerances

```text id="myfbb2"
Numerical-tuning order:
  1. inspect units and coefficient magnitudes
  2. tighten bounds
  3. reduce big-M
  4. scale objective/constraints
  5. avoid near-zero denominators/domains
  6. only then adjust numerics/*
```

SCIP defines `numerics/epsilon`, `numerics/sumepsilon`, and `numerics/feastol`; `numerics/feastol` is the feasibility tolerance for constraints and defaults to `1e-6`. ([SCIP Optimization Library][3])

### 14.9.2 Parameter recipe

```python id="p3t8zu"
def scip_profile_numerical_stability(opt):
    # Do not over-tighten blindly.
    opt.options["numerics/feastol"] = 1e-6
    opt.options["numerics/epsilon"] = 1e-9
    opt.options["numerics/sumepsilon"] = 1e-6

    opt.options["display/verblevel"] = 5
    opt.options["display/allviols"] = "TRUE"
    opt.options["display/relevantstats"] = "TRUE"
```

### 14.9.3 Model-side stability checklist

```text id="2wadqt"
Stability checklist:
  coefficient ranges ideally not spanning 1e12+
  no big-M = 1e9 unless units justify it
  all nonlinear variables bounded
  log(x): x.lb > 0
  sqrt(x): x.lb >= 0
  1/x: x excludes 0
  objective terms scaled to comparable magnitude
  constraints scaled by meaningful units
  binary-continuous products linearized with tight bounds
```

### 14.9.4 Pyomo scaling suffix example

```python id="7n7qeo"
from pyomo.environ import Suffix

model.scaling_factor = Suffix(direction=Suffix.EXPORT)

# Example: scale objective and constraints
model.scaling_factor[model.obj] = 1e-3
model.scaling_factor[model.capacity] = 1e-2
```

---

## 14.10 Objective F: nonlinear robustness

### 14.10.1 Use when

```text id="os2n59"
Use nonlinear robustness profile when:
  MINLP fails early
  nonlinear constraint violations appear
  bilinear terms dominate
  binary products occur in nonlinear expressions
  local domains are weak
  nonlinear branching/cuts need diagnosis
```

### 14.10.2 Parameter recipe

```python id="wq6hxy"
def scip_profile_nonlinear_robust(opt):
    # Nonlinear constraint handler controls; verify exact keys in installed SCIP set-save file.
    opt.options["constraints/nonlinear/maxproprounds"] = 20
    opt.options["constraints/nonlinear/reformbinprods"] = "TRUE"
    opt.options["constraints/nonlinear/reformbinprodsand"] = "TRUE"
    opt.options["constraints/nonlinear/weakcutthreshold"] = 0.1

    # Root propagation/cuts diagnostics
    opt.options["propagating/maxroundsroot"] = 1000
    opt.options["display/verblevel"] = 5
    opt.options["display/relevantstats"] = "TRUE"
    opt.options["table/constraint/active"] = "TRUE"
    opt.options["table/nlp/active"] = "TRUE"
    opt.options["table/lp/active"] = "TRUE"
```

### 14.10.3 Model-side nonlinear actions

```text id="s4h1qw"
Robust MINLP formulation:
  finite bounds on every nonlinear variable
  bound tightening before solve
  replace binary-continuous products with exact linearization when possible
  replace piecewise nonlinear functions with Piecewise/SOS2 if acceptable
  avoid nonlinear equalities unless necessary
  use convex relaxations where possible
  reduce expression nesting
  eliminate redundant nonlinear subexpressions manually when clear
```

---

## 14.11 Randomization and deterministic benchmarking

### 14.11.1 Deterministic-ish settings

```python id="xxpv65"
def scip_profile_deterministic(opt, threads=1):
    opt.options["randomization/randomseedshift"] = 0
    opt.options["randomization/permutationseed"] = 0
    opt.options["randomization/permuteconss"] = "FALSE"
    opt.options["randomization/permutevars"] = "FALSE"
    opt.options["randomization/lpseed"] = 0

    opt.options["parallel/mode"] = 1
    opt.options["parallel/minnthreads"] = int(threads)
    opt.options["parallel/maxnthreads"] = int(threads)
```

SCIP exposes randomization controls for global seed shift, permutation seed, constraint/variable permutation, and LP seed; it also exposes `parallel/mode`, where `0` is opportunistic and `1` is deterministic, plus minimum/maximum thread counts. ([SCIP Optimization Library][3])

### 14.11.2 Benchmark rule

```text id="5sgmwk"
For benchmark comparison:
  same data
  same Pyomo model code
  same exported model determinism
  same SCIP version
  same parameter file
  same thread count
  same randomization settings
  same hardware class if possible
```

---

## 14.12 Model-side performance playbook

### 14.12.1 Tighten bounds

```python id="avy401"
# Bad
m.flow = Var(m.Arcs, domain=NonNegativeReals)

# Better
m.flow = Var(m.Arcs, bounds=lambda m, a: (0, capacity[a]))
```

```text id="n11nst"
Impact:
  stronger LP/NLP relaxations
  better propagation
  better big-M calculation
  better nonlinear relaxations
  smaller search tree
```

### 14.12.2 Avoid weak big-M

```python id="fc6icm"
# z = 1 -> expr <= rhs
# Compute M from bounds, not a hard-coded huge constant.
def upper_bound_linear_expr(coef, lb, ub):
    return sum(c * (ub[i] if c >= 0 else lb[i]) for i, c in coef.items())

M = max(0.0, upper_bound_linear_expr(coef, lb, ub) - rhs)
m.ind = Constraint(expr=sum(coef[i] * m.x[i] for i in coef) <= rhs + M * (1 - m.z))
```

### 14.12.3 Use SOS/piecewise carefully

```python id="u1nv9y"
m.pw = Piecewise(
    m.y,
    m.x,
    pw_pts=[0, 1, 2, 3, 4],
    f_rule=[0, 1, 4, 9, 16],
    pw_constr_type="EQ",
    pw_repn="SOS2",
)
```

```text id="z6p20f"
Piecewise tuning:
  SOS2: compact, natural for SCIP through Pyomo
  DCC/CC: explicit convex-combination formulations
  DLOG/LOG: fewer binaries for many breakpoints
  BIGM_BIN: only if generated M values are trusted and scaling is clean
```

### 14.12.4 Exploit sparsity

```python id="s5qmsd"
# Bad: all-pairs dense constraints
m.c = Constraint(m.I, m.J, rule=lambda m, i, j: ...)

# Better: only real edges/nonzeros
m.E = Set(dimen=2, initialize=edges)
m.c = Constraint(m.E, rule=lambda m, i, j: ...)
```

### 14.12.5 Reduce nonlinear expression complexity

```text id="w2w6iw"
Reduce:
  repeated expression trees
  products of sums
  nested nonlinear functions
  nonlinear equalities
  unnecessary binary-continuous products

Replace:
  repeated expression -> Expression component or auxiliary variable
  binary*continuous -> linearization if exact
  smooth convex function -> piecewise approximation if acceptable
```

---

## 14.13 Benchmark harness

### 14.13.1 Benchmark scenario definition

```python id="o0egce"
from dataclasses import dataclass
from typing import Callable

@dataclass(frozen=True)
class BenchmarkCase:
    name: str
    build_model: Callable[[], object]
    apply_profile: Callable
    time_limit: float = 600.0
```

### 14.13.2 Solver factory

```python id="irtcwn"
from pyomo.environ import SolverFactory

def make_scip_for_benchmark(profile_fn, *, time_limit=600, deterministic=True):
    opt = SolverFactory("scip", solver_io="nl")

    if not opt.available(False):
        raise RuntimeError("SCIP unavailable")

    opt.options["limits/time"] = time_limit
    opt.options["display/verblevel"] = 4
    opt.options["display/relevantstats"] = "TRUE"
    opt.options["table/timing/active"] = "TRUE"
    opt.options["table/presolver/active"] = "TRUE"
    opt.options["table/separator/active"] = "TRUE"
    opt.options["table/heuristics/active"] = "TRUE"
    opt.options["table/lp/active"] = "TRUE"
    opt.options["table/tree/active"] = "TRUE"

    if deterministic:
        scip_profile_deterministic(opt, threads=1)

    profile_fn(opt)
    return opt
```

### 14.13.3 Run one benchmark

```python id="vqlqf1"
import json
import time
from pathlib import Path

def write_options_manifest(opt, path):
    data = {str(k): str(v) for k, v in sorted(opt.options.items()) if k != "solver"}
    Path(path).write_text(json.dumps(data, indent=2, sort_keys=True))

def run_benchmark_case(case: BenchmarkCase, out_dir: str):
    out = Path(out_dir) / case.name
    out.mkdir(parents=True, exist_ok=True)

    model = case.build_model()
    opt = make_scip_for_benchmark(case.apply_profile, time_limit=case.time_limit)

    write_options_manifest(opt, out / "scip-options.json")

    t0 = time.perf_counter()
    res = opt.solve(
        model,
        tee=False,
        logfile=str(out / "scip.log"),
        keepfiles=True,
        symbolic_solver_labels=True,
        load_solutions=False,
    )
    wall_time = time.perf_counter() - t0

    metrics = extract_scip_metrics(res)
    payload = {
        "case": case.name,
        "wall_time": wall_time,
        **asdict(metrics),
    }
    (out / "metrics.json").write_text(json.dumps(payload, indent=2, sort_keys=True))
    return payload
```

### 14.13.4 Compare profiles

```python id="puc7u2"
profiles = {
    "safe": scip_profile_safe,
    "fast_feasible": scip_profile_fast_feasible,
    "proof": scip_profile_proof,
    "memory_light": scip_profile_memory_light,
    "nonlinear_robust": scip_profile_nonlinear_robust,
}

cases = [
    BenchmarkCase(
        name=f"instance001__{profile_name}",
        build_model=lambda: build_model(data),
        apply_profile=profile_fn,
        time_limit=600,
    )
    for profile_name, profile_fn in profiles.items()
]

results = [run_benchmark_case(c, "bench_runs") for c in cases]
```

### 14.13.5 Required benchmark columns

```text id="b0stlu"
Benchmark output columns:
  case
  profile
  scip_version
  pyomo_version
  wall_time
  solver_time
  termination_condition
  status
  nodes
  gap
  primal_bound
  dual_bound
  n_solutions
  objective_after_load
  options_hash
  model_data_hash
```

---

## 14.14 Profile library

### 14.14.1 Safe baseline

```python id="80ldlw"
def scip_profile_safe(opt):
    opt.options["limits/time"] = 600
    opt.options["limits/gap"] = 1e-4
    opt.options["display/verblevel"] = 4
    opt.options["display/relevantstats"] = "TRUE"
```

### 14.14.2 Fast feasible

```python id="y325b9"
def scip_profile_fast_feasible(opt):
    opt.options["limits/time"] = 300
    opt.options["limits/solutions"] = 1
    opt.options["limits/gap"] = 0.05
    opt.options["separating/maxroundsroot"] = 5
    opt.options["separating/maxrounds"] = 1
    opt.options["heuristics/rens/freq"] = 10
    opt.options["heuristics/alns/freq"] = 20
```

### 14.14.3 Proof-focused

```python id="izzour"
def scip_profile_proof(opt):
    opt.options["limits/time"] = 7200
    opt.options["limits/gap"] = 1e-6
    opt.options["limits/absgap"] = 1e-8
    opt.options["presolving/maxrounds"] = -1
    opt.options["separating/maxroundsroot"] = -1
    opt.options["separating/maxcutsroot"] = 5000
    opt.options["separating/maxrounds"] = 3
```

### 14.14.4 Memory-light

```python id="43n5j9"
def scip_profile_memory_light(opt):
    opt.options["limits/memory"] = 8192
    opt.options["separating/maxroundsroot"] = 3
    opt.options["separating/maxrounds"] = 0
    opt.options["separating/maxcutsroot"] = 300
    opt.options["separating/maxcuts"] = 0
    opt.options["separating/poolfreq"] = -1
    opt.options["presolving/maxrestarts"] = 0
```

### 14.14.5 Numerical-stability diagnostic

```python id="5bsl4e"
def scip_profile_numerics_debug(opt):
    opt.options["display/verblevel"] = 5
    opt.options["display/allviols"] = "TRUE"
    opt.options["display/relevantstats"] = "TRUE"
    opt.options["numerics/feastol"] = 1e-6
    opt.options["numerics/epsilon"] = 1e-9
    opt.options["numerics/sumepsilon"] = 1e-6
```

### 14.14.6 Nonlinear robust

```python id="ac0zol"
def scip_profile_nonlinear_robust(opt):
    opt.options["constraints/nonlinear/maxproprounds"] = 20
    opt.options["constraints/nonlinear/reformbinprods"] = "TRUE"
    opt.options["constraints/nonlinear/reformbinprodsand"] = "TRUE"
    opt.options["constraints/nonlinear/weakcutthreshold"] = 0.1
    opt.options["propagating/maxroundsroot"] = 1000
```

---

## 14.15 Diagnostics-to-action matrix

| Symptom                             | Primary signal                       | Likely issue                       | First action                           | Second action                      |
| ----------------------------------- | ------------------------------------ | ---------------------------------- | -------------------------------------- | ---------------------------------- |
| no incumbent                        | `n_solutions=0`, no primal bound     | feasibility hard / heuristics weak | fast-feasible profile                  | tighten bounds, repair formulation |
| large final gap                     | high gap                             | dual bound weak                    | proof profile, root cuts               | stronger formulation               |
| root takes too long                 | log root/presolve/cut time           | presolve/cuts too heavy            | reduce `maxcutsroot` / `maxroundsroot` | model simplification               |
| many nodes                          | high nodes, slow dual bound          | branching/formulation weak         | add valid inequalities, tighter M      | branch parameter/native priorities |
| memory limit                        | `memory limit reached`, huge LP/cuts | cuts/tree too large                | memory-light profile                   | decompose/reformulate              |
| numerical warnings                  | violations, unstable log             | scaling/big-M                      | scale/tighten bounds                   | tolerance adjustment               |
| nonlinear failure                   | nonlinear violations/domain issues   | weak domains/nonlinear complexity  | nonlinear robust profile               | linearize/approximate/reformulate  |
| presolve solves or deletes too much | hard to debug names                  | presolve obscures mapping          | `presolving/maxrounds=0`, keep files   | inspect raw model                  |

---

## 14.16 Agent tuning algorithm

```text id="5szu7r"
Algorithm:
  1. Build baseline with safe profile.
  2. Capture .nl/.row/.col/.log/options/metrics.
  3. Classify failure mode:
       no incumbent
       poor proof
       memory
       numerical
       nonlinear
       infeasible
  4. Apply exactly one profile change.
  5. Re-run same data/model/version/seed.
  6. Compare:
       wall_time
       solver_time
       nodes
       gap
       primal_bound
       dual_bound
       first incumbent
       memory/log evidence
  7. Keep profile only if metric improves target without unacceptable regression.
  8. Port final options into JSON and scip.set-equivalent artifact.
```

---

## 14.17 Compact mental model

```text id="jv5fcp"
Fast feasible:
  increase heuristic usefulness
  reduce proof-heavy separation
  accept incumbent policy

Strong proof:
  tighten gap
  aggressive root cuts/presolve
  inspect dual-bound movement

Memory reduction:
  reduce cuts, cut pool, local separation, restarts, threads

Aggressive presolve:
  use when generated model is redundant
  avoid when debugging raw infeasibility

Numerical stability:
  fix model scale before changing tolerances
  avoid weak big-M and missing bounds

Nonlinear robustness:
  finite domains
  simplify nonlinear expressions
  use nonlinear handler controls only after formulation review

Benchmark:
  same model
  same data
  same SCIP/Pyomo versions
  same options
  same randomization/thread settings
  capture time, nodes, gap, primal/dual bounds
```

[1]: https://pyomo.readthedocs.io/en/6.8.2/_modules/pyomo/solvers/plugins/solvers/SCIPAMPL.html "pyomo.solvers.plugins.solvers.SCIPAMPL — Pyomo 6.8.2 documentation"
[2]: https://www.scipopt.org/doc/html/group__ParameterMethods.php "SCIP Doxygen Documentation: Parameter"
[3]: https://www.scipopt.org/doc/html/PARAMETERS.php "SCIP Doxygen Documentation: List of all SCIP parameters"

# 15) Numerical stability and modeling best practices — Pyomo + SCIP

Dense technical reference for LLM programming agents. Style aligned with the uploaded advanced-doc pattern. 

---

## 15.0 Stability contract

```text id="4utucp"
Numerically stable Pyomo+SCIP model:
  variables have meaningful units
  variables have finite, tight bounds where possible
  objective magnitude is scaled to decision relevance
  constraint coefficients have controlled ranges
  big-M values are derived, not guessed
  domains match true integrality semantics
  nonlinear expressions are domain-safe
  transformations are selected intentionally
  solver tolerances are not used to hide modeling defects
```

SCIP exposes numerical tolerance parameters such as `numerics/epsilon`, `numerics/sumepsilon`, and `numerics/feastol`, and its FAQ notes feasibility checks are made with respect to `numerics/feastol`; however, stability work should start with scaling, bounds, and formulation, not with tolerance tightening. ([SCIP Optimization Library][1])

---

## 15.1 Scaling: variables, objective, constraints

### 15.1.1 Scaling target

```text id="iuqpo0"
Target numeric regime:
  most active variable magnitudes: 1e-3 to 1e6
  most active constraint coefficients: avoid 1e-12 next to 1e9
  objective terms: comparable order unless lexicographic weighting intentional
  big-M coefficients: as small as valid
  nonlinear domains: away from singularities where possible
```

### 15.1.2 Variable units

```text id="orj2oj"
Bad:
  x_energy_kWh ~ 1e9
  x_flow_kg_s ~ 1e-8
  x_binary ∈ {0,1}
  all in same constraint without scaling

Better:
  x_energy_GWh = x_energy_kWh / 1e6
  x_flow_ton_h = x_flow_kg_s * 3.6
  constraints written in coherent engineering units
```

Pyomo variables can be declared with explicit bounds and domains through `Var(domain=..., bounds=...)`; for SCIP, finite, meaningful bounds improve relaxation strength, propagation, big-M derivation, and nonlinear domain safety. ([Pyomo Documentation][2])

```python id="jkcm0u"
from pyomo.environ import *

m = ConcreteModel()

# Bad: raw huge unit
m.energy_kwh = Var(bounds=(0, 2_000_000_000))

# Better: scaled engineering unit
m.energy_gwh = Var(bounds=(0, 2_000))
```

### 15.1.3 Objective scaling

```text id="3cd0dt"
Objective scaling failure:
  cost term ~ 1e12
  penalty term ~ 1e2
  penalty effectively ignored numerically and economically unless intentionally weighted

Objective scaling rule:
  use objective units meaningful to stakeholders
  normalize penalties
  avoid huge artificial lexicographic weights
  implement lexicographic solves explicitly when needed
```

```python id="pyzi2e"
# Bad: massive artificial weight
m.obj = Objective(expr=1e9 * m.primary_cost + m.secondary_penalty)

# Better: two-stage lexicographic solve
m.obj1 = Objective(expr=m.primary_cost)
res1 = opt.solve(m, load_solutions=False)
m.solutions.load_from(res1)
best_primary = value(m.primary_cost)

m.obj1.deactivate()
m.primary_cap = Constraint(expr=m.primary_cost <= best_primary + 1e-6)
m.obj2 = Objective(expr=m.secondary_penalty)
res2 = opt.solve(m)
```

### 15.1.4 Pyomo scaling suffix

Pyomo supports scaling through a `scaling_factor` suffix, and its NL writer can output model constraints and variables in scaled space when `scale_model=True`, which is the default for the NL writer path. ([Pyomo Documentation][3])

```python id="xmqwjx"
from pyomo.environ import *

m = ConcreteModel()
m.scaling_factor = Suffix(direction=Suffix.EXPORT)

m.x = Var(bounds=(0, 1e6))
m.y = Var(bounds=(0, 1))

m.c = Constraint(expr=1e-6 * m.x + m.y <= 2)
m.obj = Objective(expr=1e6 * m.y + m.x)

# Scale components for solver-side numeric properties
m.scaling_factor[m.x] = 1e-6
m.scaling_factor[m.obj] = 1e-6
m.scaling_factor[m.c] = 1.0
```

Pyomo also has a `ScaleModel` transformation that performs variable, constraint, and objective scaling based on `scaling_factor` suffixes, useful when an explicit transformed model is desired rather than relying only on writer behavior. ([Pyomo Documentation][4])

```python id="dsj89j"
from pyomo.environ import TransformationFactory

scaled = TransformationFactory("core.scale_model").create_using(m)
res = SolverFactory("scip").solve(scaled, tee=True)
```

### 15.1.5 Constraint coefficient-range audit

```python id="1wo2ni"
from pyomo.environ import Constraint, value
from pyomo.repn import generate_standard_repn

def audit_linear_coefficient_ranges(model):
    rows = []
    for con in model.component_data_objects(Constraint, active=True):
        if con.body is None:
            continue
        repn = generate_standard_repn(con.body)
        if not repn.is_linear():
            continue
        coefs = [abs(value(c)) for c in repn.linear_coefs if value(c) != 0]
        if not coefs:
            continue
        lo, hi = min(coefs), max(coefs)
        ratio = hi / lo if lo > 0 else float("inf")
        rows.append((con.name, lo, hi, ratio))
    return sorted(rows, key=lambda r: r[3], reverse=True)

for name, lo, hi, ratio in audit_linear_coefficient_ranges(m)[:20]:
    if ratio > 1e8:
        print(f"large coefficient range: {name}: min={lo:g}, max={hi:g}, ratio={ratio:g}")
```

---

## 15.2 Bounds: finite, tight, derived

### 15.2.1 Bound hierarchy

```text id="5mjdjt"
Bound quality levels:
  none:
    Var(domain=Reals)
    weak relaxation, weak propagation, unsafe nonlinear domains

  finite but loose:
    Var(bounds=(-1e9, 1e9))
    often numerically poor, weak big-M, large LP ranges

  finite and data-derived:
    Var(bounds=(lb[i], ub[i]))
    preferred

  tight by preprocessing:
    bounds from physical constraints, data, optimization-based bound tightening, propagation
```

Pyomo `Var` supports `bounds` as a tuple or function returning lower/upper values, while its domain controls valid values such as `Reals`, `NonNegativeReals`, and `Binary`. ([Pyomo Documentation][2])

```python id="yvxysk"
# Good: data-derived indexed bounds
def flow_bounds(m, arc):
    return (0, m.capacity[arc])

m.flow = Var(m.Arcs, bounds=flow_bounds)
```

### 15.2.2 Bound audit

```python id="rgd6b7"
from pyomo.environ import Var

def audit_variable_bounds(model):
    bad = []
    for v in model.component_data_objects(Var, active=True):
        lb, ub = v.lb, v.ub
        if lb is None or ub is None:
            bad.append((v.name, lb, ub, "missing_bound"))
        elif abs(lb) > 1e8 or abs(ub) > 1e8:
            bad.append((v.name, lb, ub, "very_large_bound"))
        elif ub - lb > 1e8:
            bad.append((v.name, lb, ub, "wide_bound_range"))
    return bad

for item in audit_variable_bounds(m)[:50]:
    print(item)
```

### 15.2.3 Bound tightening workflow

```text id="84hqha"
Workflow:
  1. derive physical bounds from data
  2. propagate simple algebraic bounds manually
  3. solve continuous relaxation
  4. perform optimization-based bound tightening for critical variables
  5. update model bounds
  6. rerun SCIP baseline
```

```python id="sjd6t9"
from pyomo.environ import Objective, minimize, maximize, value

def tighten_var_by_solves(model, var, opt, *, time_limit=30):
    old_objs = [obj for obj in model.component_data_objects(Objective, active=True)]
    for obj in old_objs:
        obj.deactivate()

    model._bound_obj = Objective(expr=var, sense=minimize)
    opt.options["limits/time"] = time_limit
    res_min = opt.solve(model, load_solutions=False)
    lb = None
    if len(res_min.solution) > 0:
        model.solutions.load_from(res_min)
        lb = value(var)

    model._bound_obj.deactivate()
    model._bound_obj_max = Objective(expr=var, sense=maximize)
    res_max = opt.solve(model, load_solutions=False)
    ub = None
    if len(res_max.solution) > 0:
        model.solutions.load_from(res_max)
        ub = value(var)

    model._bound_obj_max.deactivate()
    del model._bound_obj
    del model._bound_obj_max

    for obj in old_objs:
        obj.activate()

    if lb is not None:
        var.setlb(max(var.lb if var.lb is not None else lb, lb))
    if ub is not None:
        var.setub(min(var.ub if var.ub is not None else ub, ub))
```

### 15.2.4 Big-M derivation

Pyomo’s Big-M transformation accepts scalar or 2-tuple M values and, for linear constraints, can estimate M from variable bounds if possible; the GDP solving docs emphasize that Big-M yields a smaller reformulation but a looser continuous relaxation and that bounded variables allow more reasonable automatic M estimates. ([Pyomo Documentation][5])

```python id="sg9zc9"
def linear_expr_upper_bound(coef, lb, ub):
    total = 0
    for i, a in coef.items():
        total += a * (ub[i] if a >= 0 else lb[i])
    return total

def linear_expr_lower_bound(coef, lb, ub):
    total = 0
    for i, a in coef.items():
        total += a * (lb[i] if a >= 0 else ub[i])
    return total

# z = 1 -> sum(a_i*x_i) <= rhs
M = max(0, linear_expr_upper_bound(a, lb, ub) - rhs)
m.ind = Constraint(expr=sum(a[i] * m.x[i] for i in a) <= rhs + M * (1 - m.z))
```

### 15.2.5 Big-M anti-patterns

```text id="5oihh5"
Bad:
  M = 1e9
  no variable bounds
  M shared across all constraints
  M chosen from “large enough” intuition
  M used to mask logical modeling error

Good:
  M per constraint
  M derived from variable bounds
  M unit-consistent
  M documented
  M stress-tested with edge data
```

---

## 15.3 Integrality: binary, integer, continuous domains

### 15.3.1 Domain semantics

```text id="fgv65l"
Binary:
  yes/no, selected/not selected, active/inactive
  use domain=Binary

Integer:
  count, lot size, number of machines, discrete unit quantity
  use domain=Integers or NonNegativeIntegers

Continuous:
  flow, mass, energy, time, concentration, relaxed quantity
  use Reals / NonNegativeReals + bounds
```

Pyomo variable domains are declared through `Var(domain=...)`, and the documented examples include `Reals`, `NonNegativeReals`, and `Binary`; Pyomo kernel docs also note that a binary variable can be represented as integer domain with bounds 0 and 1, but `domain=Binary` is clearer and stronger semantically for model agents. ([Pyomo Documentation][2])

```python id="orfzr8"
m.open = Var(m.Facilities, domain=Binary)
m.num_trucks = Var(m.Facilities, domain=NonNegativeIntegers, bounds=(0, 50))
m.flow = Var(m.Arcs, domain=NonNegativeReals, bounds=flow_bounds)
```

### 15.3.2 Integrality anti-patterns

```python id="2c4zk9"
# Bad: continuous relaxation, not a binary decision
m.open = Var(m.Facilities, bounds=(0, 1))

# Good
m.open = Var(m.Facilities, domain=Binary)
```

```python id="4a2zq6"
# Bad: integer variable with no useful upper bound
m.count = Var(domain=NonNegativeIntegers)

# Good
m.count = Var(domain=NonNegativeIntegers, bounds=(0, max_count))
```

### 15.3.3 Fixing and unfixing variables

Pyomo `Var.fix(value)` fixes variables by setting the fixed indicator to `True` and optionally updates the value first; `unfix()` reverses this fixed status. ([Pyomo Documentation][6])

```python id="u0qfsi"
# Fix strategic decision
m.open["plant_A"].fix(1)

# Fix all variables in an indexed component from a known incumbent
for i in m.I:
    m.x[i].fix(round(value(m.x[i])))

# Unfix for later solve
m.open["plant_A"].unfix()
```

### 15.3.4 Fixing vs bounds

```text id="prff0e"
fix(value):
  variable removed as decision degree of freedom
  use for scenario fixing, decomposition, validation, incumbent feasibility checks

setlb/setub:
  variable remains decision variable
  use for bound tightening and domain narrowing

binary fixing:
  x.fix(0) or x.fix(1), not x.setlb(0); x.setub(0) unless you intentionally want bound semantics
```

### 15.3.5 Warm-start-style initial values

Pyomo’s solver recipes say some solvers support warm starts based on the current values of variables; the documented usage is to assign values on the model and pass `warmstart=True` to `solve()`, but support is solver/interface-specific. ([Pyomo Documentation][7])

```python id="nucn9q"
# Initial values / incumbent candidate
for i in m.I:
    m.x[i].set_value(0)

m.x[1].set_value(1)
m.x[3].set_value(1)

# Interface-specific; verify SCIPAMPL behavior before relying on it
res = opt.solve(m, tee=True, warmstart=True)
```

Agent rule:

```text id="kd8kvc"
For Pyomo+SCIPAMPL:
  initial values are useful for nonlinear evaluation and diagnostics,
  but do not assume full MIP-start support unless verified in logs/files.
For reliable SCIP incumbent/callback control:
  use PySCIPOpt/native SCIP.
```

---

## 15.4 Nonlinear modeling: explicit domains, no undefined expressions

### 15.4.1 Domain-safe expression rules

```text id="jksewc"
log(x):
  require x.lb > 0

sqrt(x):
  require x.lb >= 0

1/x:
  require x excludes 0, preferably |x| >= eps

x**a with noninteger a:
  require x domain compatible with exponent

exp(x):
  bound x to avoid overflow/weak relaxation

tan(x), asin(x), acos(x):
  avoid unless domain tightly controlled and solver support verified

product x*y:
  both x and y need finite bounds
  if one factor binary and other continuous, consider exact linearization
```

SCIP/PySCIPOpt documentation notes SCIP supports nonlinear expressions and global optimization within tolerances, but modelers must still provide valid domains and finite bounds for robust MINLP behavior. ([PySCIPOpt Documentation][8])

```python id="no1t4g"
from pyomo.environ import *

m.x = Var(bounds=(1e-4, 100), initialize=1.0)
m.y = Var(bounds=(0, 100), initialize=4.0)
m.z = Var(bounds=(1, 10), initialize=2.0)

m.c1 = Constraint(expr=log(m.x) + sqrt(m.y) <= 10)
m.c2 = Constraint(expr=1 / m.z <= 0.8)
```

### 15.4.2 Bad nonlinear expressions

```python id="4hgt4n"
# Bad: log domain includes zero
m.x = Var(bounds=(0, 10))
m.c = Constraint(expr=log(m.x) <= 2)

# Good
m.x = Var(bounds=(1e-6, 10))
m.c = Constraint(expr=log(m.x) <= 2)
```

```python id="xql2ts"
# Bad: unbounded bilinear product
m.x = Var()
m.y = Var()
m.c = Constraint(expr=m.x * m.y <= 10)

# Good: finite domains
m.x = Var(bounds=(-100, 100))
m.y = Var(bounds=(0, 50))
m.c = Constraint(expr=m.x * m.y <= 10)
```

### 15.4.3 Binary-continuous product: exact linearization

```python id="3ignys"
# w = b * y, b ∈ {0,1}, 0 <= y <= U
m.b = Var(domain=Binary)
m.y = Var(bounds=(0, U))
m.w = Var(bounds=(0, U))

m.lin1 = Constraint(expr=m.w <= U * m.b)
m.lin2 = Constraint(expr=m.w <= m.y)
m.lin3 = Constraint(expr=m.w >= m.y - U * (1 - m.b))
m.lin4 = Constraint(expr=m.w >= 0)
```

```text id="ptmxcs"
Use exact linearization when:
  binary-continuous product
  finite tight bounds exist
  MILP formulation preferred
  nonlinear relaxation not needed
```

### 15.4.4 Nonlinear expression audit

```python id="acqv7c"
from pyomo.environ import Constraint, Objective

def audit_polynomial_degrees(model):
    rows = []
    for obj in model.component_data_objects(Objective, active=True):
        rows.append(("Objective", obj.name, obj.expr.polynomial_degree()))
    for con in model.component_data_objects(Constraint, active=True):
        if con.body is not None:
            rows.append(("Constraint", con.name, con.body.polynomial_degree()))
    return rows

for kind, name, degree in audit_polynomial_degrees(m):
    if degree is None:
        print(f"general nonlinear: {kind} {name}")
    elif degree > 2:
        print(f"high-degree polynomial: {kind} {name}, degree={degree}")
```

---

## 15.5 Pyomo transformations: GDP-to-MIP/MINLP

### 15.5.1 GDP transformation choices

```text id="mg6xam"
TransformationFactory("gdp.bigm"):
  smaller formulation
  looser continuous relaxation
  M values required or estimated from bounds

TransformationFactory("gdp.hull"):
  larger formulation
  stronger continuous relaxation
  requires bounded variables in disjunctive expressions
  often better proof behavior

TransformationFactory("core.logical_to_linear"):
  converts logical constraints to algebraic constraints
  creates generated binaries for Boolean variables when needed

TransformationFactory("contrib.logical_to_disjunctive"):
  alternative logical transformation path with factorable programming objects
```

Pyomo GDP docs state the Big-M reformulation is smaller but looser, can estimate M values when variables are bounded, and Hull reformulation is available as a GDP-to-MIP alternative; logical constraints can be transformed using `core.logical_to_linear`, which creates algebraic constraints and associated binary variables for `BooleanVar` objects when needed. ([Pyomo Documentation][9])

### 15.5.2 Big-M transformation syntax

```python id="c02xa5"
from pyomo.environ import *
from pyomo.gdp import Disjunct, Disjunction

m = ConcreteModel()
m.x = Var(bounds=(0, 10))
m.y = Var(bounds=(0, 10))

m.d1 = Disjunct()
m.d1.c = Constraint(expr=m.x + m.y <= 3)

m.d2 = Disjunct()
m.d2.c = Constraint(expr=m.x - m.y >= 2)

m.choice = Disjunction(expr=[m.d1, m.d2])

TransformationFactory("gdp.bigm").apply_to(m, bigM=100)
res = SolverFactory("scip").solve(m, tee=True)
```

### 15.5.3 Big-M suffix syntax

```python id="towkrp"
m.BigM = Suffix(direction=Suffix.LOCAL)

# Constraint-specific M
m.BigM[m.d1.c] = 10.0

# Lower/upper tuple M for two-sided constraint body
m.BigM[m.d2.c] = (-5.0, 20.0)

TransformationFactory("gdp.bigm").apply_to(m)
```

Pyomo’s Big-M transformation documents that M values may be scalar or 2-tuples for lower and upper bounds, and that values can be supplied through arguments or `BigM` suffixes at constraint/block/model levels. ([Pyomo Documentation][5])

### 15.5.4 Hull transformation syntax

```python id="4fb55p"
TransformationFactory("gdp.hull").apply_to(m)
res = SolverFactory("scip").solve(m, tee=True)
```

### 15.5.5 Transformation decision rule

```text id="t6bi71"
Use Big-M when:
  M values are tight
  model size must be small
  disjunction count is large
  linear relaxation weakness acceptable

Use Hull when:
  proof gap matters
  bounds are finite
  disjunctive relaxation strength matters
  model size increase acceptable

Use manual formulation when:
  logic pattern is simple
  M derivation is obvious
  generated transformation obscures debugging
```

---

## 15.6 Piecewise transformations

### 15.6.1 Pyomo `Piecewise` syntax

Pyomo’s `Piecewise` supports constraints such as `y = f(x)` and multiple representation choices through `pw_repn`, including `SOS2`, `BIGM_BIN`, `BIGM_SOS1`, `DCC`, `DLOG`, `CC`, `LOG`, `MC`, and `INC`; Pyomo’s docs note representation choice can have major performance impact. ([Pyomo Documentation][10])

```python id="liw08l"
m.x = Var(bounds=(0, 4))
m.y = Var()

m.pw = Piecewise(
    m.y,
    m.x,
    pw_pts=[0, 1, 2, 3, 4],
    f_rule=[0, 1, 4, 9, 16],
    pw_constr_type="EQ",
    pw_repn="SOS2",
)
```

### 15.6.2 Representation decision table

```text id="bpkawk"
SOS2:
  default first choice with SCIP
  compact
  solver SOS2 handling important

CC:
  explicit convex-combination
  easier to inspect
  more algebraic variables/constraints

DCC:
  disaggregated convex-combination
  stronger/larger
  useful for nonconvex/step-like forms

LOG/DLOG:
  logarithmic binary count
  useful for many breakpoints
  representation requirements must be met

BIGM_BIN / BIGM_SOS1:
  can be compact
  M quality and scaling critical
  use only after inspecting generated formulation/performance
```

### 15.6.3 Breakpoint hygiene

```python id="8dg5x1"
def validate_piecewise_breakpoints(points, x_lb, x_ub):
    assert len(points) >= 2, "need at least two breakpoints"
    assert all(points[i] < points[i+1] for i in range(len(points)-1)), "strictly increasing"
    assert points[0] <= x_lb, "breakpoints must cover lower bound"
    assert points[-1] >= x_ub, "breakpoints must cover upper bound"
```

```text id="0n8as1"
Piecewise best practices:
  finite x bounds
  breakpoints cover x bounds
  monotonic breakpoint order
  scaled x/y units
  test breakpoint values
  test midpoint interpolation
  benchmark SOS2 vs CC/DCC/LOG for large models
```

---

## 15.7 Nonlinear expression handling and solver routing

### 15.7.1 Pyomo+SCIP model class routing

```text id="cu8xlf"
Linear + integer:
  MILP -> SCIP strong fit

Quadratic + integer:
  MIQP/MIQCP -> SCIP fit; bounds/scaling important

Nonlinear + integer:
  MINLP -> SCIP fit if bounded and domain-safe

Continuous nonlinear only:
  try IPOPT for local NLP first if global/integer logic not needed

Nonlinear with binary products:
  linearize exact binary-continuous products when possible
  leave general nonlinear only when necessary
```

SCIP is designed for CIPs, a generalization of MILPs and MINLPs; the SCIP 10 report describes CIPs as finite-dimensional problems with arbitrary constraints and a linear objective where fixing integer variables yields an LP or NLP subproblem. ([arXiv][11])

### 15.7.2 Nonlinear handler parameter diagnostics

```python id="jv7jki"
opt.options["constraints/nonlinear/maxproprounds"] = 20
opt.options["constraints/nonlinear/reformbinprods"] = "TRUE"
opt.options["constraints/nonlinear/reformbinprodsand"] = "TRUE"
opt.options["constraints/nonlinear/weakcutthreshold"] = 0.1

opt.options["display/relevantstats"] = "TRUE"
opt.options["table/constraint/active"] = "TRUE"
opt.options["table/nlp/active"] = "TRUE"
```

SCIP’s parameter list exposes `constraints/nonlinear/*` controls, including nonlinear propagation rounds, binary-product reformulation, and weak-cut threshold parameters. ([SCIP Optimization Library][1])

---

## 15.8 Infeasibility and near-bound diagnostics

Pyomo provides `log_infeasible_constraints`, which logs infeasible constraints using the current model state and supports options for logging expressions and variables. ([Pyomo Documentation][12])

```python id="63scy6"
import logging
from pyomo.util.infeasible import (
    log_infeasible_constraints,
    log_infeasible_bounds,
    log_close_to_bounds,
)

logging.basicConfig(level=logging.INFO)

log_infeasible_constraints(
    m,
    tol=1e-6,
    log_expression=True,
    log_variables=True,
)

log_infeasible_bounds(m, tol=1e-6)
log_close_to_bounds(m, tol=1e-6)
```

Diagnostic workflow:

```text id="a2zv5m"
If infeasible:
  1. solve with keepfiles=True and symbolic_solver_labels=True
  2. inspect SCIP log
  3. run log_infeasible_constraints on current model state
  4. relax integrality
  5. deactivate constraint blocks incrementally
  6. audit bounds and big-M
  7. rerun with presolving/maxrounds=0 for mapping
```

---

## 15.9 Model-quality audit harness

```python id="b27r4w"
from pyomo.environ import *
from pyomo.repn import generate_standard_repn

def audit_model_quality(model):
    report = {
        "missing_bounds": [],
        "wide_bounds": [],
        "large_linear_coefficient_ranges": [],
        "general_nonlinear": [],
        "high_degree_polynomial": [],
        "binary_semantics_suspect": [],
    }

    for v in model.component_data_objects(Var, active=True):
        if v.lb is None or v.ub is None:
            report["missing_bounds"].append(v.name)
        elif v.ub - v.lb > 1e8:
            report["wide_bounds"].append((v.name, v.lb, v.ub))

        # Suspicious continuous [0,1] variable
        if (not v.is_binary()) and v.lb == 0 and v.ub == 1 and v.domain is not Binary:
            report["binary_semantics_suspect"].append(v.name)

    for con in model.component_data_objects(Constraint, active=True):
        if con.body is None:
            continue

        deg = con.body.polynomial_degree()
        if deg is None:
            report["general_nonlinear"].append(con.name)
        elif deg > 2:
            report["high_degree_polynomial"].append((con.name, deg))

        repn = generate_standard_repn(con.body)
        if repn.is_linear():
            coefs = [abs(value(c)) for c in repn.linear_coefs if value(c) != 0]
            if coefs:
                lo, hi = min(coefs), max(coefs)
                if lo > 0 and hi / lo > 1e8:
                    report["large_linear_coefficient_ranges"].append((con.name, lo, hi, hi / lo))

    return report
```

Use:

```python id="gyj42z"
report = audit_model_quality(m)
for k, v in report.items():
    print(k, len(v))
    for item in v[:20]:
        print("  ", item)
```

---

## 15.10 SCIP option guardrails for numeric debugging

### 15.10.1 Diagnostic profile

```python id="3xx7la"
def apply_numeric_debug_profile(opt):
    opt.options["display/verblevel"] = 5
    opt.options["display/allviols"] = "TRUE"
    opt.options["display/relevantstats"] = "TRUE"
    opt.options["table/lp/active"] = "TRUE"
    opt.options["table/nlp/active"] = "TRUE"
    opt.options["table/constraint/active"] = "TRUE"

    # Use defaults explicitly; do not tighten blindly.
    opt.options["numerics/feastol"] = 1e-6
    opt.options["numerics/epsilon"] = 1e-9
    opt.options["numerics/sumepsilon"] = 1e-6
```

### 15.10.2 Tolerance anti-pattern

```text id="zlqngf"
Bad:
  infeasible/violating result -> immediately set numerics/feastol = 1e-12

Better:
  inspect scaling
  inspect big-M
  inspect coefficient ranges
  inspect variable bounds
  inspect domain violations
  only then adjust tolerances, and benchmark side effects
```

SCIP’s FAQ describes feasibility comparisons relative to `numerics/feastol`, which means changing tolerance changes solver interpretation of feasibility; it should be treated as a numerical policy decision, not a substitute for formulation quality. ([SCIP Optimization Library][13])

---

## 15.11 Integrated best-practice templates

### 15.11.1 SCIP-friendly MILP template

```python id="nhu4dj"
m = ConcreteModel()

m.I = Set(initialize=data.items)

m.x = Var(m.I, domain=Binary)
m.q = Var(m.I, domain=NonNegativeReals, bounds=lambda m, i: (0, data.max_q[i]))

m.capacity = Constraint(
    expr=sum(m.q[i] for i in m.I) <= data.total_capacity
)

m.link = Constraint(
    m.I,
    rule=lambda m, i: m.q[i] <= data.max_q[i] * m.x[i],
)

m.obj = Objective(
    expr=sum(data.cost[i] * m.q[i] + data.fixed[i] * m.x[i] for i in m.I),
    sense=minimize,
)
```

### 15.11.2 SCIP-friendly MINLP template

```python id="wmu5bo"
m = ConcreteModel()

m.x = Var(bounds=(1e-4, 100), initialize=1.0)  # log-safe
m.y = Var(bounds=(0, 50), initialize=5.0)      # sqrt-safe
m.z = Var(domain=Binary)

m.c1 = Constraint(expr=log(m.x) + sqrt(m.y) <= 5)
m.c2 = Constraint(expr=m.x * m.y <= 100 + 50 * m.z)

m.obj = Objective(expr=(m.x - 3)**2 + m.y + 10*m.z)
```

### 15.11.3 GDP template with explicit M

```python id="a0rlxq"
m.BigM = Suffix(direction=Suffix.LOCAL)

# after disjunct constraints are built
m.BigM[m.some_disjunct.some_constraint] = (-M_lower, M_upper)

TransformationFactory("gdp.bigm").apply_to(m)
```

### 15.11.4 Piecewise template

```python id="9ek4zy"
m.x = Var(bounds=(0, 100))
m.y = Var()

pts = [0, 10, 20, 50, 100]
vals = [0, 4, 7, 13, 20]

validate_piecewise_breakpoints(pts, 0, 100)

m.pw = Piecewise(
    m.y,
    m.x,
    pw_pts=pts,
    f_rule=vals,
    pw_constr_type="EQ",
    pw_repn="SOS2",
)
```

---

## 15.12 Deployment checklist

```text id="c2cj29"
Before first SCIP solve:
  audit missing bounds
  audit coefficient ranges
  audit accidental continuous [0,1] variables
  audit nonlinear domains
  validate piecewise breakpoints
  validate big-M derivations
  choose GDP transformation deliberately

For debug runs:
  tee=True
  logfile="scip.log"
  keepfiles=True
  symbolic_solver_labels=True
  load_solutions=False
  display/allviols=TRUE
  display/relevantstats=TRUE

For production:
  pin environment
  store opt.options
  store model data hash
  store SCIP log
  store termination/gap/primal/dual
  avoid unreviewed tolerance changes
```

---

## 15.13 Decision matrix

| Issue              | First fix                  | Second fix                  | Solver parameter last resort |
| ------------------ | -------------------------- | --------------------------- | ---------------------------- |
| infeasible         | data/bounds/logical audit  | Pyomo infeasibility logs    | presolve off for mapping     |
| unbounded          | add physical bounds        | objective-sense audit       | none                         |
| huge gap           | tighten big-M/formulation  | add valid inequalities      | more separation              |
| no incumbent       | feasibility formulation    | heuristic/initial candidate | heuristic frequencies        |
| numeric violations | scale units/constraints    | tighten bounds              | `numerics/*`                 |
| MINLP unstable     | explicit nonlinear domains | linearize binary products   | nonlinear handler params     |
| piecewise slow     | compare SOS2/CC/DCC/LOG    | reduce breakpoints          | separator/presolve tuning    |
| GDP slow           | improve M or use hull      | simplify disjunctions       | cut/presolve tuning          |

---

## 15.14 Compact mental model

```text id="tuy0l4"
Scaling:
  use coherent units
  scale objective/constraints
  avoid extreme coefficient ranges
  use Pyomo scaling_factor suffix or ScaleModel when needed

Bounds:
  finite bounds first
  tight bounds second
  derive big-M from bounds
  perform bound-tightening for critical variables

Integrality:
  Binary for true 0/1
  Integer for counts
  Continuous for relaxable quantities
  fix variables for scenarios/decomposition
  initial values are not guaranteed SCIP MIP starts through Pyomo unless verified

Nonlinear:
  guard log/sqrt/division/powers
  finite domains on nonlinear variables
  linearize binary-continuous products when exact
  reduce expression complexity

Transformations:
  Big-M = compact but weaker; M quality critical
  Hull = stronger but larger; bounded variables required
  Piecewise = representation choice affects performance; SOS2 is a strong default with SCIP
  Logical constraints must be transformed before SCIP solve

Golden rule:
  numerical stability is mostly formulation quality, not solver tolerance tuning.
```

[1]: https://www.scipopt.org/doc/html/PARAMETERS.php?utm_source=chatgpt.com "List of all SCIP parameters"
[2]: https://pyomo.readthedocs.io/en/6.9.0/api/pyomo.core.base.var.Var.html?utm_source=chatgpt.com "Var — Pyomo 6.9.0 documentation"
[3]: https://pyomo.readthedocs.io/en/stable/api/pyomo.repn.plugins.nl_writer.NLWriter.html?utm_source=chatgpt.com "NLWriter - Pyomo Documentation 6.10.0"
[4]: https://pyomo.readthedocs.io/en/6.9.1/api/pyomo.core.plugins.transform.scaling.ScaleModel.html?utm_source=chatgpt.com "ScaleModel — Pyomo 6.9.1 documentation"
[5]: https://pyomo.readthedocs.io/en/6.8.2/api/pyomo.gdp.plugins.bigm.BigM_Transformation.html?utm_source=chatgpt.com "BigM_Transformation — Pyomo 6.8.2 documentation"
[6]: https://pyomo.readthedocs.io/en/6.8.1/_modules/pyomo/core/base/var.html?utm_source=chatgpt.com "Source code for pyomo.core.base.var"
[7]: https://pyomo.readthedocs.io/en/6.9.1/howto/solver_recipes.html?utm_source=chatgpt.com "Solver Recipes — Pyomo 6.9.1 documentation"
[8]: https://pyscipopt.readthedocs.io/en/stable/tutorials/expressions.html?utm_source=chatgpt.com "Non-Linear Expressions - PySCIPOpt Documentation"
[9]: https://pyomo.readthedocs.io/en/6.8.0/modeling_extensions/gdp/solving.html?utm_source=chatgpt.com "Solving Logic-based Models with Pyomo.GDP"
[10]: https://pyomo.readthedocs.io/en/6.8.1/api/pyomo.core.base.piecewise.Piecewise.html?utm_source=chatgpt.com "Piecewise — Pyomo 6.8.1 documentation"
[11]: https://arxiv.org/html/2511.18580v1?utm_source=chatgpt.com "The SCIP Optimization Suite 10.0"
[12]: https://pyomo.readthedocs.io/en/latest/api/pyomo.util.infeasible.log_infeasible_constraints.html?utm_source=chatgpt.com "log_infeasible_constraints — Pyomo 6.10.1.dev0 documentation"
[13]: https://www.scipopt.org/doc/html/FAQ.php?utm_source=chatgpt.com "Frequently Asked Questions (FAQ)"


# 16) Infeasibility analysis and debugging — Pyomo + SCIP

Dense technical reference for LLM programming agents. Style aligned with the uploaded advanced-doc pattern. 

---

## 16.0 Debugging mental model

```text id="0cs02w"
Infeasibility debugging layers:
  1. Pyomo model-construction layer:
       wrong data
       wrong index sets
       missing bounds
       sign errors
       incorrect conditional constraints
       weak/invalid big-M
       unit/scale mistakes

  2. Pyomo expression/instance layer:
       constraints created but not intended
       inactive/active component mismatch
       variable domains wrong
       Params wrong
       transformed GDP/piecewise model wrong

  3. Solver/export layer:
       .nl representation
       presolve reductions
       SCIP infeasibility proof
       conflict analysis
       IIS / MinUC tooling

  4. Cross-solver layer:
       compare relaxed LP/MIP/NLP behavior
       compare another solver if model class permits
```

Pyomo’s `log_infeasible_constraints` logs infeasible constraints for the current model state, uses an absolute feasibility tolerance, and can optionally print expressions and variable values; this is a model-state diagnostic, not a solver-generated IIS proof. ([pyomo.readthedocs.io][1])

---

## 16.1 First rule: never load or trust values blindly after infeasible termination

```python id="dr6en8"
from pyomo.environ import SolverFactory
from pyomo.opt import SolverStatus, TerminationCondition

opt = SolverFactory("scip", solver_io="nl")

res = opt.solve(
    model,
    tee=True,
    logfile="scip-infeasible.log",
    keepfiles=True,
    symbolic_solver_labels=True,
    load_solutions=False,
)

tc = res.solver.termination_condition

if tc == TerminationCondition.optimal:
    model.solutions.load_from(res)
elif tc == TerminationCondition.infeasible:
    raise RuntimeError("SCIP reports infeasible; enter infeasibility-debug workflow.")
else:
    raise RuntimeError(f"Unexpected termination: {res.solver.status=} {tc=}")
```

Pyomo’s documented safe pattern is `load_solutions=False`, inspect `results.solver.termination_condition`, and call `model.solutions.load_from(results)` only when the result is acceptable; Pyomo examples also show checking `SolverStatus.ok` with `TerminationCondition.optimal` before treating the result as feasible/optimal. ([pyomo.readthedocs.io][2])

---

## 16.2 Pyomo-level tools

### 16.2.1 `log_infeasible_constraints`

```python id="ivz7ot"
import logging
from pyomo.util.infeasible import log_infeasible_constraints

logging.basicConfig(level=logging.INFO)

log_infeasible_constraints(
    model,
    tol=1e-6,
    log_expression=True,
    log_variables=True,
)
```

Signature:

```python id="eo2rwp"
log_infeasible_constraints(
    m,
    tol=1e-6,
    logger=<Logger pyomo.util.infeasible>,
    log_expression=False,
    log_variables=False,
)
```

Semantics:

```text id="xhi927"
Uses current model state.
Logs at INFO level.
Does not solve a diagnostic optimization problem.
Does not compute IIS.
Requires variable values to be meaningful.
Most useful after:
  a previous feasible/near-feasible solve
  manual variable assignment
  relaxed-model solution loaded
  slack-minimization diagnostic solution loaded
```

The Pyomo API states that `log_infeasible_constraints` logs infeasible constraints in a Pyomo block/model, uses the current model state, logs messages at INFO level, and supports `tol`, `log_expression`, and `log_variables` arguments. ([pyomo.readthedocs.io][1])

### 16.2.2 `model.pprint()` and component-level `pprint()`

```python id="665oax"
model.pprint()
model.x.pprint()
model.MyConstraint.pprint()
```

Use cases:

```text id="1qungg"
pprint:
  verify components exist
  verify index sets
  verify bounds
  verify domains
  verify constraint expressions
  verify transformed model structure
```

Pyomo’s model-interrogation docs show `model.pprint()` and component-level `model.x.pprint()` as the standard way to display the model or individual components. ([pyomo.readthedocs.io][3])

### 16.2.3 `display()` for values

```python id="fe4xcc"
model.display()
model.x.display()
model.MyConstraint.display()
```

Use cases:

```text id="hhyq58"
display:
  inspect current variable values
  inspect evaluated constraints/objectives
  compare values after relaxed/slack solve
```

### 16.2.4 Constraint slack inspection

Pyomo constraints expose lower and upper slack functions:

```python id="xoo2yx"
from pyomo.environ import Constraint, value

def constraint_slack_report(model, tol=1e-6, limit=100):
    rows = []
    for c in model.component_data_objects(Constraint, active=True):
        try:
            ls = c.lslack()
            us = c.uslack()
        except Exception as e:
            rows.append((c.name, None, None, f"eval_error: {e!r}"))
            continue

        status = "ok"
        if ls is not None and ls < -tol:
            status = "lower_violated"
        if us is not None and us < -tol:
            status = "upper_violated"

        if status != "ok":
            rows.append((c.name, ls, us, status))

    return rows[:limit]

for row in constraint_slack_report(model):
    print(row)
```

Pyomo’s model documentation states that `lslack()` and `uslack()` return lower and upper slacks for a constraint. ([pyomo.readthedocs.io][2])

### 16.2.5 Bounds and near-bound diagnostics

```python id="ltqw07"
from pyomo.environ import Var

def variable_bound_report(model, tol=1e-7):
    rows = []
    for v in model.component_data_objects(Var, active=True):
        val = v.value
        if val is None:
            continue

        if v.lb is not None and val < v.lb - tol:
            rows.append((v.name, val, v.lb, v.ub, "below_lb"))

        if v.ub is not None and val > v.ub + tol:
            rows.append((v.name, val, v.lb, v.ub, "above_ub"))

        if v.lb is not None and abs(val - v.lb) <= tol:
            rows.append((v.name, val, v.lb, v.ub, "near_lb"))

        if v.ub is not None and abs(val - v.ub) <= tol:
            rows.append((v.name, val, v.lb, v.ub, "near_ub"))

    return rows
```

---

## 16.3 SCIP-level tools

### 16.3.1 SCIP infeasibility messages

```text id="ncqnj5"
SCIP/Pyomo result fields to preserve:
  results.solver.status
  results.solver.termination_condition
  results.solver.message
  results.solver.time
  results.solver.gap
  results.solver.primal_bound
  results.solver.dual_bound
  len(results.solution)
```

```python id="5dwkph"
def summarize_solver_result(res):
    return {
        "status": str(res.solver.status),
        "termination_condition": str(res.solver.termination_condition),
        "message": str(getattr(res.solver, "message", "")),
        "time": getattr(res.solver, "time", None),
        "gap": getattr(res.solver, "gap", None),
        "primal_bound": getattr(res.solver, "primal_bound", None),
        "dual_bound": getattr(res.solver, "dual_bound", None),
        "n_solutions": len(res.solution),
    }
```

### 16.3.2 SCIP conflict analysis

```text id="gyhgdq"
Conflict analysis:
  automatic use of infeasible node information
  learns a constraint explaining infeasibility of the current node
  attempts to avoid similar infeasible search states later
  constructs conflict graph from variable bound changes and propagation dependencies
```

SCIP’s conflict-analysis docs state that conflict analysis uses information from infeasible branch-and-bound nodes; once a node is infeasible, SCIP tries to infer a constraint explaining the infeasibility to avoid similar search states, and it uses a conflict graph over variable bound changes and propagation dependencies. ([scipopt.org][4])

SCIP conflict-related parameters include `conflict/enable`, `conflict/useprop`, `conflict/useinflp`, `conflict/useboundlp`, `conflict/maxvarsfac`, `conflict/maxconss`, and conflict-store controls; `conflict/enable` and `conflict/useprop` default to `TRUE` in the current parameter list. ([scipopt.org][5])

Pyomo-side conflict diagnostic profile:

```python id="5er9df"
def apply_conflict_debug_options(opt):
    opt.options["conflict/enable"] = "TRUE"
    opt.options["conflict/useprop"] = "TRUE"
    opt.options["conflict/useinflp"] = "b"      # both conflict graph and dual ray
    opt.options["conflict/useboundlp"] = "b"
    opt.options["display/verblevel"] = 5
    opt.options["display/relevantstats"] = "TRUE"
    opt.options["table/conflict/active"] = "TRUE"
    opt.options["table/constraint/active"] = "TRUE"
```

### 16.3.3 SCIP IIS and MinUC infeasibility explanation

```text id="d6a9m3"
SCIP IIS:
  irreducible infeasible subsystem
  subset of original constraints and variable bounds
  still infeasible
  removing any additional included constraint makes it feasible
  useful for isolating formulation/data defects

SCIP MinUC:
  transforms problem to minimize number of unsatisfied constraints
  solution identifies constraints whose relaxation/removal can induce feasibility
```

SCIP’s infeasibility-explanation documentation says there are two main ways to analyze infeasible instances: IIS functionality and MinUC functionality. The IIS procedure produces a smaller infeasible problem containing a subset of original constraints and variable bounds, and the MinUC procedure changes the problem to minimize the number of unsatisfied constraints. ([scipopt.org][6])

Standalone SCIP IIS commands:

```text id="6iozn5"
SCIP> read path_to_instance
SCIP> iis
SCIP> display/iis
SCIP> write/iis path_to_iis_output
```

Standalone SCIP MinUC commands:

```text id="vp1f9o"
SCIP> read path_to_instance
SCIP> change/minuc
SCIP> optimize
SCIP> display/solution
```

SCIP’s FAQ states that IIS can be called from the command line with `iis` or from the C API with `SCIPgenerateIIS()`, and that after computing the IIS it can be printed with `display/iis` or `write/iis`; it also describes `change/minuc` as transforming the current problem so optimization minimizes the number of unsatisfied constraints. ([scipopt.org][7])

### 16.3.4 Pyomo-to-SCIP IIS bridge

```text id="7c7nxt"
Best practice:
  Pyomo -> keepfiles=True, symbolic_solver_labels=True
  preserve .nl, .row, .col, .log, .sol
  if IIS required:
    run standalone SCIP on an equivalent file format
    prefer LP/MPS/CIP if model is linear/quadratic and exportable
    use Pyomo .nl replay only after verifying SCIP IIS supports the reader path for the target model
```

Pyomo’s SCIP path is external NL/SOL-based; Pyomo’s SCIP plugin writes NL and receives SOL, so solver-native IIS/MinUC workflows may require standalone SCIP replay and careful artifact mapping.

---

## 16.4 Workflow A: immediate Pyomo infeasibility triage

```python id="jvwjy9"
from pyomo.environ import SolverFactory
from pyomo.opt import TerminationCondition

opt = SolverFactory("scip", solver_io="nl")
apply_conflict_debug_options(opt)

res = opt.solve(
    model,
    tee=True,
    logfile="debug/scip.log",
    keepfiles=True,
    symbolic_solver_labels=True,
    load_solutions=False,
)

if res.solver.termination_condition == TerminationCondition.infeasible:
    print("SCIP says infeasible")
    print(summarize_solver_result(res))

    # Model-state diagnostics: meaningful only for current variable values
    import logging
    logging.basicConfig(level=logging.INFO)
    log_infeasible_constraints(
        model,
        tol=1e-6,
        log_expression=True,
        log_variables=True,
    )
```

Interpretation:

```text id="8b08h2"
If variables have no meaningful values:
  log_infeasible_constraints may report evaluation errors or irrelevant violations.
Next:
  solve relaxed/slack model
  then run model-state diagnostics on that loaded diagnostic solution
```

---

## 16.5 Workflow B: solve relaxed model

### 16.5.1 Integrality relaxation

Use `core.relax_integer_vars`, not deprecated `core.relax_integrality`.

```python id="vzspcu"
from pyomo.environ import TransformationFactory, SolverFactory, value

relaxed = TransformationFactory("core.relax_integer_vars").create_using(model)

relax_opt = SolverFactory("scip", solver_io="nl")
relax_opt.options["limits/time"] = 300

relax_res = relax_opt.solve(
    relaxed,
    tee=True,
    logfile="debug/relaxed-scip.log",
    load_solutions=False,
)

if len(relax_res.solution) > 0:
    relaxed.solutions.load_from(relax_res)
```

Pyomo documents `RelaxIntegerVars` as the transformation that relaxes integer variables to continuous counterparts; `core.relax_integrality` is deprecated in favor of `core.relax_integer_vars`. ([pyomo.readthedocs.io][8])

### 16.5.2 Relaxation diagnostic interpretation

```text id="1j0mp7"
If relaxed model feasible but original infeasible:
  integrality logic likely implicated
  binary/integer domains + big-M + disjunctions + fixed variables
  check linking constraints and logical formulations

If relaxed model infeasible:
  pure algebraic/bounds/data contradiction exists
  integrality is not the primary cause
  proceed to slack/IIS/constraint-isolation workflow

If relaxed model unbounded:
  missing bounds or wrong objective sense
```

### 16.5.3 Copy relaxed solution back as initial guess

```python id="msl3bi"
def transfer_values_by_name(src, dst):
    src_vars = {
        v.name: v.value
        for v in src.component_data_objects(Var, active=True)
        if v.value is not None
    }
    for v in dst.component_data_objects(Var, active=True):
        if v.name in src_vars:
            try:
                v.set_value(src_vars[v.name], skip_validation=True)
            except Exception:
                pass
```

---

## 16.6 Workflow C: slack-penalty feasibility relaxation

### 16.6.1 Pyomo built-in slack transformation

```python id="l7otm7"
from pyomo.environ import TransformationFactory

slack_model = TransformationFactory("core.add_slack_variables").create_using(model)

res = SolverFactory("scip", solver_io="nl").solve(
    slack_model,
    tee=True,
    logfile="debug/slack-scip.log",
    load_solutions=False,
)

if len(res.solution) > 0:
    slack_model.solutions.load_from(res)
    slack_model.display()
```

Pyomo’s `core.add_slack_variables` transformation creates slack variables for constraints and a new objective that minimizes the sum of slack variables; if a constraint has a lower bound greater than its upper bound, it raises a structural infeasibility error because slacks cannot repair that. ([pyomo.readthedocs.io][9])

### 16.6.2 Manual targeted slack pattern

```python id="ka9bez"
from pyomo.environ import *

m = model.clone()

m._debug_slack = Var(m.SUSPECT_CONSTRAINTS, domain=NonNegativeReals)

# Example: upper-bound constraint body <= ub becomes body <= ub + slack[i]
def relaxed_rule(m, i):
    return suspect_body(m, i) <= suspect_ub[i] + m._debug_slack[i]

m.SuspectRelaxed = Constraint(m.SUSPECT_CONSTRAINTS, rule=relaxed_rule)

# Disable original suspect constraints if needed
m.OriginalSuspectConstraint.deactivate()

# Minimize total violation
for obj in m.component_data_objects(Objective, active=True):
    obj.deactivate()

m._debug_slack_obj = Objective(expr=sum(m._debug_slack[i] for i in m.SUSPECT_CONSTRAINTS))
```

### 16.6.3 Slack interpretation

```text id="sw10n8"
Positive slack:
  constraint family requires relaxation at diagnostic solution

Large slack:
  likely bad data, wrong sign, wrong bound, wrong unit, impossible demand/capacity

Zero slack:
  constraint not implicated in this diagnostic relaxation

Caveat:
  slack-min solution is not IIS
  multiple alternative relaxations can exist
  objective scaling of slacks matters
```

---

## 16.7 Workflow D: add constraints incrementally

### 16.7.1 Activate blocks one at a time

```python id="sw6jch"
from pyomo.environ import Block, Constraint, Objective

def deactivate_constraint_blocks(model):
    for block in model.component_objects(Block, descend_into=False):
        if block.name.startswith("cons_"):
            block.deactivate()

def test_incremental_blocks(model, block_names, opt):
    for name in block_names:
        getattr(model, name).activate()
        res = opt.solve(model, tee=False, load_solutions=False)
        print(name, res.solver.termination_condition)
        if str(res.solver.termination_condition).lower().endswith("infeasible"):
            return name, res
    return None, None
```

### 16.7.2 Constraint family bisection

```python id="w9un2d"
from pyomo.environ import Constraint

def set_constraint_active(constraints, active):
    for c in constraints:
        if active:
            c.activate()
        else:
            c.deactivate()

def find_infeasible_subset_by_bisection(model, constraints, opt):
    constraints = list(constraints)

    def infeasible(active_subset):
        set_constraint_active(constraints, False)
        set_constraint_active(active_subset, True)
        res = opt.solve(model, tee=False, load_solutions=False)
        return "infeasible" in str(res.solver.termination_condition).lower()

    current = constraints
    if not infeasible(current):
        return []

    while len(current) > 1:
        mid = len(current) // 2
        left, right = current[:mid], current[mid:]

        if infeasible(left):
            current = left
        elif infeasible(right):
            current = right
        else:
            # infeasibility caused by interaction across halves
            break

    set_constraint_active(constraints, True)
    return current
```

### 16.7.3 Incremental build pattern for agents

```text id="04v6mu"
Build order:
  1. variables + bounds only
  2. objective only
  3. physical conservation
  4. capacity constraints
  5. logical/binary linking constraints
  6. big-M constraints
  7. disjunction/GDP transformations
  8. nonlinear constraints
  9. integrality restored
```

---

## 16.8 Workflow E: inspect bounds and big-M values

### 16.8.1 Missing and wide bounds

```python id="bz3hxp"
from pyomo.environ import Var

def audit_bounds(model, wide=1e8):
    rows = []
    for v in model.component_data_objects(Var, active=True):
        lb, ub = v.lb, v.ub
        if lb is None or ub is None:
            rows.append((v.name, lb, ub, "missing"))
        elif ub - lb > wide:
            rows.append((v.name, lb, ub, "wide"))
        elif abs(lb) > wide or abs(ub) > wide:
            rows.append((v.name, lb, ub, "large_magnitude"))
    return rows
```

### 16.8.2 Big-M report

```python id="mv8bad"
def report_big_m(M_by_constraint, threshold=1e6):
    rows = []
    for name, M in M_by_constraint.items():
        if isinstance(M, tuple):
            vals = [abs(v) for v in M if v is not None]
            maxM = max(vals) if vals else 0
        else:
            maxM = abs(M)
        if maxM >= threshold:
            rows.append((name, M, "large_M"))
    return rows
```

### 16.8.3 Derive M from bounds

```python id="j4olfc"
def linear_expr_bounds(coefs, lbs, ubs):
    lo = 0.0
    hi = 0.0
    for i, a in coefs.items():
        if a >= 0:
            lo += a * lbs[i]
            hi += a * ubs[i]
        else:
            lo += a * ubs[i]
            hi += a * lbs[i]
    return lo, hi

# z = 1 -> sum(a_i*x_i) <= rhs
expr_lo, expr_hi = linear_expr_bounds(a, lb, ub)
M = max(0.0, expr_hi - rhs)
```

Debug rule:

```text id="0h0vgu"
If M is large because a variable is unbounded:
  do not tune SCIP first
  derive/introduce a real bound
```

---

## 16.9 Workflow F: compare with another solver

### 16.9.1 Solver comparison matrix

```text id="2djrgt"
If MILP:
  compare SCIP with HiGHS/CBC/Gurobi/CPLEX if available

If LP relaxation:
  compare with HiGHS or any LP solver

If continuous NLP:
  compare with IPOPT if smooth and no integer variables

If MINLP:
  compare with Couenne/BONMIN/SCIP where installed and model class permits
```

### 16.9.2 Compare relaxed MILP with HiGHS

```python id="gvn5a2"
relaxed = TransformationFactory("core.relax_integer_vars").create_using(model)

for solver_name in ["scip", "highs"]:
    opt = SolverFactory(solver_name)
    if not opt.available(False):
        continue
    res = opt.solve(relaxed, tee=True, load_solutions=False)
    print(solver_name, res.solver.status, res.solver.termination_condition)
```

### 16.9.3 Cross-solver interpretation

```text id="4lhh5p"
Both solvers infeasible:
  likely model/data contradiction

SCIP infeasible, other solver feasible:
  inspect solver tolerances, nonlinear support, export format, model class, transformations

One solver unbounded:
  inspect missing bounds and objective sense

LP relaxation feasible, MIP infeasible:
  integrality/logical linking issue

NLP feasible, MINLP infeasible:
  discrete constraints/linking issue
```

---

## 16.10 Artifacts to preserve

### 16.10.1 Required debug artifacts

```text id="5zny3x"
Preserve:
  model data snapshot
  environment.yml / lockfile
  scip --version output
  Pyomo version
  solver option manifest
  generated scip.set equivalent
  .nl
  .row
  .col
  .sol if produced
  .log
  results summary JSON
  transformed model export if GDP/piecewise transformations used
```

### 16.10.2 Debug solve call

```python id="fpimdj"
res = opt.solve(
    model,
    tee=True,
    logfile="debug/scip.log",
    keepfiles=True,
    symbolic_solver_labels=True,
    load_solutions=False,
)
```

### 16.10.3 Write options manifest

```python id="israhx"
import json
from pathlib import Path

def write_scip_options(opt, path):
    data = {str(k): str(v) for k, v in sorted(opt.options.items()) if k != "solver"}
    Path(path).write_text(json.dumps(data, indent=2, sort_keys=True))

def write_scip_set_equivalent(opt, path):
    lines = [f"{k} = {v}" for k, v in sorted(opt.options.items()) if k != "solver"]
    Path(path).write_text("\n".join(lines) + "\n")
```

### 16.10.4 Write model snapshot

```python id="ytia0b"
from pathlib import Path
import json

def write_debug_bundle(model, opt, res, run_dir="debug"):
    d = Path(run_dir)
    d.mkdir(parents=True, exist_ok=True)

    write_scip_options(opt, d / "scip-options.json")
    write_scip_set_equivalent(opt, d / "scip-from-pyomo-options.set")

    (d / "solver-summary.json").write_text(
        json.dumps(summarize_solver_result(res), indent=2, sort_keys=True)
    )

    model.write(
        str(d / "model.nl"),
        format="nl",
        io_options={"symbolic_solver_labels": True, "file_determinism": 30},
    )

    try:
        model.write(
            str(d / "model.lp"),
            format="lp",
            io_options={"symbolic_solver_labels": True, "file_determinism": 30},
        )
    except Exception as e:
        (d / "model-lp-export-failed.txt").write_text(repr(e))
```

---

## 16.11 Standalone SCIP IIS workflow from Pyomo artifact

### 16.11.1 Export LP when possible

```python id="rwupq2"
model.write(
    "debug/model.lp",
    format="lp",
    io_options={"symbolic_solver_labels": True, "file_determinism": 30},
)
```

### 16.11.2 Standalone IIS script

```bash id="9q7xft"
cat > debug/iis.scip <<'EOF'
read model.lp
iis
display/iis
write/iis model.iis.cip
quit
EOF

(
  cd debug
  scip < iis.scip > iis.log 2>&1
)
```

### 16.11.3 Standalone MinUC script

```bash id="422qyj"
cat > debug/minuc.scip <<'EOF'
read model.lp
change/minuc
optimize
display/solution
write solution minuc.sol
quit
EOF

(
  cd debug
  scip < minuc.scip > minuc.log 2>&1
)
```

Interpretation:

```text id="y0u8bi"
IIS output:
  reduced infeasible subproblem
  constraint/bound subset
  not necessarily smallest cardinality subsystem
  irreducible with respect to removing additional included constraints

MinUC output:
  constraints marked by originalconsname_master = 1
  candidate set of constraints to relax/remove for feasibility
```

SCIP’s FAQ says IIS output is irreducible but not guaranteed to be the smallest possible infeasible subsystem for the whole instance, and MinUC solution variables named `originalconsname_master` indicate constraints whose relaxation/removal can induce feasibility. ([scipopt.org][7])

---

## 16.12 End-to-end infeasibility playbook

```text id="pygmng"
Step 0: Reproduce
  same data
  same environment
  same solver options
  same random seeds/thread settings if relevant
  tee=True, logfile, keepfiles, symbolic labels

Step 1: Confirm termination
  SolverStatus
  TerminationCondition
  results.solver.message
  log tail

Step 2: Static model audit
  model.pprint()
  variable bounds
  domains
  fixed variables
  big-M values
  missing data
  impossible lower/upper bounds

Step 3: Relax integrality
  core.relax_integer_vars
  solve
  classify LP/NLP relaxation feasibility

Step 4: Slack minimization
  core.add_slack_variables
  identify violated constraint families

Step 5: Constraint isolation
  activate blocks incrementally
  bisection by constraint family
  check transformations

Step 6: SCIP IIS / MinUC
  export LP/MPS/CIP if possible
  standalone SCIP iis / change/minuc

Step 7: Cross-solver comparison
  MILP: HiGHS/CBC/commercial
  NLP: IPOPT
  MINLP: SCIP/Couenne/BONMIN where available

Step 8: Fix model
  data correction
  bounds
  big-M
  sign
  unit scaling
  domain guards
  transformation choice
```

---

## 16.13 Common infeasibility root causes

| Symptom                                   | Likely cause                                   | Diagnostic                                      |
| ----------------------------------------- | ---------------------------------------------- | ----------------------------------------------- |
| infeasible before branch-and-bound        | contradictory bounds/constraints               | presolve log, IIS, slack model                  |
| relaxed model feasible, MIP infeasible    | binary/integer logic issue                     | relax integrality, inspect linking constraints  |
| slack concentrated in demand constraints  | impossible demand vs capacity                  | slack transform, data audit                     |
| slack concentrated in big-M constraints   | invalid/tight M or wrong implication direction | derive M from bounds                            |
| unbounded relaxation but infeasible MIP   | missing bounds and discrete logic conflict     | bound audit                                     |
| infeasible only after GDP transformation  | wrong disjunction or M values                  | inspect transformed constraints                 |
| infeasible only in SCIP                   | solver/export/model-class issue                | compare another solver/export LP/NL             |
| `log_infeasible_constraints` not useful   | no meaningful variable values                  | solve relaxed/slack model first                 |
| IIS contains many transformed constraints | transformation obscured original model         | symbolic labels, preserve pre-transform mapping |

---

## 16.14 Recommended debug profiles

### 16.14.1 Pyomo/SCIP infeasibility-debug options

```python id="mwtitf"
def apply_infeasibility_debug_profile(opt):
    opt.options["limits/time"] = 600

    # Conflict diagnostics
    opt.options["conflict/enable"] = "TRUE"
    opt.options["conflict/useprop"] = "TRUE"
    opt.options["conflict/useinflp"] = "b"
    opt.options["conflict/useboundlp"] = "b"

    # More diagnostics
    opt.options["display/verblevel"] = 5
    opt.options["display/allviols"] = "TRUE"
    opt.options["display/relevantstats"] = "TRUE"
    opt.options["table/conflict/active"] = "TRUE"
    opt.options["table/constraint/active"] = "TRUE"
    opt.options["table/propagator/active"] = "TRUE"
    opt.options["table/presolver/active"] = "TRUE"
```

### 16.14.2 Presolve-off mapping profile

```python id="4vo9zz"
def apply_mapping_profile(opt):
    opt.options["presolving/maxrounds"] = 0
    opt.options["display/verblevel"] = 5
    opt.options["display/relevantstats"] = "TRUE"
```

Use when:

```text id="tjs0ec"
presolve removes/aggregates too much
IIS/logs hard to map back
need original constraint names
debugging, not performance
```

---

## 16.15 Agent-ready orchestration function

```python id="af8t7z"
from pyomo.environ import *
from pyomo.opt import TerminationCondition
from pyomo.util.infeasible import log_infeasible_constraints
import logging
from pathlib import Path

def diagnose_infeasible_pyomo_scip(model, run_dir="debug_infeasibility"):
    run = Path(run_dir)
    run.mkdir(parents=True, exist_ok=True)

    opt = SolverFactory("scip", solver_io="nl")
    if not opt.available(False):
        raise RuntimeError("SCIP unavailable")

    apply_infeasibility_debug_profile(opt)

    res = opt.solve(
        model,
        tee=True,
        logfile=str(run / "scip.log"),
        keepfiles=True,
        symbolic_solver_labels=True,
        load_solutions=False,
    )

    write_scip_options(opt, run / "scip-options.json")
    write_scip_set_equivalent(opt, run / "scip-from-pyomo-options.set")

    (run / "solver-summary.json").write_text(
        json.dumps(summarize_solver_result(res), indent=2, sort_keys=True)
    )

    # Always export deterministic snapshots.
    model.write(
        str(run / "model.nl"),
        format="nl",
        io_options={"symbolic_solver_labels": True, "file_determinism": 30},
    )

    try:
        model.write(
            str(run / "model.lp"),
            format="lp",
            io_options={"symbolic_solver_labels": True, "file_determinism": 30},
        )
    except Exception as e:
        (run / "model-lp-export-failed.txt").write_text(repr(e))

    if res.solver.termination_condition == TerminationCondition.infeasible:
        # Static/state diagnostic; current values may be uninitialized.
        logging.basicConfig(level=logging.INFO)
        log_infeasible_constraints(
            model,
            tol=1e-6,
            log_expression=True,
            log_variables=True,
        )

    # Relaxed model diagnostic
    relaxed = TransformationFactory("core.relax_integer_vars").create_using(model)
    relax_res = opt.solve(
        relaxed,
        tee=True,
        logfile=str(run / "relaxed-scip.log"),
        load_solutions=False,
    )

    (run / "relaxed-summary.json").write_text(
        json.dumps(summarize_solver_result(relax_res), indent=2, sort_keys=True)
    )

    # Slack diagnostic
    slack = TransformationFactory("core.add_slack_variables").create_using(model)
    slack_res = opt.solve(
        slack,
        tee=True,
        logfile=str(run / "slack-scip.log"),
        load_solutions=False,
    )

    (run / "slack-summary.json").write_text(
        json.dumps(summarize_solver_result(slack_res), indent=2, sort_keys=True)
    )

    return {
        "original": res,
        "relaxed": relax_res,
        "slack": slack_res,
    }
```

---

## 16.16 Compact mental model

```text id="51bi97"
Pyomo tools:
  log_infeasible_constraints:
    current model-state violation logger, not IIS

  model.pprint / component.pprint:
    structure and expression inspection

  c.lslack() / c.uslack():
    evaluated lower/upper slack for current variable values

  core.relax_integer_vars:
    remove integrality to separate algebraic infeasibility from discrete infeasibility

  core.add_slack_variables:
    build slack-penalty diagnostic model

SCIP tools:
  conflict analysis:
    learns from infeasible B&B nodes; mostly internal but log/table visible

  IIS:
    standalone SCIP `iis`, `display/iis`, `write/iis`

  MinUC:
    standalone SCIP `change/minuc`, then `optimize`, then inspect `originalconsname_master`

Workflow:
  reproduce -> preserve artifacts -> audit model -> relax integrality -> slack solve -> isolate constraints -> SCIP IIS/MinUC -> cross-solver compare -> fix data/formulation

Artifacts:
  .nl
  .row
  .col
  .lp if exportable
  .sol
  .log
  scip.set equivalent
  solver summary JSON
  model data snapshot
  environment/package snapshot
```

[1]: https://pyomo.readthedocs.io/en/latest/api/pyomo.util.infeasible.log_infeasible_constraints.html "log_infeasible_constraints — Pyomo 6.10.1.dev0 documentation"
[2]: https://pyomo.readthedocs.io/en/6.8.0/working_models.html "Working with Pyomo Models — Pyomo 6.8.0 documentation"
[3]: https://pyomo.readthedocs.io/en/6.8.0/model_debugging/model_interrogation.html?utm_source=chatgpt.com "Interrogating Pyomo Models — Pyomo 6.8.0 documentation"
[4]: https://www.scipopt.org/doc/html/CONF.php "SCIP Doxygen Documentation: How to use conflict analysis"
[5]: https://www.scipopt.org/doc/html/PARAMETERS.php "SCIP Doxygen Documentation: List of all SCIP parameters"
[6]: https://scipopt.org/scip/doc/html/MINUCIIS.php "SCIP Doxygen Documentation: How to deduce reasons for infeasibility in SCIP"
[7]: https://www.scipopt.org/doc/html/FAQ.php "SCIP Doxygen Documentation: Frequently Asked Questions (FAQ)"
[8]: https://pyomo.readthedocs.io/en/6.10.0/api/pyomo.core.plugins.transform.discrete_vars.RelaxIntegerVars.html?utm_source=chatgpt.com "RelaxIntegerVars - Pyomo Documentation 6.10.0"
[9]: https://pyomo.readthedocs.io/en/6.8.2/_modules/pyomo/core/plugins/transform/add_slack_vars.html "pyomo.core.plugins.transform.add_slack_vars — Pyomo 6.8.2 documentation"

# 17) Deployment patterns — Pyomo + SCIP production layout

Dense technical reference for LLM programming agents. Style aligned with the uploaded advanced-doc pattern. 

---

## 17.0 Deployment contract

```text id="4xna31"
Production Pyomo+SCIP deployment must guarantee:

  executable:
    scip visible inside the same runtime environment as Python/Pyomo

  package provenance:
    conda-forge package versions pinned
    channel priority strict
    environment not base/global

  runtime check:
    SolverFactory("scip").available(False)
    opt.executable()
    opt.version()
    scip --version

  solve artifacts:
    run_id/
      model.nl
      model.row
      model.col
      model.sol
      scip.log
      scip.set or scip-options.json
      results.json
      environment.json
      input-data snapshot

  result policy:
    solve(..., load_solutions=False)
    inspect status + termination
    load only when accepted
```

`conda-forge::scip` currently publishes SCIP 10.0.2, describes it as a “Constraint Integer Programming and Branch-and-Cut-and-Price Framework,” lists install command `conda install conda-forge::scip`, and supports Linux x86_64, Linux ARM64, Windows x86_64, macOS Intel, and macOS ARM platforms. The package metadata also lists a multi-license expression, so deployment documentation should record package-level license metadata, not only upstream SCIP’s project license. ([Anaconda][1])

---

## 17.1 Recommended repository / deployment structure

```text id="qdosxq"
project/
  env/
    environment.yml
    conda-lock.yml                  # optional but preferred for production
    explicit-linux-64.txt           # optional platform lock
    explicit-osx-arm64.txt          # optional platform lock
    explicit-win-64.txt             # optional platform lock

  src/
    myopt/
      __init__.py
      config.py
      envcheck.py
      solve.py
      cli.py
      reporting.py
      artifacts.py
      pyomo_models/
        __init__.py
        production_model.py
        relaxations.py
        diagnostics.py

  models/
    README.md
    formulations/
      production.md
      debug.md
      transformations.md

  data/
    raw/
    processed/
    scenarios/
      scenario_001.json

  runs/
    run_id/
      inputs/
        scenario.json
        config.json
        data_hash.txt
      model/
        model.nl
        model.row
        model.col
        model.lp                  # if exportable
      solver/
        scip.log
        scip.sol
        scip-options.json
        scip-from-pyomo-options.set
        scip-version.txt
        solver-summary.json
      results/
        results.json
        variables.csv
        objective.json
      env/
        environment.yml
        package-list.txt
        runtime-fingerprint.json

  tests/
    test_solver_available.py
    test_smoke_milp.py
    test_model_build.py
    test_expected_objective.py

  Dockerfile
  pyproject.toml
  README.md
```

---

## 17.2 Conda/micromamba environment patterns

### 17.2.1 `environment.yml`

```yaml id="kbj71h"
name: opt-scip
channels:
  - conda-forge
channel_priority: strict
dependencies:
  - python=3.11
  - pyomo
  - scip=10.0.2
  - pandas
  - pyyaml
  - pytest
```

### 17.2.2 Create named environment

```bash id="dq6yep"
micromamba create -n opt-scip -f env/environment.yml
micromamba activate opt-scip
```

### 17.2.3 Create prefix environment

```bash id="9ju37l"
micromamba create -p ./env/.micromamba -f env/environment.yml
micromamba run -p ./env/.micromamba python -m myopt.envcheck
```

### 17.2.4 CI/container-safe execution

```bash id="kz20mt"
micromamba run -n opt-scip python -m myopt.cli solve --config configs/prod.yaml
micromamba run -p /opt/env python -m myopt.cli solve --config configs/prod.yaml
```

Micromamba’s docs explicitly call out `micromamba run` as convenient for CI and Docker environments where shell activation hooks are complicated, and show `micromamba create -p /tmp/env ...` followed by `micromamba run -p /tmp/env ...`. ([Mamba][2])

### 17.2.5 Environment rules

```text id="g07cj5"
Do:
  use named or prefix environments
  pin SCIP in production
  keep conda-forge-only stack
  run application through micromamba run in CI/containers
  record exact scip executable path

Do not:
  rely on system/global scip
  rely on base environment
  mix unrelated scip executable with Pyomo from another env
  let PATH choose a stale solver silently
```

---

## 17.3 Startup executable checks

### 17.3.1 `src/myopt/envcheck.py`

```python id="hhlq4q"
from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from pathlib import Path

import pyomo
from pyomo.environ import SolverFactory


def run_text(cmd: list[str]) -> str:
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    ).stdout.strip()


def scip_runtime_fingerprint() -> dict:
    opt = SolverFactory("scip", solver_io="nl")
    available = opt.available(False)
    executable = opt.executable() if available else None

    return {
        "python_executable": sys.executable,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "pyomo_version": getattr(pyomo, "__version__", None),
        "conda_prefix": os.environ.get("CONDA_PREFIX"),
        "mamba_root_prefix": os.environ.get("MAMBA_ROOT_PREFIX"),
        "scip_available": available,
        "scip_executable": executable,
        "scip_version_tuple": tuple(opt.version()) if available else None,
        "scip_version_text": run_text([executable, "--version"]) if executable else None,
    }


def require_scip() -> dict:
    fp = scip_runtime_fingerprint()

    if not fp["scip_available"]:
        raise RuntimeError(
            "SCIP unavailable to Pyomo. Activate the conda/micromamba environment "
            "containing conda-forge::scip, or execute via `micromamba run -n <env> ...`."
        )

    exe = Path(fp["scip_executable"])
    py = Path(fp["python_executable"])

    if "CONDA_PREFIX" in os.environ:
        prefix = Path(os.environ["CONDA_PREFIX"]).resolve()
        if prefix not in exe.resolve().parents:
            raise RuntimeError(f"SCIP executable is outside active env: {exe}")
        if prefix not in py.resolve().parents:
            raise RuntimeError(f"Python executable is outside active env: {py}")

    return fp


if __name__ == "__main__":
    print(json.dumps(require_scip(), indent=2, sort_keys=True))
```

Pyomo’s solver APIs expose `executable()`, which returns the executable used by a solver, and `has_capability()`, which returns whether a solver supports a named feature; using these checks at startup is safer than trusting the shell `PATH` alone. ([Pyomo Documentation][3])

### 17.3.2 Shell checks

```bash id="nr17nl"
which scip || where scip
scip --version

python -m myopt.envcheck
```

### 17.3.3 Service startup gate

```python id="ncp5g9"
from myopt.envcheck import require_scip

SCIP_ENV = require_scip()
```

---

## 17.4 Local notebooks

### 17.4.1 Use case

```text id="u3yz59"
Local notebooks:
  formulation exploration
  scenario debugging
  solver-log inspection
  small/medium model runs
  visualization of results
```

### 17.4.2 Notebook bootstrap cell

```python id="xmfyy8"
from pathlib import Path
import json

from pyomo.environ import *
from pyomo.opt import SolverStatus, TerminationCondition

from myopt.envcheck import require_scip
from myopt.artifacts import make_run_dir, write_options_manifest, write_result_summary

fp = require_scip()
print(json.dumps(fp, indent=2))
```

### 17.4.3 Notebook solve pattern

```python id="sqvn3e"
run_dir = make_run_dir("notebook-debug")

opt = SolverFactory("scip", solver_io="nl")
opt.options["limits/time"] = 300
opt.options["limits/gap"] = 1e-4
opt.options["display/verblevel"] = 4
opt.options["display/relevantstats"] = "TRUE"

res = opt.solve(
    model,
    tee=True,
    logfile=str(run_dir / "solver" / "scip.log"),
    keepfiles=True,
    symbolic_solver_labels=True,
    load_solutions=False,
)

write_options_manifest(opt, run_dir / "solver" / "scip-options.json")
write_result_summary(res, run_dir / "solver" / "solver-summary.json")

if (
    res.solver.status == SolverStatus.ok
    and res.solver.termination_condition == TerminationCondition.optimal
):
    model.solutions.load_from(res)
```

### 17.4.4 Notebook guardrails

```text id="m9lnw6"
Do:
  use small data snapshots
  keep logs and generated files for surprising results
  put model construction in importable modules, not only notebook cells
  record run_id in notebook output

Do not:
  build production-only logic inside notebook cells
  rely on notebook kernel activation for deployment
  silently overwrite runs/
```

---

## 17.5 CLI scripts

### 17.5.1 Use case

```text id="77j9nj"
CLI scripts:
  reproducible local runs
  scheduled jobs
  CI smoke tests
  batch scenario execution
  Docker entrypoints
  HPC job payloads
```

### 17.5.2 Minimal CLI

```python id="jx5f0u"
# src/myopt/cli.py
from __future__ import annotations

import argparse
import json
from pathlib import Path

from pyomo.environ import SolverFactory
from pyomo.opt import SolverStatus, TerminationCondition

from myopt.envcheck import require_scip
from myopt.pyomo_models.production_model import build_model
from myopt.artifacts import make_run_dir, write_options_manifest, write_result_summary


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--config", required=True)
    p.add_argument("--run-id", default=None)
    p.add_argument("--time-limit", type=float, default=300)
    p.add_argument("--gap", type=float, default=1e-4)
    p.add_argument("--debug", action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    env = require_scip()

    config = json.loads(Path(args.config).read_text())
    run_dir = make_run_dir(args.run_id)

    (run_dir / "inputs" / "config.json").write_text(json.dumps(config, indent=2))
    (run_dir / "env" / "runtime-fingerprint.json").write_text(json.dumps(env, indent=2))

    model = build_model(config)

    opt = SolverFactory("scip", solver_io="nl")
    opt.options["limits/time"] = args.time_limit
    opt.options["limits/gap"] = args.gap
    opt.options["display/verblevel"] = 4
    opt.options["display/relevantstats"] = "TRUE"

    res = opt.solve(
        model,
        tee=True,
        logfile=str(run_dir / "solver" / "scip.log"),
        keepfiles=args.debug,
        symbolic_solver_labels=args.debug,
        load_solutions=False,
    )

    write_options_manifest(opt, run_dir / "solver" / "scip-options.json")
    write_result_summary(res, run_dir / "solver" / "solver-summary.json")

    tc = res.solver.termination_condition
    status = res.solver.status

    if status == SolverStatus.ok and tc == TerminationCondition.optimal:
        model.solutions.load_from(res)
        return 0

    if len(res.solution) > 0 and tc in {
        TerminationCondition.maxTimeLimit,
        TerminationCondition.feasible,
    }:
        model.solutions.load_from(res)
        return 2

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
```

### 17.5.3 CLI invocation

```bash id="80t1l7"
micromamba run -n opt-scip python -m myopt.cli \
  --config data/scenarios/scenario_001.json \
  --run-id scenario_001__baseline \
  --time-limit 600 \
  --gap 0.0001 \
  --debug
```

### 17.5.4 Exit-code policy

```text id="aekbpn"
0:
  proven optimal

2:
  feasible incumbent accepted, not proven optimal

1:
  infeasible, unbounded, no solution, unknown, solver failure

130:
  user interrupt, if explicitly mapped
```

---

## 17.6 Batch / HPC jobs

### 17.6.1 Use case

```text id="joz7x4"
Batch/HPC:
  many scenarios
  long solve times
  resource quotas
  noninteractive execution
  log-first debugging
  per-job isolated run artifacts
```

Pyomo’s solver recipes state that building and solving multiple Pyomo models in parallel is common and recommend `mpi4py` for parallel execution patterns. ([Pyomo Documentation][4])

### 17.6.2 Slurm-style script

```bash id="dh5fj4"
#!/usr/bin/env bash
#SBATCH --job-name=scip_scenario
#SBATCH --output=runs/slurm-%j.out
#SBATCH --error=runs/slurm-%j.err
#SBATCH --time=04:00:00
#SBATCH --mem=32G
#SBATCH --cpus-per-task=1

set -euo pipefail

SCENARIO="${1:?scenario JSON required}"
RUN_ID="$(basename "$SCENARIO" .json)__${SLURM_JOB_ID:-manual}"

micromamba run -n opt-scip python -m myopt.cli \
  --config "$SCENARIO" \
  --run-id "$RUN_ID" \
  --time-limit 14000 \
  --gap 0.0001
```

### 17.6.3 Array-job pattern

```bash id="gx1ab5"
#!/usr/bin/env bash
#SBATCH --array=0-99
#SBATCH --time=02:00:00
#SBATCH --mem=16G
#SBATCH --cpus-per-task=1

set -euo pipefail

SCENARIO="$(sed -n "$((SLURM_ARRAY_TASK_ID + 1))p" data/scenario_manifest.txt)"
RUN_ID="scenario_${SLURM_ARRAY_TASK_ID}_${SLURM_JOB_ID}"

micromamba run -n opt-scip python -m myopt.cli \
  --config "$SCENARIO" \
  --run-id "$RUN_ID" \
  --time-limit 7000
```

### 17.6.4 MPI scenario execution sketch

```python id="xvy8f5"
from mpi4py import MPI
from pathlib import Path
import json
import subprocess

comm = MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()

scenarios = [line.strip() for line in Path("data/scenario_manifest.txt").read_text().splitlines()]
my_scenarios = scenarios[rank::size]

for scenario in my_scenarios:
    run_id = f"{Path(scenario).stem}__rank{rank}"
    subprocess.run(
        [
            "python", "-m", "myopt.cli",
            "--config", scenario,
            "--run-id", run_id,
        ],
        check=True,
    )
```

### 17.6.5 HPC guardrails

```text id="j1b1z8"
Do:
  set SCIP memory limit below scheduler memory cap
  set SCIP time limit below job walltime
  use one run directory per scenario
  keep stdout/stderr and scip.log
  avoid shared mutable files across array jobs
  use local scratch for large temporary files when available

Do not:
  write all jobs to the same runs/latest/
  rely on interactive activation
  let many jobs share one logfile
  assume thread count > 1 improves total cluster throughput
```

---

## 17.7 Containers

### 17.7.1 Dockerfile with micromamba

```dockerfile id="mzi8q3"
FROM mambaorg/micromamba:2.6.0

COPY --chown=$MAMBA_USER:$MAMBA_USER env/environment.yml /tmp/environment.yml

RUN micromamba install --yes --file /tmp/environment.yml && \
    micromamba clean --all --yes

ARG MAMBA_DOCKERFILE_ACTIVATE=1
RUN python -m pip check || true

COPY --chown=$MAMBA_USER:$MAMBA_USER src/ /app/src/
COPY --chown=$MAMBA_USER:$MAMBA_USER pyproject.toml /app/pyproject.toml

WORKDIR /app
ENV PYTHONPATH=/app/src

CMD ["python", "-m", "myopt.envcheck"]
```

Micromamba-docker docs state that the conda environment is automatically activated for `docker run`, but not automatically during `docker build`; for Dockerfile `RUN` commands inside the conda environment, set `ARG MAMBA_DOCKERFILE_ACTIVATE=1` and use shell-form `RUN`, and keep `_entrypoint.sh` in the entrypoint chain for runtime activation. ([micromamba-docker.readthedocs.io][5])

### 17.7.2 Container run

```bash id="8atza5"
docker build -t myopt-scip:latest .

docker run --rm \
  -v "$PWD/data:/app/data:ro" \
  -v "$PWD/runs:/app/runs" \
  myopt-scip:latest \
  python -m myopt.cli \
    --config data/scenarios/scenario_001.json \
    --run-id container_scenario_001
```

### 17.7.3 Container guardrails

```text id="ip19f4"
Do:
  use read-only bind mount for input data
  write runs/ to a mounted volume
  set limits/memory in SCIP below container memory cap
  log runtime fingerprint
  pin image digest for regulated workflows

Do not:
  build solver env at container startup
  overwrite ENTRYPOINT without preserving micromamba activation
  depend on host-installed scip
```

### 17.7.4 `environment.yml` inside image

```yaml id="wtskiu"
name: base
channels:
  - conda-forge
channel_priority: strict
dependencies:
  - python=3.11
  - pyomo
  - scip=10.0.2
  - pandas
  - pyyaml
```

For the `mambaorg/micromamba` image, the default activated environment is commonly `base`; using `name: base` in the image environment file avoids accidental creation of an unused second environment unless multi-env behavior is intentional.

---

## 17.8 Streamlit / web app deployment

### 17.8.1 Use case

```text id="97k49u"
Streamlit/web app:
  user supplies scenario data
  app validates inputs
  app launches solve job
  app shows run status
  app renders artifacts/results
```

Streamlit docs distinguish `st.cache_data`, which is suited for serializable data and returns copies, from `st.cache_resource`, which is for global resources shared across reruns/sessions and must be thread-safe because mutations affect the cached object globally. ([Streamlit Docs][6])

### 17.8.2 Web deployment rule

```text id="gl053r"
Do not run long SCIP solves directly as mutable global UI state.

Preferred:
  Streamlit process:
    validate input
    create run_id
    submit job
    poll run status
    render artifacts

  Worker process:
    executes Pyomo+SCIP solve
    writes runs/run_id/*
    never mutates shared Streamlit cached objects
```

### 17.8.3 Simple local Streamlit pattern: subprocess job

```python id="owp1vn"
# app.py
from __future__ import annotations

import json
import subprocess
import uuid
from pathlib import Path

import streamlit as st

RUNS = Path("runs")
RUNS.mkdir(exist_ok=True)

st.title("SCIP optimization runner")

uploaded = st.file_uploader("Scenario JSON", type=["json"])

if uploaded:
    scenario = json.loads(uploaded.read())
    run_id = st.text_input("Run ID", value=f"web_{uuid.uuid4().hex[:12]}")

    scenario_path = RUNS / run_id / "inputs" / "scenario.json"
    scenario_path.parent.mkdir(parents=True, exist_ok=True)
    scenario_path.write_text(json.dumps(scenario, indent=2))

    if st.button("Submit solve"):
        subprocess.Popen(
            [
                "python", "-m", "myopt.cli",
                "--config", str(scenario_path),
                "--run-id", run_id,
                "--time-limit", "600",
            ],
            stdout=(RUNS / run_id / "web-submit.out").open("w"),
            stderr=(RUNS / run_id / "web-submit.err").open("w"),
        )
        st.success(f"Submitted {run_id}")

    summary_path = RUNS / run_id / "solver" / "solver-summary.json"
    log_path = RUNS / run_id / "solver" / "scip.log"

    if summary_path.exists():
        st.json(json.loads(summary_path.read_text()))

    if log_path.exists():
        st.text_area("SCIP log tail", "\n".join(log_path.read_text(errors="replace").splitlines()[-100:]), height=300)
```

### 17.8.4 Web production pattern

```text id="ow449g"
For real production:
  use queue/worker:
    Redis Queue
    Celery
    cloud batch jobs
    Kubernetes Job
    Slurm submitter
  store run status:
    pending
    running
    optimal
    feasible_limit
    infeasible
    failed
  store immutable artifacts under run_id
  enforce input size limits
  enforce time/memory limits
  isolate user runs
```

### 17.8.5 Streamlit caching rules

```python id="ngprlh"
import streamlit as st
import json
from pathlib import Path

@st.cache_data
def load_completed_summary(path: str):
    return json.loads(Path(path).read_text())

# Use cache_resource only for thread-safe resources such as a DB connection,
# not for a mutable Pyomo model that user sessions will mutate.
```

---

## 17.9 CI validation

### 17.9.1 CI goals

```text id="itaywx"
CI should validate:
  environment can import Pyomo
  SCIP executable is available to Pyomo
  tiny MILP solves
  model builders instantiate
  expected objective on small golden case
  result classification works
  debug artifact generation works
```

### 17.9.2 Minimal pytest: solver availability

```python id="amg58i"
# tests/test_solver_available.py
from pyomo.environ import SolverFactory

def test_scip_available():
    opt = SolverFactory("scip", solver_io="nl")
    assert opt.available(False)
    assert opt.executable() is not None
```

### 17.9.3 Minimal pytest: smoke solve

```python id="fxhqnz"
# tests/test_smoke_milp.py
from pyomo.environ import *
from pyomo.opt import SolverStatus, TerminationCondition

def test_scip_smoke_milp():
    m = ConcreteModel()
    m.x = Var(domain=Binary)
    m.y = Var(bounds=(0, None))
    m.obj = Objective(expr=5*m.x + m.y, sense=maximize)
    m.c = Constraint(expr=3*m.x + m.y <= 4)

    opt = SolverFactory("scip", solver_io="nl")
    opt.options["limits/time"] = 30

    res = opt.solve(m, tee=False, load_solutions=False)

    assert res.solver.status == SolverStatus.ok
    assert res.solver.termination_condition == TerminationCondition.optimal

    m.solutions.load_from(res)
    assert abs(value(m.obj) - 6.0) <= 1e-7
```

### 17.9.4 CI command

```bash id="gv9btn"
micromamba run -n opt-scip pytest -q
```

Micromamba’s docs explicitly show `micromamba run -p /tmp/env pytest myproject/tests` as a CI/Docker-friendly execution pattern when activation hooks are inconvenient. ([Mamba][2])

### 17.9.5 GitHub Actions sketch

```yaml id="j9pvnf"
name: pyomo-scip-ci

on:
  push:
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install micromamba
        uses: mamba-org/setup-micromamba@v2
        with:
          environment-file: env/environment.yml
          environment-name: opt-scip
          cache-environment: true

      - name: Environment check
        shell: bash -l {0}
        run: |
          micromamba run -n opt-scip python -m myopt.envcheck

      - name: Tests
        shell: bash -l {0}
        run: |
          micromamba run -n opt-scip pytest -q
```

---

## 17.10 Run artifact API

### 17.10.1 `src/myopt/artifacts.py`

```python id="ejrpzc"
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any


def make_run_dir(run_id: str | None = None, root: str | Path = "runs") -> Path:
    if run_id is None:
        run_id = dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ")

    run_dir = Path(root) / run_id

    for sub in [
        "inputs",
        "model",
        "solver",
        "results",
        "env",
    ]:
        (run_dir / sub).mkdir(parents=True, exist_ok=True)

    return run_dir


def write_json(data: Any, path: str | Path) -> None:
    Path(path).write_text(json.dumps(data, indent=2, sort_keys=True, default=str))


def write_options_manifest(opt, path: str | Path) -> None:
    write_json(
        {str(k): str(v) for k, v in sorted(opt.options.items()) if k != "solver"},
        path,
    )


def write_scip_set_equivalent(opt, path: str | Path) -> None:
    lines = [
        f"{k} = {v}"
        for k, v in sorted(opt.options.items())
        if k != "solver"
    ]
    Path(path).write_text("\n".join(lines) + "\n")


def solver_summary(results) -> dict[str, Any]:
    solver = results.solver
    problem = results.problem

    return {
        "status": str(getattr(solver, "status", "")),
        "termination_condition": str(getattr(solver, "termination_condition", "")),
        "message": str(getattr(solver, "message", "")),
        "time": getattr(solver, "time", None),
        "gap": getattr(solver, "gap", None),
        "primal_bound": getattr(solver, "primal_bound", None),
        "dual_bound": getattr(solver, "dual_bound", None),
        "problem_lower_bound": getattr(problem, "lower_bound", None),
        "problem_upper_bound": getattr(problem, "upper_bound", None),
        "n_solutions": len(results.solution),
    }


def write_result_summary(results, path: str | Path) -> None:
    write_json(solver_summary(results), path)
```

### 17.10.2 Standard solve artifact call

```python id="dr9zuo"
run_dir = make_run_dir(run_id)

res = opt.solve(
    model,
    tee=True,
    logfile=str(run_dir / "solver" / "scip.log"),
    keepfiles=debug,
    symbolic_solver_labels=debug,
    load_solutions=False,
)

write_options_manifest(opt, run_dir / "solver" / "scip-options.json")
write_scip_set_equivalent(opt, run_dir / "solver" / "scip-from-pyomo-options.set")
write_result_summary(res, run_dir / "solver" / "solver-summary.json")

model.write(
    str(run_dir / "model" / "model.nl"),
    format="nl",
    io_options={"symbolic_solver_labels": True, "file_determinism": 30},
)
```

---

## 17.11 Configuration file pattern

### 17.11.1 Run config schema

```json id="1szzji"
{
  "scenario": "data/scenarios/scenario_001.json",
  "solver": {
    "name": "scip",
    "time_limit": 600,
    "relative_gap": 0.0001,
    "memory_mb": 8192,
    "options": {
      "display/verblevel": 4,
      "display/relevantstats": "TRUE"
    }
  },
  "artifacts": {
    "keepfiles": true,
    "symbolic_solver_labels": true,
    "run_root": "runs"
  }
}
```

### 17.11.2 Config application

```python id="wdayha"
def configure_solver_from_config(config: dict):
    opt = SolverFactory(config["solver"].get("name", "scip"), solver_io="nl")

    solver_cfg = config["solver"]

    if solver_cfg.get("time_limit") is not None:
        opt.options["limits/time"] = solver_cfg["time_limit"]

    if solver_cfg.get("relative_gap") is not None:
        opt.options["limits/gap"] = solver_cfg["relative_gap"]

    if solver_cfg.get("memory_mb") is not None:
        opt.options["limits/memory"] = solver_cfg["memory_mb"]

    for key, value in solver_cfg.get("options", {}).items():
        opt.options[key] = value

    return opt
```

### 17.11.3 Config best practices

```text id="0cox5s"
Do:
  version config schema
  archive exact config in run_id/inputs/
  separate solver options from model data
  validate allowed solver option prefixes
  use absolute or run-relative paths deterministically

Do not:
  mutate production config in place
  let UI-provided options pass unrestricted to SCIP in public apps
  accept arbitrary filesystem paths from untrusted users
```

---

## 17.12 Deployment-specific guidance matrix

| Deployment target | Primary command           | Artifact mode   | Main risk                     | Recommended mitigation                   |
| ----------------- | ------------------------- | --------------- | ----------------------------- | ---------------------------------------- |
| local notebook    | interactive Python        | debug on demand | hidden state/kernel drift     | startup fingerprint, importable modules  |
| CLI script        | `python -m myopt.cli ...` | full per-run    | env/PATH mismatch             | `micromamba run`, startup check          |
| batch/HPC         | scheduler script          | full per-job    | shared files/resource limits  | per-run dirs, limits/time, limits/memory |
| container         | Docker CMD                | mounted runs/   | activation/build mistakes     | micromamba-docker activation rules       |
| Streamlit/web     | job submit + polling      | full per-job    | long solve in UI, concurrency | worker queue, immutable run dirs         |
| CI                | pytest smoke              | logs on failure | solver unavailable            | environment check test                   |

---

## 17.13 Security and multi-user deployment notes

```text id="go0ap5"
For web/multi-user:
  never execute user-supplied Python
  never pass arbitrary SCIP options blindly
  cap input size
  cap time/memory
  isolate run_id directories
  sanitize run_id
  store uploaded data under generated names
  do not expose server filesystem paths in UI
  use worker process permissions with restricted access
```

```python id="yjdaws"
import re
import uuid

SAFE_RUN_ID = re.compile(r"^[A-Za-z0-9_.-]+$")

def sanitize_or_generate_run_id(candidate: str | None) -> str:
    if candidate and SAFE_RUN_ID.match(candidate):
        return candidate
    return f"run_{uuid.uuid4().hex}"
```

---

## 17.14 Failure-mode diagnostics by deployment

| Symptom                           | Deployment    | Likely root cause                       | Fix                                                      |
| --------------------------------- | ------------- | --------------------------------------- | -------------------------------------------------------- |
| `SCIP unavailable`                | all           | wrong env / missing solver              | run `python -m myopt.envcheck`; install `scip`           |
| works in shell, not cron/HPC      | CLI/HPC       | activation not loaded                   | use `micromamba run -n opt-scip ...`                     |
| works locally, not Docker         | container     | env not active in Dockerfile/runtime    | preserve micromamba entrypoint; set activation arg       |
| stale solver version              | all           | global `scip` earlier on PATH           | compare `opt.executable()` and `sys.executable`          |
| no logs after failure             | all           | `logfile` absent / run dir not writable | create run dirs before solve                             |
| multiple jobs overwrite artifacts | HPC/web       | shared run_id                           | generate unique run IDs                                  |
| web app freezes                   | Streamlit     | long solve in UI process                | submit to worker/subprocess/job queue                    |
| CI flaky solve time               | CI            | no time limit / nondeterminism          | small smoke model, `limits/time`, deterministic settings |
| memory killed by OS               | container/HPC | SCIP memory > cgroup/job cap            | set `limits/memory` below external cap                   |
| infeasibility not debuggable      | all           | no `.nl/.row/.col`                      | rerun with debug artifact mode                           |

---

## 17.15 Production startup checklist

```text id="gyxciw"
At application startup:
  1. import Pyomo
  2. create SolverFactory("scip", solver_io="nl")
  3. assert opt.available(False)
  4. record opt.executable()
  5. record opt.version()
  6. run `scip --version`
  7. optionally solve tiny MILP smoke model
  8. fail fast if mismatch or unavailable
```

```python id="46vwqv"
def startup_self_test():
    fp = require_scip()

    m = ConcreteModel()
    m.x = Var(domain=Binary)
    m.obj = Objective(expr=m.x, sense=maximize)

    opt = SolverFactory("scip", solver_io="nl")
    opt.options["limits/time"] = 10
    res = opt.solve(m, tee=False, load_solutions=False)

    if res.solver.termination_condition != TerminationCondition.optimal:
        raise RuntimeError(f"SCIP smoke solve failed: {res.solver.termination_condition}")

    return fp
```

---

## 17.16 Production deployment checklist

```text id="93koxy"
Environment:
  conda-forge only
  strict channel priority
  named/prefix env
  SCIP pinned
  Pyomo pinned or lockfile
  no reliance on system solver

Startup:
  check SolverFactory("scip").available(False)
  check opt.executable()
  check opt.version()
  write runtime fingerprint

Solve:
  set limits/time
  set limits/gap
  set limits/memory when deployed under quota
  logfile per run
  load_solutions=False
  classify result before loading

Artifacts:
  config snapshot
  data snapshot/hash
  scip-options.json
  scip-from-pyomo-options.set
  scip.log
  solver-summary.json
  .nl/.row/.col for debug or hard cases
  results.json

Operations:
  unique run_id
  no shared output filenames
  batch/web jobs isolated
  CI smoke solve
  failure preserves artifacts
```

---

## 17.17 Compact mental model

```text id="0ytnqd"
Local notebook:
  explore and debug; keep env fingerprint when results matter.

CLI:
  canonical production entrypoint; run through micromamba run.

HPC:
  one scenario per run_id; scheduler limits mirrored into SCIP limits.

Container:
  build solver env into image; preserve micromamba activation; mount data/runs.

Streamlit/web:
  UI submits jobs; worker solves; UI polls artifacts; cache data/resources carefully.

CI:
  verify solver availability and tiny solve; do not run huge optimization in CI.

Golden deployment rule:
  Python executable and SCIP executable must come from the same pinned environment,
  and every serious solve must produce a self-contained run directory.
```

[1]: https://anaconda.org/conda-forge/scip "scip - conda-forge | Anaconda.org"
[2]: https://mamba.readthedocs.io/en/latest/user_guide/micromamba.html "Micromamba User Guide — documentation"
[3]: https://pyomo.readthedocs.io/en/latest/api/pyomo.solvers.plugins.solvers.ASL.ASL.html "ASL — Pyomo 6.10.1.dev0 documentation"
[4]: https://pyomo.readthedocs.io/en/latest/howto/solver_recipes.html "Solver Recipes — Pyomo 6.10.1.dev0 documentation"
[5]: https://micromamba-docker.readthedocs.io/en/latest/quick_start.html "Quick Start — micromamba-docker 2.6.0 documentation"
[6]: https://docs.streamlit.io/develop/concepts/architecture/caching "Caching overview - Streamlit Docs"

# 18) Testing and QA for Pyomo + SCIP

Dense technical reference for LLM programming agents. Style aligned with the uploaded advanced-doc pattern. 

---

## 18.0 QA contract

```text
Pyomo+SCIP QA must verify:

  environment:
    Pyomo import works
    SolverFactory("scip") exists
    SCIP executable available
    SCIP executable version captured

  solver functionality:
    tiny MILP solves
    tiny MINLP solves if project uses nonlinear/integer models
    logs and artifacts can be captured

  result semantics:
    expected SolverStatus
    expected TerminationCondition
    expected objective
    expected primal feasibility
    expected integrality
    expected gap/bounds where parsed

  failure semantics:
    infeasible model maps as expected
    unbounded model maps as expected
    missing executable fails fast
    invalid SCIP parameter is detected from log/result

  reproducibility:
    known options manifest
    known log signatures
    deterministic data/model build
    golden result JSON
```

Pyomo’s standard result-handling contract is `results = opt.solve(...)`, then inspect `results.solver.status` and `results.solver.termination_condition`; Pyomo’s documentation shows the canonical `SolverStatus.ok` plus `TerminationCondition.optimal` check and explicitly lists statuses such as `ok`, `warning`, `error`, `aborted`, and termination categories such as `optimal`, `infeasible`, `unbounded`, `maxTimeLimit`, and `maxEvaluations`. ([Pyomo][1])

---

## 18.1 Test stack

### 18.1.1 Recommended test dependencies

```yaml
# env/environment.yml
name: opt-scip-test
channels:
  - conda-forge
channel_priority: strict
dependencies:
  - python=3.11
  - pyomo
  - scip=10.0.2
  - pytest
  - pandas
```

### 18.1.2 CI command

```bash
micromamba run -n opt-scip-test pytest -q
```

### 18.1.3 Test directory layout

```text
tests/
  conftest.py
  test_00_solver_availability.py
  test_01_smoke_milp.py
  test_02_smoke_minlp.py
  test_03_regression_objective.py
  test_04_solution_feasibility.py
  test_05_options.py
  test_06_failure_modes.py
  test_07_artifacts.py
  goldens/
    smoke_milp_solver_summary.json
    infeasible_solver_summary.json
    expected_log_signatures.txt
```

---

## 18.2 Shared pytest fixtures

```python
# tests/conftest.py
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from pyomo.environ import *
from pyomo.opt import SolverFactory


@pytest.fixture(scope="session")
def scip_solver():
    opt = SolverFactory("scip", solver_io="nl")
    if not opt.available(False):
        pytest.skip("SCIP solver executable is not available to Pyomo")
    return opt


@pytest.fixture
def run_dir(tmp_path):
    d = tmp_path / "run"
    (d / "solver").mkdir(parents=True)
    (d / "model").mkdir(parents=True)
    (d / "results").mkdir(parents=True)
    return d


def solver_summary(results):
    solver = results.solver
    problem = results.problem
    return {
        "status": str(getattr(solver, "status", "")),
        "termination_condition": str(getattr(solver, "termination_condition", "")),
        "message": str(getattr(solver, "message", "")),
        "time": getattr(solver, "time", None),
        "gap": getattr(solver, "gap", None),
        "primal_bound": getattr(solver, "primal_bound", None),
        "dual_bound": getattr(solver, "dual_bound", None),
        "problem_lower_bound": getattr(problem, "lower_bound", None),
        "problem_upper_bound": getattr(problem, "upper_bound", None),
        "n_solutions": len(results.solution),
    }


def write_json(data, path):
    Path(path).write_text(json.dumps(data, indent=2, sort_keys=True, default=str))


def read_text(path):
    return Path(path).read_text(errors="replace")


def run_cmd(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
```

Pyomo solver options set directly on `opt.options` persist across solves for that solver object unless deleted; per-call `solve(..., options={...})` options apply only to that solve and temporarily override matching persistent options. Use fresh solver fixtures or clear `opt.options` between tests when isolation matters. ([Pyomo Documentation][2])

---

## 18.3 Smoke test: solver availability

### 18.3.1 Availability test

```python
# tests/test_00_solver_availability.py
from pyomo.environ import SolverFactory


def test_scip_available():
    opt = SolverFactory("scip", solver_io="nl")

    assert opt.available(False)
    assert opt.executable() is not None

    version = opt.version()
    assert version is None or tuple(version) >= (8, 0, 0)
```

### 18.3.2 Shell executable test

```python
def test_scip_executable_runs(scip_solver):
    import subprocess

    exe = scip_solver.executable()
    proc = subprocess.run(
        [exe, "--version"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )

    assert proc.returncode == 0
    assert "SCIP" in proc.stdout or "scip" in proc.stdout.lower()
```

### 18.3.3 Failure meaning

```text
Fail:
  SCIP not installed
  wrong conda env
  stale PATH
  Pyomo process cannot find executable
  solver version resolver failed

Fix:
  micromamba install -c conda-forge scip pyomo
  micromamba run -n opt-scip-test pytest -q
  inspect opt.executable()
```

---

## 18.4 Smoke test: tiny MILP solve

### 18.4.1 Model

```python
# tests/test_01_smoke_milp.py
from pyomo.environ import *
from pyomo.opt import SolverStatus, TerminationCondition


def build_tiny_milp():
    m = ConcreteModel()
    m.x = Var(domain=Binary)
    m.y = Var(bounds=(0, None))
    m.obj = Objective(expr=5 * m.x + m.y, sense=maximize)
    m.cap = Constraint(expr=3 * m.x + m.y <= 4)
    return m


def test_tiny_milp_solve(scip_solver, run_dir):
    m = build_tiny_milp()

    res = scip_solver.solve(
        m,
        tee=False,
        logfile=str(run_dir / "solver" / "scip.log"),
        load_solutions=False,
        options={
            "limits/time": 30,
            "display/verblevel": 0,
        },
    )

    assert res.solver.status == SolverStatus.ok
    assert res.solver.termination_condition == TerminationCondition.optimal

    m.solutions.load_from(res)

    assert abs(value(m.x) - 1.0) <= 1e-8
    assert abs(value(m.y) - 1.0) <= 1e-8
    assert abs(value(m.obj) - 6.0) <= 1e-8
```

### 18.4.2 Contract

```text
Asserts:
  SCIP executable usable
  Pyomo NL writer path usable
  SCIP solves binary + continuous MILP
  result loading works
  objective deterministic
  logfile generated
```

Pyomo’s model documentation states that `solve()` normally loads results into the model, but `load_solutions=False` leaves results in the result object so callers can inspect termination before calling `model.solutions.load_from(results)`. ([Pyomo Documentation][3])

---

## 18.5 Smoke test: tiny MINLP solve, only if needed

### 18.5.1 Model

```python
# tests/test_02_smoke_minlp.py
import pytest
from pyomo.environ import *
from pyomo.opt import TerminationCondition


def build_tiny_minlp():
    m = ConcreteModel()
    m.x = Var(bounds=(0.1, 10), initialize=1.0)
    m.b = Var(domain=Binary)
    m.obj = Objective(expr=(m.x - 2) ** 2 + 3 * m.b)
    m.c = Constraint(expr=log(m.x) + m.b >= 0.5)
    return m


@pytest.mark.minlp
def test_tiny_minlp_solve_if_project_uses_minlp(scip_solver, run_dir):
    m = build_tiny_minlp()

    res = scip_solver.solve(
        m,
        tee=False,
        logfile=str(run_dir / "solver" / "scip-minlp.log"),
        load_solutions=False,
        options={
            "limits/time": 60,
            "display/verblevel": 0,
        },
    )

    assert res.solver.termination_condition in {
        TerminationCondition.optimal,
        TerminationCondition.feasible,
        TerminationCondition.maxTimeLimit,
    }

    if len(res.solution) > 0:
        m.solutions.load_from(res)
        assert value(m.x) >= 0.1 - 1e-7
```

### 18.5.2 Contract

```text
Use this test only if project model class includes:
  nonlinear expressions
  integer/binary variables
  MINLP solve path

Skip in pure MILP projects:
  faster CI
  fewer nonlinear-version sensitivities
```

---

## 18.6 Regression tests: objective value

### 18.6.1 Golden objective test

```python
# tests/test_03_regression_objective.py
from pyomo.environ import *
from pyomo.opt import SolverStatus, TerminationCondition


def assert_optimal(res):
    assert res.solver.status == SolverStatus.ok
    assert res.solver.termination_condition == TerminationCondition.optimal


def test_known_instance_objective(scip_solver, run_dir):
    m = build_known_instance_model()

    res = scip_solver.solve(
        m,
        tee=False,
        logfile=str(run_dir / "solver" / "known-instance.log"),
        load_solutions=False,
        options={
            "limits/time": 120,
            "limits/gap": 1e-8,
            "display/verblevel": 0,
        },
    )

    assert_optimal(res)
    m.solutions.load_from(res)

    assert abs(value(m.obj) - 1234.56789) <= 1e-5
```

### 18.6.2 Objective tolerance policy

```text
MILP integer objective:
  exact integer objective expected
  tolerance 1e-7 to 1e-6 usually acceptable for float representation

Continuous objective:
  choose tolerance from business units and solver gap/tolerances

MINLP:
  allow larger tolerance
  record local/global interpretation
  compare feasibility residuals, not only objective
```

---

## 18.7 Regression tests: termination condition

```python
from pyomo.opt import TerminationCondition, SolverStatus


def test_expected_termination_optimal(scip_solver):
    m = build_known_instance_model()
    res = scip_solver.solve(
        m,
        load_solutions=False,
        options={"limits/time": 120, "limits/gap": 1e-8},
    )

    assert res.solver.status == SolverStatus.ok
    assert res.solver.termination_condition == TerminationCondition.optimal


def test_expected_time_limit_when_time_is_tiny(scip_solver):
    m = build_hard_but_valid_model()

    res = scip_solver.solve(
        m,
        load_solutions=False,
        options={"limits/time": 0.01},
    )

    assert res.solver.termination_condition in {
        TerminationCondition.maxTimeLimit,
        TerminationCondition.optimal,
    }
```

For very small time limits, an easy instance may still solve before the limit; avoid brittle tests that require a time-limit termination unless the test model is deliberately hard and stable across hardware. Pyomo’s documented termination categories include `maxTimeLimit`, `optimal`, `infeasible`, and `unbounded`; use enum membership checks instead of string matching where possible. ([Pyomo][1])

---

## 18.8 Regression tests: solution feasibility

### 18.8.1 Constraint residual checker

```python
from pyomo.environ import Constraint, value


def constraint_violation(c):
    body = value(c.body, exception=False)

    if body is None:
        return None

    viol = 0.0
    if c.has_lb():
        viol = max(viol, value(c.lower) - body)
    if c.has_ub():
        viol = max(viol, body - value(c.upper))
    return max(0.0, viol)


def assert_primal_feasible(model, tol=1e-6):
    violations = []
    for c in model.component_data_objects(Constraint, active=True):
        v = constraint_violation(c)
        if v is not None and v > tol:
            violations.append((c.name, v))

    assert not violations, violations[:20]
```

### 18.8.2 Variable-bound checker

```python
from pyomo.environ import Var


def assert_variable_bounds_feasible(model, tol=1e-6):
    bad = []
    for v in model.component_data_objects(Var, active=True):
        if v.value is None:
            continue
        if v.lb is not None and v.value < v.lb - tol:
            bad.append((v.name, v.value, "below_lb", v.lb))
        if v.ub is not None and v.value > v.ub + tol:
            bad.append((v.name, v.value, "above_ub", v.ub))

    assert not bad, bad[:20]
```

### 18.8.3 Integrality checker

```python
from pyomo.environ import Var


def assert_integrality_feasible(model, tol=1e-6):
    bad = []
    for v in model.component_data_objects(Var, active=True):
        if v.value is None:
            continue
        if v.is_binary() or v.is_integer():
            if abs(v.value - round(v.value)) > tol:
                bad.append((v.name, v.value))

    assert not bad, bad[:20]
```

### 18.8.4 Combined feasibility regression

```python
def test_solution_feasibility_regression(scip_solver):
    m = build_known_instance_model()
    res = scip_solver.solve(m, load_solutions=False, options={"limits/time": 120})

    assert res.solver.termination_condition == TerminationCondition.optimal
    m.solutions.load_from(res)

    assert_variable_bounds_feasible(m)
    assert_integrality_feasible(m)
    assert_primal_feasible(m)
```

---

## 18.9 Regression tests: solver gap

### 18.9.1 Gap extraction

```python
def get_solver_gap(results):
    gap = getattr(results.solver, "gap", None)
    if isinstance(gap, str):
        if gap.lower() == "infinite":
            return float("inf")
        try:
            return float(gap)
        except ValueError:
            return None
    return gap
```

### 18.9.2 Gap test

```python
def test_solver_gap_when_parsed(scip_solver, run_dir):
    m = build_known_instance_model()

    res = scip_solver.solve(
        m,
        logfile=str(run_dir / "solver" / "gap.log"),
        load_solutions=False,
        options={
            "limits/time": 120,
            "limits/gap": 1e-4,
            "display/verblevel": 4,
        },
    )

    gap = get_solver_gap(res)

    if gap is not None:
        assert gap <= 1e-4 * 100 or res.solver.termination_condition == TerminationCondition.optimal
```

Pyomo’s SCIP plugin reads the SCIP log for `Solving Time`, `Gap`, `Primal Bound`, and `Dual Bound` and stores those values on `results.solver` when the log fields are available; tests should use `getattr` because these fields are not guaranteed in every solve path. ([Pyomo Documentation][4])

---

## 18.10 Option tests

### 18.10.1 Verify `limits/time`

```python
from pyomo.opt import TerminationCondition


def test_limits_time_is_transmitted(scip_solver, run_dir):
    m = build_hard_but_valid_model()
    log = run_dir / "solver" / "time-limit.log"

    res = scip_solver.solve(
        m,
        logfile=str(log),
        tee=False,
        load_solutions=False,
        options={
            "limits/time": 0.01,
            "display/verblevel": 4,
        },
    )

    text = log.read_text(errors="replace").lower()

    assert "solver command line" in text or log.exists()
    assert res.solver.termination_condition in {
        TerminationCondition.maxTimeLimit,
        TerminationCondition.optimal,
        TerminationCondition.feasible,
    }
```

SCIP’s current parameter list documents `limits/time` as the maximum runtime parameter, and Pyomo’s SCIP plugin writes solver options into a temporary `scip.set` file as `key = value` lines before launching SCIP. ([SCIP Optimization Library][5])

### 18.10.2 Verify `limits/gap`

```python
def test_limits_gap_is_transmitted(scip_solver, run_dir):
    m = build_known_instance_model()
    log = run_dir / "solver" / "gap-limit.log"

    res = scip_solver.solve(
        m,
        logfile=str(log),
        load_solutions=False,
        options={
            "limits/time": 120,
            "limits/gap": 0.50,
            "display/verblevel": 4,
        },
    )

    assert log.exists()

    msg = str(getattr(res.solver, "message", "")).lower()
    tc = res.solver.termination_condition

    assert tc in {
        TerminationCondition.optimal,
        TerminationCondition.other,
        TerminationCondition.maxTimeLimit,
    } or "gap" in msg
```

### 18.10.3 Verify log capture

```python
def test_logfile_is_written(scip_solver, run_dir):
    m = build_tiny_milp()
    log = run_dir / "solver" / "scip.log"

    res = scip_solver.solve(
        m,
        tee=False,
        logfile=str(log),
        load_solutions=False,
        options={"display/verblevel": 4},
    )

    assert log.exists()
    text = log.read_text(errors="replace")
    assert "SCIP" in text or "Solver command line" in text
```

Pyomo’s SCIP postsolve writes the solver command line and captured solver log to the provided log file for SCIP 8+ paths, then parses log-derived fields when available. ([Pyomo Documentation][4])

### 18.10.4 Verify local `scip.set` warning behavior

```python
import logging


def test_local_scip_set_warning_is_detectable(scip_solver, tmp_path, caplog):
    m = build_tiny_milp()

    local_set = tmp_path / "scip.set"
    local_set.write_text("limits/time = 999\n")

    caplog.set_level(logging.WARNING)

    old = Path.cwd()
    try:
        import os
        os.chdir(tmp_path)
        res = scip_solver.solve(
            m,
            load_solutions=False,
            options={"limits/time": 30},
        )
    finally:
        os.chdir(old)

    messages = "\n".join(r.getMessage() for r in caplog.records)
    assert "scip.set" in messages.lower()
    assert "ignored" in messages.lower()
```

Pyomo’s SCIP plugin explicitly warns if a file named `scip.set` exists in the current working directory while Pyomo is generating a separate options file, because the local file will be ignored. ([Pyomo Documentation][4])

---

## 18.11 Failure tests: infeasible model

### 18.11.1 Infeasible model

```python
# tests/test_06_failure_modes.py
from pyomo.environ import *
from pyomo.opt import SolverStatus, TerminationCondition


def build_infeasible_model():
    m = ConcreteModel()
    m.x = Var(bounds=(0, 1))
    m.c1 = Constraint(expr=m.x >= 2)
    m.obj = Objective(expr=m.x)
    return m


def test_infeasible_model_maps_to_infeasible(scip_solver, run_dir):
    m = build_infeasible_model()

    res = scip_solver.solve(
        m,
        logfile=str(run_dir / "solver" / "infeasible.log"),
        load_solutions=False,
        options={"display/verblevel": 4},
    )

    assert res.solver.termination_condition == TerminationCondition.infeasible
    assert res.solver.status in {SolverStatus.warning, SolverStatus.ok}
    assert len(res.solution) == 0
```

### 18.11.2 QA contract

```text
Asserts:
  result classification handles infeasibility
  pipeline does not load values
  log is preserved for diagnostics
```

---

## 18.12 Failure tests: unbounded model

### 18.12.1 Unbounded model

```python
def build_unbounded_model():
    m = ConcreteModel()
    m.x = Var(bounds=(None, None))
    m.obj = Objective(expr=m.x, sense=maximize)
    return m


def test_unbounded_model_maps_to_unbounded_or_related(scip_solver, run_dir):
    m = build_unbounded_model()

    res = scip_solver.solve(
        m,
        logfile=str(run_dir / "solver" / "unbounded.log"),
        load_solutions=False,
        options={"display/verblevel": 4},
    )

    assert res.solver.termination_condition in {
        TerminationCondition.unbounded,
        TerminationCondition.infeasibleOrUnbounded,
        TerminationCondition.other,
        TerminationCondition.unknown,
    }

    msg = str(getattr(res.solver, "message", "")).lower()
    assert (
        "unbounded" in msg
        or res.solver.termination_condition in {
            TerminationCondition.unbounded,
            TerminationCondition.infeasibleOrUnbounded,
        }
    )
```

### 18.12.2 Why use a set, not one enum

```text
Unbounded status can be version/interface/model dependent.
For QA:
  assert recognized failure class
  assert raw message contains "unbounded" when possible
  preserve log for exact mapping
```

Pyomo’s public termination-condition list includes `unbounded` and `infeasible`, and the SCIP plugin’s postsolve mapping is message-driven, so raw messages should be preserved in golden-failure tests. ([Pyomo][1])

---

## 18.13 Failure tests: missing executable

### 18.13.1 Explicit bad executable

```python
import pytest
from pyomo.environ import SolverFactory


def test_missing_executable_fails_fast():
    opt = SolverFactory("scip", executable="/path/to/definitely_missing_scip")
    assert not opt.available(False)

    with pytest.raises(Exception):
        opt.available(exception_flag=True)
```

### 18.13.2 Startup-check function test

```python
def require_solver_available(opt):
    if not opt.available(False):
        raise RuntimeError("Solver unavailable")
    return opt


def test_require_solver_available_raises_for_missing_executable():
    opt = SolverFactory("scip", executable="/path/to/definitely_missing_scip")

    with pytest.raises(RuntimeError, match="Solver unavailable"):
        require_solver_available(opt)
```

Pyomo solver recipes note that if a solver executable is not on `PATH`, `SolverFactory` accepts an `executable=` keyword for absolute or relative paths; use that explicit path facility to test missing-executable handling deterministically. ([Pyomo Documentation][2])

---

## 18.14 Failure tests: invalid SCIP parameter

### 18.14.1 Invalid parameter test

```python
def test_invalid_scip_parameter_is_caught_by_log_or_failure(scip_solver, run_dir):
    m = build_tiny_milp()
    log = run_dir / "solver" / "invalid-param.log"

    res = scip_solver.solve(
        m,
        tee=False,
        logfile=str(log),
        load_solutions=False,
        options={
            "this/is/not/a/scip/parameter": 123,
            "display/verblevel": 4,
        },
    )

    text = log.read_text(errors="replace").lower()

    assert (
        "unknown parameter" in text
        or "invalid parameter" in text
        or "error" in text
        or res.solver.termination_condition != TerminationCondition.optimal
    )
```

### 18.14.2 Why log-based assertion is required

```text
Pyomo does not schema-validate SCIP options.
Pyomo stringifies option key/value pairs into scip.set.
SCIP validates the parameter at runtime.
Therefore invalid-parameter tests must inspect:
  solver log
  return code / result status
  termination condition
```

Pyomo’s SCIP plugin loops over `self.options`, stringifies keys and values, writes them as `key = value` lines into a temporary `scip.set`, and does not check those keys against the SCIP parameter schema. SCIP’s official parameter page is the authoritative source of valid keys and notes the full parameter list can be generated with `SCIP> set save <file name>`. ([Pyomo Documentation][4])

---

## 18.15 Golden artifacts

### 18.15.1 Golden artifact types

```text
Golden artifacts:
  solver-summary.json
  expected objective value
  expected termination condition
  expected status
  expected solution feasibility residuals
  expected log substrings
  expected option manifest
  expected model-output fields
```

### 18.15.2 Golden summary schema

```json
{
  "status": "ok",
  "termination_condition": "optimal",
  "objective": 6.0,
  "max_constraint_violation": 0.0,
  "max_integrality_violation": 0.0,
  "required_log_signatures": [
    "SCIP Status",
    "Solving Time",
    "Primal Bound",
    "Dual Bound",
    "Gap"
  ]
}
```

### 18.15.3 Golden writer

```python
import json
from pathlib import Path
from pyomo.environ import value


def max_constraint_violation(model):
    vals = []
    for c in model.component_data_objects(Constraint, active=True):
        v = constraint_violation(c)
        if v is not None:
            vals.append(v)
    return max(vals, default=0.0)


def max_integrality_violation(model):
    vals = []
    for v in model.component_data_objects(Var, active=True):
        if v.value is None:
            continue
        if v.is_binary() or v.is_integer():
            vals.append(abs(v.value - round(v.value)))
    return max(vals, default=0.0)


def build_golden_payload(model, results):
    return {
        "status": str(results.solver.status),
        "termination_condition": str(results.solver.termination_condition),
        "objective": value(model.obj),
        "max_constraint_violation": max_constraint_violation(model),
        "max_integrality_violation": max_integrality_violation(model),
    }


def assert_matches_golden(payload, golden_path, *, obj_tol=1e-7, feas_tol=1e-6):
    golden = json.loads(Path(golden_path).read_text())

    assert payload["status"] == golden["status"]
    assert payload["termination_condition"] == golden["termination_condition"]
    assert abs(payload["objective"] - golden["objective"]) <= obj_tol
    assert payload["max_constraint_violation"] <= feas_tol
    assert payload["max_integrality_violation"] <= feas_tol
```

### 18.15.4 Golden log signatures

```python
def assert_log_signatures(log_path, required):
    text = Path(log_path).read_text(errors="replace")
    missing = [sig for sig in required if sig not in text]
    assert not missing, f"Missing log signatures: {missing}"


def test_log_golden_signatures(scip_solver, run_dir):
    m = build_tiny_milp()
    log = run_dir / "solver" / "scip.log"

    res = scip_solver.solve(
        m,
        logfile=str(log),
        load_solutions=False,
        options={"display/verblevel": 4},
    )

    assert_log_signatures(
        log,
        [
            "Solver command line",
            "SCIP Status",
            "Solving Time",
        ],
    )
```

For SCIP 8+ paths, Pyomo writes “Solver command line” plus the captured solver log into the log file, then parses summary labels such as solving time, gap, primal bound, and dual bound when available. ([Pyomo Documentation][4])

---

## 18.16 Expected termination mapping tests

### 18.16.1 Classification helper

```python
from pyomo.opt import TerminationCondition


def classify_result(results):
    tc = results.solver.termination_condition
    msg = str(getattr(results.solver, "message", "") or "").lower()
    nsol = len(results.solution)

    if tc == TerminationCondition.optimal:
        return "optimal"
    if tc == TerminationCondition.infeasible:
        return "infeasible"
    if tc == TerminationCondition.unbounded:
        return "unbounded"
    if "infeasible or unbounded" in msg:
        return "infeasible_or_unbounded"
    if tc == TerminationCondition.maxTimeLimit:
        return "time_limit_with_solution" if nsol else "time_limit_no_solution"
    if tc == TerminationCondition.maxEvaluations:
        return "node_limit_with_solution" if nsol else "node_limit_no_solution"
    if tc == TerminationCondition.other:
        if "gap limit reached" in msg:
            return "gap_limit"
        if "solution limit reached" in msg:
            return "solution_limit"
        if "memory limit reached" in msg:
            return "memory_limit"
        return "other"
    return "unknown"
```

### 18.16.2 Mapping test table

```python
import pytest


@pytest.mark.parametrize(
    "builder,expected",
    [
        (build_tiny_milp, {"optimal"}),
        (build_infeasible_model, {"infeasible"}),
        (build_unbounded_model, {"unbounded", "infeasible_or_unbounded", "unknown", "other"}),
    ],
)
def test_expected_result_classification(scip_solver, builder, expected):
    m = builder()
    res = scip_solver.solve(
        m,
        load_solutions=False,
        options={"limits/time": 60, "display/verblevel": 0},
    )
    assert classify_result(res) in expected
```

Pyomo’s SCIP interface maps SCIP messages into Pyomo termination conditions by inspecting solver-message substrings; this is why a local classification helper should preserve and use `results.solver.message` in addition to enums. ([Pyomo Documentation][4])

---

## 18.17 Artifact tests

### 18.17.1 Verify debug artifacts

```python
def test_debug_artifacts_created(scip_solver, run_dir):
    m = build_tiny_milp()

    log = run_dir / "solver" / "scip.log"

    res = scip_solver.solve(
        m,
        tee=False,
        logfile=str(log),
        keepfiles=True,
        symbolic_solver_labels=True,
        load_solutions=False,
        options={"display/verblevel": 4},
    )

    assert log.exists()
    assert "SCIP" in log.read_text(errors="replace") or "Solver command line" in log.read_text(errors="replace")
```

### 18.17.2 Manual deterministic export test

```python
def test_manual_nl_export_is_created(run_dir):
    m = build_tiny_milp()

    nl = run_dir / "model" / "model.nl"
    m.write(
        str(nl),
        format="nl",
        io_options={
            "symbolic_solver_labels": True,
            "file_determinism": 30,
        },
    )

    assert nl.exists()
    assert nl.stat().st_size > 0
```

Pyomo’s model docs say `keepfiles=True` preserves generated solver files and that `symbolic_solver_labels=True` should usually be specified with it for meaningful names; deterministic manual exports provide stable artifacts for golden comparisons. ([Pyomo Documentation][3])

---

## 18.18 Model-output regression tests

### 18.18.1 Result table schema

```python
def variable_values(model):
    rows = []
    for v in model.component_data_objects(Var, active=True):
        rows.append(
            {
                "name": v.name,
                "value": None if v.value is None else float(v.value),
                "lb": None if v.lb is None else float(v.lb),
                "ub": None if v.ub is None else float(v.ub),
                "binary": bool(v.is_binary()),
                "integer": bool(v.is_integer()),
            }
        )
    return sorted(rows, key=lambda r: r["name"])
```

### 18.18.2 Golden variable-value check

```python
def test_expected_model_outputs(scip_solver):
    m = build_known_instance_model()

    res = scip_solver.solve(m, load_solutions=False, options={"limits/time": 120})
    assert res.solver.termination_condition == TerminationCondition.optimal
    m.solutions.load_from(res)

    values = {row["name"]: row["value"] for row in variable_values(m)}

    assert abs(values["x[1]"] - 1.0) <= 1e-7
    assert abs(values["x[2]"] - 0.0) <= 1e-7
```

---

## 18.19 CI marker strategy

### 18.19.1 Markers

```ini
# pytest.ini
[pytest]
markers =
    scip: tests requiring SCIP executable
    minlp: tests requiring SCIP nonlinear path
    slow: long-running optimization tests
    golden: golden artifact regression tests
```

### 18.19.2 Usage

```python
import pytest

@pytest.mark.scip
def test_scip_available():
    ...

@pytest.mark.minlp
def test_tiny_minlp():
    ...

@pytest.mark.slow
def test_large_regression_instance():
    ...
```

### 18.19.3 CI commands

```bash
# fast PR checks
pytest -q -m "not slow"

# nightly
pytest -q

# only solver smoke
pytest -q -m scip
```

---

## 18.20 Test isolation rules

```text
Use fresh model per test:
  never reuse mutated model unless testing repeated solves

Use fresh solver or clear options:
  opt.options.clear()
  or use solve(..., options={...}) per test

Use tmp_path:
  no shared scip.log
  no shared scip.set
  no shared model.nl

Use load_solutions=False:
  inspect result first
  load manually only when accepted

Use small instances:
  CI tests should complete in seconds
```

Pyomo solver options on a solver object persist across solves, so test isolation requires fresh `SolverFactory(...)` objects, clearing `opt.options`, or using per-solve `options={...}`. ([Pyomo Documentation][2])

---

## 18.21 QA harness: reusable solve assertion

```python
from dataclasses import dataclass
from pyomo.opt import SolverStatus, TerminationCondition


@dataclass(frozen=True)
class SolveContract:
    allowed_termination: set
    require_solution: bool = False
    require_optimal: bool = False
    max_gap: float | None = None


def assert_solve_contract(results, contract: SolveContract):
    tc = results.solver.termination_condition

    assert tc in contract.allowed_termination, {
        "status": str(results.solver.status),
        "termination": str(tc),
        "message": str(getattr(results.solver, "message", "")),
    }

    if contract.require_optimal:
        assert results.solver.status == SolverStatus.ok
        assert tc == TerminationCondition.optimal

    if contract.require_solution:
        assert len(results.solution) > 0

    if contract.max_gap is not None:
        gap = get_solver_gap(results)
        if gap is not None:
            assert gap <= contract.max_gap
```

Usage:

```python
def test_contract_known_instance(scip_solver):
    m = build_known_instance_model()

    res = scip_solver.solve(
        m,
        load_solutions=False,
        options={"limits/time": 120, "limits/gap": 1e-4},
    )

    assert_solve_contract(
        res,
        SolveContract(
            allowed_termination={TerminationCondition.optimal},
            require_solution=True,
            require_optimal=True,
        ),
    )
```

---

## 18.22 QA matrix

| Test class             | Purpose              | Minimal assertion                        |
| ---------------------- | -------------------- | ---------------------------------------- |
| solver availability    | env/PATH correctness | `opt.available(False)`                   |
| executable version     | runtime provenance   | `scip --version` succeeds                |
| tiny MILP              | core solver path     | optimal objective                        |
| tiny MINLP             | nonlinear path       | acceptable termination + feasible values |
| objective regression   | model correctness    | objective within tolerance               |
| termination regression | result semantics     | expected enum                            |
| feasibility regression | primal correctness   | max violation <= tol                     |
| integrality regression | discrete correctness | integer residual <= tol                  |
| gap regression         | proof quality        | parsed gap <= threshold where available  |
| time-limit option      | option transport     | time-limit termination or early optimal  |
| gap-limit option       | option transport     | gap-related stop or optimal              |
| log capture            | diagnostics          | logfile exists + signatures              |
| infeasible model       | failure mapping      | infeasible termination                   |
| unbounded model        | failure mapping      | unbounded/related termination            |
| missing executable     | startup failure      | unavailable / raises                     |
| invalid parameter      | negative option test | log contains error or nonoptimal result  |
| artifacts              | reproducibility      | `.nl`/log/options summary produced       |
| golden outputs         | business correctness | known variables/objective                |

---

## 18.23 Compact mental model

```text
Smoke tests:
  SolverFactory("scip").available(False)
  scip --version
  tiny MILP optimal
  tiny MINLP if project needs MINLP

Regression tests:
  objective value
  termination condition
  feasibility residuals
  integrality residuals
  solver gap/bounds when parsed

Option tests:
  limits/time
  limits/gap
  logfile creation
  local scip.set warning if relevant

Failure tests:
  infeasible
  unbounded
  missing executable
  invalid SCIP parameter

Golden artifacts:
  solver-summary.json
  known log substrings
  expected objective
  expected variable values
  expected termination mapping

Golden rule:
  QA must test both mathematical correctness and deployment plumbing:
    environment -> solver discovery -> option transport -> solve -> result classification -> artifacts.
```

[1]: https://www.pyomo.org/blog/2015/1/8/accessing-solver "Accessing solver status and termination conditions — Pyomo"
[2]: https://pyomo.readthedocs.io/en/latest/howto/solver_recipes.html "Solver Recipes — Pyomo 6.10.1.dev0 documentation"
[3]: https://pyomo.readthedocs.io/en/6.8.0/working_models.html "Working with Pyomo Models — Pyomo 6.8.0 documentation"
[4]: https://pyomo.readthedocs.io/en/6.8.2/_modules/pyomo/solvers/plugins/solvers/SCIPAMPL.html "pyomo.solvers.plugins.solvers.SCIPAMPL — Pyomo 6.8.2 documentation"
[5]: https://www.scipopt.org/doc/html/PARAMETERS.php "SCIP Doxygen Documentation: List of all SCIP parameters"

# 19) Comparative framing — SCIP vs alternative solvers and interfaces

Dense solver-selection reference for LLM programming agents. Style aligned with the uploaded advanced-doc pattern. 

---

## 19.0 Solver-selection mental model

```text id="7wj56y"
Solver choice is a function of:

  model class:
    LP
    MILP / MIP
    QP / MIQP
    QCP / MIQCP
    NLP
    MINLP
    GDP-transformed MILP/MINLP
    pseudo-Boolean / CP-flavored CIP

  requirement:
    open-source deployment
    commercial performance/support
    local vs global nonlinear solve
    exact/certified MILP
    callbacks/plugins
    repeated solves
    solver portability
    native solver control

  interface:
    Pyomo -> portable algebraic modeling
    PySCIPOpt -> SCIP-native Python control
    solver-native APIs -> maximum performance/control
```

SCIP is a CIP/MIP/MINLP solver and branch-cut-and-price framework with plugin categories for branching, cutting-plane separation, propagation, pricing, Benders’ decomposition, constraint handlers, pricers, propagators, separators, heuristics, node selectors, and more; HiGHS targets large-scale sparse LP/MIP/QP; IPOPT targets continuous nonlinear programming; Pyomo is a solver-portable modeling layer; PySCIPOpt is the Python interface to SCIP. ([SCIP Optimization Library][1])

---

## 19.1 Quick routing table

| Model / requirement                | First candidate                           | Alternative candidates                | Avoid / caveat                                   |
| ---------------------------------- | ----------------------------------------- | ------------------------------------- | ------------------------------------------------ |
| pure LP                            | HiGHS                                     | commercial LP solvers, SCIP           | SCIP often overkill                              |
| large sparse LP                    | HiGHS                                     | Gurobi/CPLEX/Xpress                   | MINLP solvers unnecessary                        |
| MILP, open-source                  | HiGHS or SCIP                             | CBC, GLPK for simpler cases           | compare; no single universal winner              |
| hard combinatorial MILP            | SCIP                                      | HiGHS, Gurobi/CPLEX/Xpress            | SCIP stronger framework; commercial often faster |
| MIQP / MIQCP                       | SCIP or commercial solver                 | HiGHS for QP only where supported     | HiGHS is not general nonlinear/QCP solver        |
| continuous smooth NLP              | IPOPT                                     | SCIP only if global/MINLP context     | SCIP overkill for local continuous NLP           |
| MINLP open-source                  | SCIP                                      | Couenne, Bonmin                       | install/model support varies                     |
| nonconvex global MINLP             | SCIP / Couenne                            | commercial global solvers if licensed | IPOPT gives local NLP only                       |
| GDP/logical model in Pyomo         | Pyomo transformations + SCIP/other solver | GDPopt for GDP-specific workflows     | solver sees transformed algebra                  |
| callbacks/plugins/lazy constraints | PySCIPOpt                                 | native C/C++ SCIP                     | Pyomo `SolverFactory("scip")` not enough         |
| solver portability                 | Pyomo                                     | JuMP/AMPL/other modeling layers       | PySCIPOpt is SCIP-specific                       |
| SCIP-native search control         | PySCIPOpt / C/C++                         | standalone SCIP for file workflows    | Pyomo external path is file-based                |

---

## 19.2 SCIP vs HiGHS

### 19.2.1 Capability contrast

```text id="54gfad"
HiGHS:
  LP
  MIP
  QP
  large-scale sparse linear optimization
  open-source
  MIT license
  no third-party dependencies in core documentation

SCIP:
  MILP / MIP
  MINLP
  CIP
  pseudo-Boolean / CP-flavored capabilities through native readers/handlers
  branch-cut-and-price framework
  plugin architecture
  exact MILP mode in SCIP 10 when configured
```

HiGHS is documented as high-performance serial/parallel software for LP, MIP, and QP, while the HiGHS docs describe it as software for large-scale sparse linear optimization and MIT-licensed with no third-party dependencies. SCIP is documented as a pure MIP/MINLP solver and as a framework for branch-cut-and-price with plugin extensibility. ([highs.dev][2])

### 19.2.2 Pyomo syntax

```python id="0b6siw"
from pyomo.environ import SolverFactory

# SCIP
scip = SolverFactory("scip", solver_io="nl")
scip.options["limits/time"] = 300

# HiGHS
highs = SolverFactory("highs")
# or APPSI HiGHS where appropriate in Pyomo versions that expose it
```

### 19.2.3 Decision logic

```text id="xf3a0b"
Use HiGHS first when:
  LP / MILP / convex QP-like workflow
  speed + simplicity matter
  model is linear/sparse
  no MINLP/CIP/plugin features needed
  install footprint should be minimal

Use SCIP first when:
  MINLP
  quadratic constraints with integer logic
  logical/combinatorial structure benefits from CIP machinery
  pseudo-Boolean / CP-like structure
  need advanced presolve/propagation/conflict/cut/heuristic ecosystem
  need open-source solver with native plugin path later
```

### 19.2.4 Practical benchmark rule

```text id="3pn1i5"
For pure MILP:
  benchmark both HiGHS and SCIP.

Metrics:
  time to first feasible
  final primal bound
  final dual bound
  gap
  nodes
  memory
  status/termination consistency
```

---

## 19.3 SCIP vs IPOPT

### 19.3.1 Capability contrast

```text id="wrx22n"
IPOPT:
  continuous NLP
  smooth nonlinear functions
  local solution method
  no integer/discrete variables

SCIP:
  integer variables
  binary logic
  MIP/MINLP/CIP
  global/discrete tree search
  LP/NLP relaxations and branch-and-bound style workflows
```

IPOPT is documented as an open-source package for large-scale nonlinear optimization problems over continuous variables with smooth objective/constraint functions, and the COIN-OR GitHub description states it is designed to find local solutions. SCIP, by contrast, is documented as a CIP/MINLP framework and MIP/MINLP solver. ([coin-or.github.io][3])

### 19.3.2 Pyomo routing

```python id="lglh96"
# Continuous NLP
ipopt = SolverFactory("ipopt")
res = ipopt.solve(model, tee=True)

# MINLP / binary + nonlinear
scip = SolverFactory("scip")
res = scip.solve(model, tee=True)
```

### 19.3.3 Decision logic

```text id="mjcail"
Use IPOPT when:
  all variables continuous
  nonlinear functions smooth
  local optimum acceptable
  fast NLP solve desired
  using IPOPT as NLP relaxation/subproblem solver

Use SCIP when:
  any binary/integer variables are intrinsic
  global/discrete feasibility matters
  logical constraints transformed to MIP/MINLP
  nonconvex mixed-integer structure needs branch-and-bound style search
```

### 19.3.4 Hybrid pattern

```text id="17g1t1"
MINLP diagnostic workflow:
  1. relax integrality
  2. solve continuous NLP with IPOPT
  3. inspect feasibility, domains, scaling
  4. restore integrality
  5. solve MINLP with SCIP
```

---

## 19.4 SCIP vs Couenne / Bonmin

### 19.4.1 Capability contrast

```text id="ohvf8h"
Couenne:
  nonconvex MINLP
  global optimization target
  reformulation-based spatial branch-and-bound
  linearization
  branching
  heuristics
  bound reduction

Bonmin:
  open-source C++ code for general MINLP
  twice continuously differentiable functions
  several algorithms
  described by COIN-OR as experimental

SCIP:
  MIP/MINLP/CIP framework
  branch-cut-and-price
  extensive plugin ecosystem
  actively updated SCIP Optimization Suite
```

Couenne aims at global optima of nonconvex MINLPs using linearization, bound reduction, and branching within branch-and-bound; its user manual describes a reformulation-based spatial branch-and-bound approach. Bonmin is described by COIN-OR as an experimental open-source C++ code for general MINLP with twice continuously differentiable functions. SCIP is documented as a CIP/MINLP/MIP framework and SCIP 10 adds modern capabilities including exact MILP mode, infeasibility explanation tooling, and nonlinear interface improvements. ([COIN-OR][4])

### 19.4.2 Pyomo routing

```python id="57f75l"
# SCIP
res = SolverFactory("scip").solve(model, tee=True)

# Couenne, if installed and model class supported
res = SolverFactory("couenne").solve(model, tee=True)

# Bonmin, if installed and model class supported
res = SolverFactory("bonmin").solve(model, tee=True)
```

### 19.4.3 Decision logic

```text id="02j15t"
Use SCIP when:
  modern conda/micromamba installability matters
  mixed MILP/MINLP/CIP structure
  broad native plugin ecosystem desired
  PySCIPOpt/C native path may be needed later

Use Couenne when:
  nonconvex MINLP global optimization comparison needed
  model fits Couenne’s supported expression classes
  installation is available in target environment

Use Bonmin when:
  convex/general MINLP experiment
  local/algorithmic MINLP comparison useful
  installation available
  experimental status acceptable
```

### 19.4.4 Agent benchmark rule

```text id="yyjyxo"
For MINLP:
  never assume solver dominance.
  benchmark SCIP, Couenne, Bonmin where installed.
  compare:
    termination
    objective
    feasibility
    runtime
    global/local interpretation
    log warnings
    model export compatibility
```

---

## 19.5 SCIP vs commercial solvers: Gurobi / CPLEX / Xpress

### 19.5.1 Capability contrast

```text id="q302m8"
Commercial solvers:
  industrial LP/MIP/QP/QCP/MIQP/MIQCP performance
  mature APIs
  support contracts
  tuning tools
  advanced parallelism
  enterprise deployment features
  license cost / license server constraints

SCIP:
  open-source academic/noncommercial-friendly deployment path
  strong MIP/MINLP/CIP framework
  plugin architecture
  branch-cut-and-price
  exact MILP mode when configured
  PySCIPOpt/native extension path
```

Gurobi documentation states current Gurobi supports models with linear constraints, quadratic constraints, second-order cone constraints, multivariate composite nonlinear function constraints, and continuous/integer variables; IBM CPLEX documentation lists LP, QP, QCP, MIP, MIQP, and MIQCP-style problem classes; FICO Xpress documentation lists LP, MIP, QP, MIQP, QCQP, NLP, MINLP, and CP engines/products. SCIP is documented as open-source/framework-oriented MIP/MINLP/CIP software with branch-cut-and-price and plugins. ([support.gurobi.com][5])

### 19.5.2 Pyomo syntax

```python id="vqoasu"
# SCIP
opt = SolverFactory("scip")
opt.options["limits/time"] = 600

# Gurobi
opt = SolverFactory("gurobi")
opt.options["TimeLimit"] = 600
opt.options["MIPGap"] = 1e-4

# CPLEX
opt = SolverFactory("cplex")
opt.options["timelimit"] = 600
opt.options["mip_tolerances_mipgap"] = 1e-4

# Xpress
opt = SolverFactory("xpress")
# option names depend on Pyomo solver plugin / Xpress interface version
```

### 19.5.3 Decision logic

```text id="l3we6t"
Use commercial solver when:
  production MILP speed is primary
  support contract required
  large industrial model
  commercial license available
  native solver tuning/profiling tools needed
  enterprise deployment/legal review approves

Use SCIP when:
  open-source stack required
  MINLP/CIP flexibility matters
  branch-cut-and-price/plugin architecture matters
  PySCIPOpt/C extension likely
  academic/research transparency matters
  exact rational MILP mode/certification is relevant
```

### 19.5.4 Practical benchmark pattern

```text id="u8bfb7"
Commercial-vs-SCIP benchmark:
  same Pyomo model
  same data
  same stopping rule:
    time limit
    relative gap
    absolute gap where relevant
  same acceptable-solution policy
  collect:
    objective
    primal bound
    dual bound
    gap
    runtime
    nodes
    memory
    log warnings
```

### 19.5.5 Avoid false comparisons

```text id="y5kbe5"
Do not compare:
  SCIP with 1 thread vs commercial solver with many threads
  different gap definitions without normalization
  different big-M/GDP transformations
  solver-specific indicator constraints vs big-M formulation unless intentionally comparing formulations
  local NLP result vs global MINLP result
```

---

## 19.6 Pyomo vs PySCIPOpt

### 19.6.1 Capability contrast

```text id="4ng18e"
Pyomo:
  algebraic modeling
  solver portability
  transformations
  Sets / Params / Blocks / Expressions
  GDP-to-MIP/MINLP transformations
  data/model separation
  external solver integrations

PySCIPOpt:
  direct Python interface to SCIP
  in-process SCIP Model object
  direct parameters
  direct solution access
  native callback/plugin surfaces:
    event handlers
    branching rules
    heuristics
    separators
    lazy constraints via constraint handlers
    cut selectors
    node selectors
```

Pyomo’s documentation describes it as a Python-based open-source package for formulating, solving, and analyzing optimization models, with structured optimization applications and access to commercial/open-source solvers. PySCIPOpt is documented as the Python interface to SCIP, and its tutorial/docs surface covers solver-native objects and plugins/callbacks. ([Pyomo Documentation][6])

### 19.6.2 Syntax contrast

```python id="yanrh1"
# Pyomo
from pyomo.environ import *

m = ConcreteModel()
m.x = Var(domain=Binary)
m.obj = Objective(expr=m.x, sense=maximize)

res = SolverFactory("scip").solve(m, tee=True)
```

```python id="sldrs6"
# PySCIPOpt
from pyscipopt import Model

m = Model("scip-native")
x = m.addVar(vtype="B", name="x")
m.setObjective(x, "maximize")
m.optimize()
print(m.getVal(x))
```

### 19.6.3 Decision logic

```text id="hv7fno"
Stay in Pyomo when:
  model readability matters
  solver comparison matters
  transformations matter
  data/model separation matters
  existing codebase uses Pyomo
  no in-search callback/control needed

Switch to PySCIPOpt when:
  custom branching
  custom separator/cuts
  event handlers
  lazy constraints inside solve
  direct solution pool manipulation
  direct SCIP parameters/meta-settings
  solver-state inspection during search
  SCIP-only production target
```

### 19.6.4 Hybrid pattern

```text id="o6pgs9"
Recommended advanced workflow:
  Pyomo:
    reference formulation
    data validation
    regression tests
    solver comparison

  PySCIPOpt:
    performance-critical native SCIP implementation
    callback/plugin implementation
    direct SCIP instrumentation

  QA:
    compare objective and feasibility on small instances
    preserve deterministic variable names
    validate solution equivalence
```

---

## 19.7 Solver-by-model-class matrix

| Model class       |                            HiGHS |                    IPOPT |                   SCIP |                       Couenne |                         Bonmin |                             Gurobi/CPLEX/Xpress | Pyomo role          |
| ----------------- | -------------------------------: | -----------------------: | ---------------------: | ----------------------------: | -----------------------------: | ----------------------------------------------: | ------------------- |
| LP                |                        excellent |                       no |                   good |                            no |                             no |                                       excellent | model once, compare |
| MILP              |                   good/excellent |                       no |         good/excellent |                            no |               maybe not target |                                       excellent | strong              |
| QP                |                              yes | nonlinear local possible |                    yes |                         maybe |                          maybe |                                       excellent | strong              |
| MIQP              | limited/solver-version dependent |                       no |                    yes |                         maybe |                          maybe |                                       excellent | strong              |
| QCP / MIQCP       |                not general focus |               no integer |                    yes |                         maybe |                          maybe |                                       excellent | strong              |
| continuous NLP    |                               no |          excellent local | possible but not first | possible global for nonconvex |                       possible | Xpress/Gurobi nonlinear features where licensed | strong              |
| MINLP             |                               no |           no integrality |                    yes |   yes global nonconvex target | yes experimental/general MINLP |                        solver/product dependent | strong              |
| CP/CIP-like       |                               no |                       no |        native strength |                            no |                             no |              Xpress has CP/Kalis product family | model/transform     |
| callbacks/plugins |                     no via Pyomo |                 not SCIP |            PySCIPOpt/C |               solver-specific |                solver-specific |                                     native APIs | Pyomo limited       |
| portability       |                        via Pyomo |                via Pyomo |              via Pyomo |                     via Pyomo |                      via Pyomo |                                       via Pyomo | primary value       |

---

## 19.8 Installation/deployment comparison

```text id="njyuem"
Open-source conda path:
  HiGHS:
    simple LP/MIP/QP install path
    good CI portability

  SCIP:
    conda-forge::scip
    broader MINLP/CIP framework
    more complex dependency/license surface

  IPOPT:
    conda-forge install generally available
    continuous NLP only

  Couenne/Bonmin:
    availability/installability may be more fragile
    use when explicitly installed and tested

Commercial:
  Gurobi/CPLEX/Xpress:
    license/token/server setup
    strong performance/support
    extra deployment burden
```

HiGHS documentation emphasizes it is freely available under the MIT license with no third-party dependencies; PySCIPOpt/SCIP note SCIP license changes from 8.0.3 onward, and commercial solver documentation reflects broad enterprise-oriented optimizer feature sets and APIs. ([Ergo Code][7])

---

## 19.9 Agent solver-selection procedure

```text id="2h2w1x"
Procedure:

1. Classify model algebra:
   linear
   quadratic
   general nonlinear
   logical/GDP
   piecewise
   pseudo-Boolean

2. Classify domains:
   continuous only
   integer/binary present

3. Classify solve goal:
   local NLP solution
   global/discrete solution
   proof of optimality
   feasible plan
   native callback/control
   solver portability

4. Route:
   continuous NLP -> IPOPT first
   LP/MILP/QP -> HiGHS baseline + SCIP/commercial comparison
   hard open-source MILP -> SCIP and HiGHS benchmark
   MINLP -> SCIP baseline; compare Couenne/Bonmin if installed
   commercial production MILP/QP/QCP -> Gurobi/CPLEX/Xpress benchmark
   callbacks/plugins/lazy constraints -> PySCIPOpt/native SCIP
   GDP/logical -> Pyomo transformation then solver route

5. Validate:
   same data
   same objective sense
   same transformations
   same bounds
   same tolerances/gap policy
   same time limit
   same result-acceptance policy
```

---

## 19.10 Pyomo implementation: multi-solver benchmark harness

```python id="4d4a8s"
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Callable

from pyomo.environ import SolverFactory, value
from pyomo.opt import TerminationCondition


@dataclass(frozen=True)
class SolverSpec:
    name: str
    solver_io: str | None = None
    options: dict[str, object] | None = None


@dataclass(frozen=True)
class SolverRunResult:
    solver: str
    available: bool
    status: str | None = None
    termination: str | None = None
    objective: float | None = None
    gap: object | None = None
    primal_bound: object | None = None
    dual_bound: object | None = None
    message: str | None = None


def make_solver(spec: SolverSpec):
    if spec.solver_io is None:
        opt = SolverFactory(spec.name)
    else:
        opt = SolverFactory(spec.name, solver_io=spec.solver_io)

    for k, v in (spec.options or {}).items():
        opt.options[k] = v

    return opt


def run_solver_spec(build_model: Callable[[], object], spec: SolverSpec, *, tee=False):
    model = build_model()
    opt = make_solver(spec)

    if not opt.available(False):
        return SolverRunResult(solver=spec.name, available=False)

    res = opt.solve(model, tee=tee, load_solutions=False)

    objective = None
    if len(res.solution) > 0:
        model.solutions.load_from(res)
        active_objs = list(model.component_data_objects(Objective, active=True))
        if active_objs:
            objective = value(active_objs[0])

    return SolverRunResult(
        solver=spec.name,
        available=True,
        status=str(res.solver.status),
        termination=str(res.solver.termination_condition),
        objective=objective,
        gap=getattr(res.solver, "gap", None),
        primal_bound=getattr(res.solver, "primal_bound", None),
        dual_bound=getattr(res.solver, "dual_bound", None),
        message=str(getattr(res.solver, "message", "")),
    )


specs = [
    SolverSpec("highs", options={"time_limit": 300}),
    SolverSpec("scip", solver_io="nl", options={"limits/time": 300, "limits/gap": 1e-4}),
    SolverSpec("gurobi", options={"TimeLimit": 300, "MIPGap": 1e-4}),
    SolverSpec("cplex", options={"timelimit": 300}),
]

results = [run_solver_spec(build_model, spec) for spec in specs]
for r in results:
    print(asdict(r))
```

---

## 19.11 Comparative anti-patterns

```text id="pkfpnw"
Anti-pattern:
  “SCIP is better than HiGHS” without model class and metrics.
Fix:
  benchmark on the actual LP/MILP/QP model.

Anti-pattern:
  “IPOPT solved the MINLP” when integer variables were relaxed.
Fix:
  distinguish NLP relaxation from MINLP.

Anti-pattern:
  “Couenne/Bonmin failed, therefore model is infeasible.”
Fix:
  compare SCIP, inspect export/model class, check solver status.

Anti-pattern:
  “Commercial solver and SCIP produce different results, so one is wrong.”
Fix:
  compare gap, tolerances, transformations, objective sense, M values, feasibility residuals.

Anti-pattern:
  “Use PySCIPOpt for portability.”
Fix:
  PySCIPOpt is SCIP-specific; use Pyomo for portability.

Anti-pattern:
  “Use Pyomo for callbacks.”
Fix:
  Pyomo external SCIP interface has no native SCIP callback/plugin surface.
```

---

## 19.12 Final routing cheat sheet

```text id="sn7vhq"
Need fastest/simple open-source LP/MIP/QP:
  HiGHS

Need open-source MIP/MINLP/CIP and advanced solver framework:
  SCIP

Need continuous smooth NLP local solve:
  IPOPT

Need open-source nonconvex MINLP comparison:
  Couenne

Need open-source general MINLP comparison:
  Bonmin

Need industrial MILP/QP/QCP performance/support:
  Gurobi / CPLEX / Xpress

Need solver-portable algebraic model:
  Pyomo

Need SCIP-native callbacks/plugins/events:
  PySCIPOpt

Need maximum SCIP plugin performance/control:
  native SCIP C/C++
```

---

## 19.13 Compact mental model

```text id="zcic64"
SCIP vs HiGHS:
  HiGHS = LP/MIP/QP speed + simplicity.
  SCIP = broader MIP/MINLP/CIP/plugin framework.

SCIP vs IPOPT:
  IPOPT = continuous local NLP.
  SCIP = integer/discrete/global search for MIP/MINLP/CIP.

SCIP vs Couenne/Bonmin:
  all can be MINLP-relevant.
  Couenne targets global nonconvex MINLP.
  Bonmin is experimental general MINLP.
  SCIP is broader, actively modern SCIP-suite framework.

SCIP vs commercial:
  commercial = industrial performance/support/licensing.
  SCIP = open-source flexibility, MINLP/CIP, plugins, exact MILP option.

Pyomo vs PySCIPOpt:
  Pyomo = portable modeling + transformations.
  PySCIPOpt = SCIP-native control + callbacks/plugins.
```

[1]: https://www.scipopt.org/?utm_source=chatgpt.com "SCIP Optimization Suite"
[2]: https://highs.dev/?utm_source=chatgpt.com "HiGHS - High-performance parallel linear optimization software"
[3]: https://coin-or.github.io/Ipopt/?utm_source=chatgpt.com "Ipopt: Documentation"
[4]: https://www.coin-or.org/Couenne/?utm_source=chatgpt.com "Couenne, a solver for non-convex MINLP problems"
[5]: https://support.gurobi.com/hc/en-us/articles/360013156432-What-types-of-models-can-Gurobi-solve?utm_source=chatgpt.com "What types of models can Gurobi solve?"
[6]: https://pyomo.readthedocs.io/?utm_source=chatgpt.com "Pyomo Documentation 6.10.0 - Read the Docs"
[7]: https://ergo-code.github.io/HiGHS/stable/?utm_source=chatgpt.com "About · HiGHS Documentation"
