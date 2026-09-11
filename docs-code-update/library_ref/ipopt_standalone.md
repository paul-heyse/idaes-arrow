# Ipopt advanced technical doc plan — feature-category catalog

I mirrored the structure of your uploaded Cyclopts “advanced technical doc plan” as the style target. 

## Version anchors and deployment assumptions

As of the current conda-forge metadata I found, `conda-forge::ipopt` is at **Ipopt 3.14.19**, installable with `conda install conda-forge::ipopt`, and published for Linux, macOS, and Windows 64-bit platforms. The package metadata shows dependencies including `ampl-asl`, BLAS/LAPACK, `mumps-seq`, and, on Linux builds, `libspral`, which matters because Ipopt’s available linear solvers and defaults are build-dependent. ([Anaconda][1])

Ipopt is a large-scale nonlinear programming solver for problems of the form “minimize a nonlinear objective subject to variable bounds and general equality/inequality constraints,” and its documentation assumes functions are twice continuously differentiable. Algorithmically, Ipopt implements an interior-point line-search filter method and aims for a **local** solution of the NLP, not a global optimum guarantee. ([COIN-OR][2])

For Pyomo, the documented conda path is:

```bash
conda install -c conda-forge pyomo
conda install -c conda-forge ipopt glpk
```

Pyomo explicitly notes that optimization solvers are not installed automatically with Pyomo, so `ipopt` must be installed separately or otherwise made available on `PATH`. ([Pyomo Documentation][3])

---

# 0) Scope, versioning, and the Ipopt mental model

* What Ipopt is: sparse, large-scale, smooth NLP solver.
* What Ipopt is not: not a MILP solver, not a nonsmooth optimizer, not a global nonlinear optimizer.
* Problem class: continuous nonlinear variables, variable bounds, equality constraints, inequality constraints, nonlinear objective.
* Local optimality and nonconvexity expectations.
* Core algorithm: primal-dual interior point, barrier parameter, filter line search, restoration phase.
* What Pyomo contributes: expression system, automatic derivative generation through NL writer, `.nl` file interface, suffix import/export, result parsing.
* What Ipopt contributes: numerical nonlinear optimization engine.

---

# 1) Installation and environment deployment with conda / micromamba

* Recommended environment creation patterns:

```bash
micromamba create -n nlp -c conda-forge python=3.11 pyomo ipopt
micromamba activate nlp
```

or:

```bash
conda create -n nlp -c conda-forge python=3.11 pyomo ipopt
conda activate nlp
```

* Verifying installation:

```bash
conda list ipopt
which ipopt        # Linux/macOS
where ipopt        # Windows
ipopt -=           # print AMPL-interface option list
python -c "import pyomo.environ as pyo; print(pyo.SolverFactory('ipopt').available())"
```

* Conda package anatomy: executable, shared libraries, headers, `ampl-asl`, BLAS/LAPACK, MUMPS, SPRAL where present.
* Difference between `ipopt` and `cyipopt`: `ipopt` is the solver/library/executable package; `cyipopt` is a Python wrapper around Ipopt and is not required for Pyomo’s standard `SolverFactory("ipopt")` workflow. ([Anaconda][4])
* When conda-forge is enough versus when source builds are required: custom HSL, Pardiso, proprietary linear solvers, MKL-specific tuning, custom compile flags.

---

# 2) Packaging reality: “installed Ipopt” versus “all Ipopt features”

* Build-dependent capabilities: linear solvers, defaults, and option availability.
* How to inspect the actual installed build: `ipopt --print-options`, `ipopt -=`, Pyomo `has_linear_solver(...)`, solver logs.
* Conda-forge’s current practical baseline: MUMPS is broadly present; Linux metadata also shows SPRAL dependency in current builds. ([prefix.dev][5])
* Runtime-loadable solvers: HSL and Pardiso can be loaded from shared libraries in builds that support the loader; Ipopt’s docs describe runtime loading through options such as `hsllib` and `pardisolib`. ([COIN-OR][6])
* Licensing implications: Ipopt EPL license, third-party linear solver licenses, HSL/Pardiso/MKL distinctions.

---

# 3) Core NLP modeling contract

* Mathematical form: objective, constraint vector, lower/upper constraint bounds, lower/upper variable bounds.
* Equality constraints as identical lower and upper bounds.
* Infinite bounds and Ipopt’s `nlp_lower_bound_inf` / `nlp_upper_bound_inf`.
* Smoothness requirements: twice continuously differentiable objective and constraints.
* Convex versus nonconvex behavior.
* Feasibility, local infeasibility, restoration phase, and why infeasible starts can still be accepted.
* Scaling consequences: units, badly scaled constraints, and poorly scaled objectives.

---

# 4) Ipopt algorithmic control surface

* Barrier method concepts: `mu_strategy`, `mu_init`, `mu_oracle`, `mu_min`, adaptive versus monotone barrier updates.
* Line search and filter method controls.
* Restoration phase: when Ipopt enters it, how to interpret restoration iterations, and what options influence it.
* Step calculation: primal/dual steps, second-order correction, penalty updates.
* Termination tests: `tol`, `acceptable_tol`, `dual_inf_tol`, `constr_viol_tol`, `compl_inf_tol`, `max_iter`, `max_wall_time`, `max_cpu_time`.
* Difference between “desired” convergence and “acceptable” convergence. Ipopt’s `tol` requires the scaled NLP error to be below tolerance plus absolute criteria for dual infeasibility, constraint violation, and complementarity; `acceptable_tol` provides a secondary stopping criterion. ([COIN-OR][7])

---

# 5) Ipopt option syntax and option deployment

* Option types: Number, Integer, String.
* Option channels:

  * Pyomo `opt.options["tol"] = 1e-8`
  * Pyomo `solve(..., options={...})`
  * `ipopt.opt` file
  * command-line option strings for direct `.nl` solves
* `ipopt.opt` syntax:

```text
# Turn off NLP scaling
nlp_scaling_method none

# Initial barrier parameter
mu_init 1e-2

# Iteration limit
max_iter 500
```

Ipopt reads `ipopt.opt` line by line as `option_name value`, and the file is a first-class way to provide options. The documentation also notes that option availability/defaults for linear solvers depend on the Ipopt build, so an installed-build option dump should be part of our docs. ([COIN-OR][7])

---

# 6) Pyomo integration front doors

* Classic interface:

```python
import pyomo.environ as pyo

opt = pyo.SolverFactory("ipopt")
opt.options["tol"] = 1e-8
results = opt.solve(model, tee=True)
```

* Explicit executable:

```python
opt = pyo.SolverFactory("ipopt", executable="/path/to/ipopt")
```

Pyomo documents `tee=True` for streaming solver output, `options` dictionaries for passing solver options, and `executable=` for specifying a solver path. Options placed on the solver object persist across solves, while options passed to `solve(..., options={...})` are temporary. ([Pyomo Documentation][8])

* Newer Pyomo solver interface: `pyomo.contrib.solver.solvers.ipopt.Ipopt`, documented as an NL-file-based interface with config entries including `tee`, `working_dir`, `load_solutions`, `symbolic_solver_labels`, `time_limit`, `solver_options`, and `executable`. ([Pyomo Documentation][9])
* APPSI Ipopt: useful for repeated solves and model updates; APPSI is designed to be efficient when resolving the same model with small changes. ([Pyomo Documentation][10])

---

# 7) Pyomo model construction patterns for Ipopt

* Variables: bounds, initialization, fixed variables.
* Objectives: single active objective, minimization/maximization transformation.
* Constraints: equality, inequality, ranged constraints.
* Mutable `Param` patterns for repeated solves.
* Expressions and derivative generation.
* Domains: why `NonNegativeReals` is fine but integer/binary variables are not directly solved by Ipopt.
* Model sanity checks:

  * all variables initialized where helpful,
  * no accidental unbounded variables,
  * no inactive objective,
  * no undefined external functions,
  * no nonsmooth operators where smooth derivatives are expected.

---

# 8) Derivatives and Hessian strategy

* Pyomo NL writer derivative behavior.
* Ipopt required derivative information: objective value, gradient, constraint values, Jacobian, Hessian structure/values for direct code interfaces.
* Exact Hessian versus quasi-Newton.
* `hessian_approximation=limited-memory`: when to use it, tradeoffs, and Pyomo syntax.
* Jacobian and gradient approximation options: `jacobian_approximation`, `gradient_approximation`, `findiff_perturbation`.
* Sparse structure and why sparsity quality matters.
* Ipopt’s docs explicitly identify the information needed by direct interfaces: dimensions, bounds, starting point, Jacobian/Hessian sparsity, objective, gradient, constraints, Jacobian, and Hessian. ([COIN-OR][11])

---

# 9) Derivative checker and model debugging

* `derivative_test=first-order`
* `derivative_test=second-order`
* `derivative_test_tol`
* `derivative_test_perturbation`
* `derivative_test_print_all`
* Interpreting derivative checker output: missing sparsity entries, wrong Jacobian values, wrong Hessian entries.
* Best practice: run derivative tests on small instances only.
* Ipopt’s derivative checker uses finite differences at the starting point and can test first- or second-order derivatives before optimization starts. ([COIN-OR][12])

---

# 10) Linear solvers and numerical linear algebra

* Why the linear solver is central to Ipopt performance.
* Conda-forge baseline: MUMPS; Linux current builds also depend on SPRAL.
* Ipopt `linear_solver` option values: `ma27`, `ma57`, `ma77`, `ma86`, `ma97`, `pardiso`, `pardisomkl`, `spral`, `wsmp`, `mumps`, `custom`.
* HSL family: licensing, runtime libraries, `hsllib`.
* Pardiso Project versus MKL Pardiso, `pardisolib`.
* MUMPS options: `mumps_pivtol`, `mumps_pivtolmax`, `mumps_print_level`.
* SPRAL options and GPU-related controls where available.
* BLAS/LAPACK choices and conda BLAS variants.
* Ipopt’s documentation emphasizes that sparse symmetric indefinite linear-system solves dominate performance and that linear solver choice affects speed and robustness. ([COIN-OR][6])

---

# 11) Scaling, initialization, and bound treatment

* NLP scaling:

  * `nlp_scaling_method`
  * `nlp_scaling_max_gradient`
  * when to disable scaling.
* Bound relaxation:

  * `bound_relax_factor`
  * interaction with reported constraint violation.
* Fixed variable treatment:

  * `make_parameter`
  * `make_parameter_nodual`
  * `make_constraint`
  * `relax_bounds`
* Starting values:

  * Pyomo `Var(initialize=...)`
  * setting `.value`
  * heuristics for badly initialized nonlinear models.
* Least-squares initialization:

  * `least_square_init_primal`
  * `least_square_init_duals`

---

# 12) Warm starts in Pyomo + Ipopt

* What Ipopt means by warm start: initial primal and dual variable information from a previous related solve.
* Core options:

  * `warm_start_init_point=yes`
  * `warm_start_bound_push`
  * `warm_start_mult_bound_push`
  * `mu_init`
* Pyomo suffixes:

  * `model.dual`
  * `model.ipopt_zL_out`
  * `model.ipopt_zU_out`
  * `model.ipopt_zL_in`
  * `model.ipopt_zU_in`
* Pyomo suffix directions: `IMPORT`, `EXPORT`, `IMPORT_EXPORT`.
* Warm-start recipe: solve once, import multipliers, copy output bound multiplier suffixes to input suffixes, set warm-start options, solve again.
* Ipopt documents `warm_start_init_point` as the switch for using primal and dual initial values, and Pyomo’s example uses `ipopt_zL_out`, `ipopt_zU_out`, `ipopt_zL_in`, `ipopt_zU_in`, and `dual` suffixes to implement an Ipopt warm start. ([COIN-OR][7])

---

# 13) Solver output, logs, and termination interpretation

* Iteration table columns:

  * `iter`
  * `objective`
  * `inf_pr`
  * `inf_du`
  * `lg(mu)`
  * `||d||`
  * `lg(rg)`
  * `alpha_du`
  * `alpha_pr`
  * `ls`
* Restoration phase markers.
* Step acceptance letters: `f`, `h`, `R`, `w`, `s`, `t`, etc.
* Exit statuses:

  * `Solve_Succeeded`
  * `Solved_To_Acceptable_Level`
  * `Infeasible_Problem_Detected`
  * max iteration / time limits
  * numerical failure
* Pyomo status handling:

  * `results.solver.status`
  * `results.solver.termination_condition`
  * `load_solutions=False`
* Ipopt’s output docs define the iteration columns and explain exit messages such as “Optimal Solution Found,” “Solved To Acceptable Level,” and “Converged to a point of local infeasibility.” ([COIN-OR][13])

---

# 14) Result loading, duals, reduced costs, and suffix data

* Loading primal variable values into Pyomo.
* `load_solutions=False` and manual `model.solutions.load_from(results)`.
* Constraint duals through `model.dual`.
* Bound multipliers through Ipopt-specific suffixes.
* Reduced costs and slacks in APPSI.
* Sign convention documentation.
* Pyomo Suffix mechanics: mapping Pyomo components to solver-side data.
* Compatibility caveat: suffix support depends on solver and solver interface. ([Pyomo Documentation][14])

---

# 15) Common Ipopt option bundles

* “Debug derivatives” bundle:

```python
opt.options.update({
    "derivative_test": "first-order",
    "derivative_test_print_all": "yes",
    "max_iter": 0,
})
```

* “Fast quiet solve” bundle:

```python
opt.options.update({
    "print_level": 0,
    "sb": "yes",
})
```

* “Relaxed convergence” bundle:

```python
opt.options.update({
    "tol": 1e-6,
    "acceptable_tol": 1e-5,
    "max_iter": 1000,
})
```

* “Limited-memory Hessian” bundle:

```python
opt.options.update({
    "hessian_approximation": "limited-memory",
})
```

* “MUMPS tuning” bundle:

```python
opt.options.update({
    "linear_solver": "mumps",
    "mumps_pivtol": 1e-6,
    "mumps_pivtolmax": 0.1,
})
```

---

# 16) Failure modes and troubleshooting

* `No executable found for solver 'ipopt'`
* Solver available in shell but not in notebook/kernel.
* Option typo or option unsupported by installed build.
* `Restoration Failed`
* `Infeasible_Problem_Detected`
* `Maximum_Iterations_Exceeded`
* `Search_Direction_Becomes_Too_Small`
* `Error_In_Step_Computation`
* NaN/Inf in objective or constraints.
* Nonsmooth expressions: `abs`, `max`, `min`, conditionals.
* Bad scaling.
* Missing or poor variable initial values.
* Singular Jacobian or dependent equality constraints.
* Linear solver memory failures.
* Windows path and executable issues.

---

# 17) Best practices for Pyomo + Ipopt model quality

* Initialize variables near feasible, meaningful values.
* Scale objectives and constraints to roughly similar magnitudes.
* Use bounds wherever physically meaningful.
* Avoid nonsmooth functions; reformulate with smooth approximations or complementarity/GDP transformations where appropriate.
* Check degrees of freedom for equality-constrained systems.
* Use `tee=True` and inspect iteration behavior before tuning options.
* Start with defaults, then tune one option family at a time.
* Prefer exact derivatives unless Hessians are too dense or expensive.
* Use `symbolic_solver_labels=True` for debugging, not necessarily production.
* Keep `ipopt.opt` files version-controlled for reproducibility when option sets grow.

---

# 18) Performance engineering

* Sparse expression construction in Pyomo.
* Avoid Python-side loops in repeated objective/constraint construction where possible.
* Reusing model instances versus rebuilding.
* Mutable `Param` for parametric studies.
* APPSI repeated-solve workflows.
* Temporary file locations and working directories.
* Solver log timing:

  * `print_timing_statistics`
  * `timing_statistics`
* BLAS threading and conda BLAS variant control.
* Parallel scenario solving with multiprocessing or MPI.
* Linear solver selection as the first serious performance lever.

---

# 19) Advanced Pyomo workflows

* Parametric sweeps.
* Sequential solves.
* Homotopy / continuation.
* Feasibility restoration workflows.
* Manual warm starts.
* Bound tightening loops.
* NLP subproblems inside decomposition methods.
* NLP subproblems in GDP/MINLP algorithms.
* DAE discretization + Ipopt.
* External functions and compiled callbacks.
* Hybrid use with `cyipopt` when Pyomo is not the desired interface.

---

# 20) Direct Ipopt interfaces outside Pyomo

* AMPL `.nl` command-line usage.
* C++ TNLP interface.
* C interface.
* Fortran, Java, R interfaces.
* `cyipopt` Python wrapper.
* When direct interfaces beat Pyomo:

  * tight callback control,
  * custom derivative code,
  * avoiding file-based solver calls,
  * embedding in compiled systems.
* Ipopt documents AMPL, C++, C, Fortran, Java, and R interfaces, and notes that direct linking requires more work but can be more efficient for large problems. ([COIN-OR][11])

---

# 21) Reproducibility and environment capture

* Record:

  * `ipopt` version,
  * Pyomo version,
  * conda environment YAML,
  * platform,
  * BLAS variant,
  * linear solver selected,
  * full Ipopt option dump,
  * random seeds in model-generation code, if any.
* Use:

```bash
conda env export --from-history
conda list
ipopt -=
```

* Store solver logs for benchmark cases.
* Capture `results.solver.status`, `termination_condition`, objective, infeasibilities, and solve time.

---

# 22) Testing and QA harness

* Minimal availability test.
* Small known NLP test.
* Infeasible model test.
* Bad derivative / nonsmooth model test.
* Option propagation test.
* Warm-start suffix round-trip test.
* Linear solver availability test.
* Golden log fragments for termination messages.
* Regression test for model scaling and initialization.
* CI matrix:

  * Linux/macOS/Windows if needed,
  * pinned conda environment,
  * latest conda-forge environment as allowed-to-fail.

---

# 23) Documentation artifacts to produce from this map

* `ipopt-installation-conda-micromamba.md`
* `ipopt-pyomo-quickstart.md`
* `ipopt-option-reference-for-pyomo.md`
* `ipopt-linear-solvers-conda-forge.md`
* `ipopt-warm-starts-pyomo-suffixes.md`
* `ipopt-debugging-derivatives-and-infeasibility.md`
* `ipopt-output-interpretation.md`
* `ipopt-best-practices-scaling-initialization.md`
* `ipopt-performance-and-repeated-solves.md`
* `ipopt-troubleshooting-playbook.md`

---

## Recommended first deep dives

I would start with **Section 1: Installation and verification**, **Section 6: Pyomo integration front doors**, **Section 5: option syntax**, and **Section 12: warm starts**, because those give you the deployment foundation and the exact syntax patterns needed for real Pyomo usage.

[1]: https://anaconda.org/conda-forge/ipopt "ipopt - conda-forge | Anaconda.org"
[2]: https://coin-or.github.io/Ipopt/ "Ipopt: Documentation"
[3]: https://pyomo.readthedocs.io/en/latest/getting_started/installation.html "Installation — Pyomo 6.10.1.dev0 documentation"
[4]: https://anaconda.org/conda-forge/cyipopt?utm_source=chatgpt.com "cyipopt - conda-forge"
[5]: https://prefix.dev/channels/conda-forge/packages/ipopt "ipopt - conda-forge"
[6]: https://coin-or.github.io/Ipopt/INSTALL.html "Ipopt: Installing Ipopt"
[7]: https://coin-or.github.io/Ipopt/OPTIONS.html "Ipopt: Ipopt Options"
[8]: https://pyomo.readthedocs.io/en/latest/howto/solver_recipes.html "Solver Recipes — Pyomo 6.10.1.dev0 documentation"
[9]: https://pyomo.readthedocs.io/en/stable/api/pyomo.contrib.solver.solvers.ipopt.Ipopt.html "Ipopt — Pyomo 6.10.0 documentation"
[10]: https://pyomo.readthedocs.io/en/6.7.1/library_reference/appsi/appsi.html "APPSI — Pyomo 6.7.1 documentation"
[11]: https://coin-or.github.io/Ipopt/INTERFACES.html "Ipopt: Interfacing your NLP to Ipopt"
[12]: https://coin-or.github.io/Ipopt/SPECIALS.html "Ipopt: Special Features"
[13]: https://coin-or.github.io/Ipopt/OUTPUT.html "Ipopt: Ipopt Output"
[14]: https://pyomo.readthedocs.io/en/6.6.1/pyomo_modeling_components/Suffixes.html "Suffixes — Pyomo 6.6.1 documentation"

# Ipopt Advanced — Section 0: scope, versioning, mental model

Style target: advanced technical section map / agent-ready reference format. 

## 0.0 Version anchors and installed-build reality

**Canonical package identity**

* **Ipopt** = *Interior Point Optimizer*; open-source COIN-OR solver for large-scale nonlinear optimization.
* Current conda-forge package page lists `ipopt` **3.14.19**, install command `conda install conda-forge::ipopt`, EPL-1.0 license metadata, and platform builds for Linux, macOS, and Windows 64-bit targets. ([Anaconda][1])
* Pyomo does **not** install solvers automatically; Pyomo’s installation docs explicitly recommend installing Pyomo and then installing solvers such as Ipopt separately via conda-forge. ([Pyomo Documentation][2])

```bash
micromamba create -n pyomo-ipopt -c conda-forge python=3.11 pyomo ipopt
micromamba activate pyomo-ipopt

ipopt -=
python - <<'PY'
import pyomo.environ as pyo
opt = pyo.SolverFactory("ipopt")
print("available:", opt.available())
print("version:", opt.version() if hasattr(opt, "version") else None)
PY
```

**Agent rule:** never infer feature availability from “Ipopt” alone. Infer from **installed executable + build configuration + option dump**. Ipopt’s own options reference says linear-solver option availability/defaults depend on the configuration used to build Ipopt and recommends printing available options for the installed build. ([COIN-OR][3])

---

## 0.1 Ipopt in one sentence

**Ipopt solves smooth, continuous, sparse nonlinear programming problems by applying a primal-dual interior-point method with filter line-search globalization, using sparse linear algebra at each iteration, targeting a local KKT point.**

Ipopt’s documentation defines the target NLP as minimizing `f(x)` over continuous variables `x ∈ R^n`, subject to general constraint bounds `gL ≤ g(x) ≤ gU` and variable bounds `xL ≤ x ≤ xU`; objective and constraint functions may be linear/nonlinear and convex/nonconvex, but should be twice continuously differentiable. ([COIN-OR][4])

---

## 0.2 Supported mathematical problem class

### Canonical Ipopt NLP form

```text
minimize      f(x)

subject to    gL <= g(x) <= gU
              xL <= x    <= xU

where         x ∈ R^n
              f: R^n -> R
              g: R^n -> R^m
```

Ipopt natively treats lower/upper bounds on both variables and constraints. Equality constraints are represented by setting the matching lower and upper constraint bounds equal: `gL[i] == gU[i] == target_value`. ([COIN-OR][4])

### Pyomo syntax mapping

```python
import pyomo.environ as pyo

m = pyo.ConcreteModel()

# xL <= x <= xU
m.x = pyo.Var(bounds=(0.0, 10.0), initialize=1.0)
m.y = pyo.Var(bounds=(None, None), initialize=2.0)

# nonlinear objective f(x)
m.obj = pyo.Objective(expr=(m.x - 3.0)**2 + pyo.sin(m.y), sense=pyo.minimize)

# inequality: g(x) <= gU
m.c_ub = pyo.Constraint(expr=m.x**2 + m.y <= 25.0)

# inequality: gL <= g(x)
m.c_lb = pyo.Constraint(expr=m.x + m.y >= 1.0)

# equality: gL == gU
m.c_eq = pyo.Constraint(expr=m.x * m.y == 4.0)

opt = pyo.SolverFactory("ipopt")
results = opt.solve(m, tee=True)
```

**Agent invariant:** every active Pyomo model sent to Ipopt must reduce to a continuous NLP. If the model contains binaries, integers, disjunctions, complementarity, nonsmooth logic, or piecewise operators, either transform/reformulate first or select a different solver class.

---

## 0.3 What Ipopt is

### Capability surface

Ipopt is appropriate for:

* **continuous NLP**
* **large-scale sparse NLP**
* **smooth nonlinear objective**
* **smooth nonlinear constraints**
* **variable bounds**
* **equality constraints**
* **inequality constraints**
* **nonconvex local optimization**
* **models with exploitable sparse Jacobian/Hessian structure**
* **Pyomo-generated `.nl` models**
* **warm-start workflows using primal values and suffix-provided dual/bound multipliers**

### Value case

| Ipopt feature                    |                                                   Practical value | Agent deployment implication                                                                                          |
| -------------------------------- | ----------------------------------------------------------------: | --------------------------------------------------------------------------------------------------------------------- |
| Sparse NLP algorithm             | scales to large algebraic models with sparse derivative structure | preserve sparsity in Pyomo; avoid dense summations/expressions where unnecessary                                      |
| Interior-point method            |                handles large constrained smooth problems robustly | provide bounds, scaling, feasible-ish starts, and differentiable expressions                                          |
| Filter line search               |          globalization without simple penalty-only merit behavior | interpret restoration/filter log markers instead of assuming monotone objective decrease                              |
| Exact derivative consumption     |                 fast local convergence when derivatives are valid | trust Pyomo NL derivative generation for standard expressions; use derivative checker for external/custom expressions |
| `.nl` / AMPL Solver Library path |                      stable bridge from Pyomo to Ipopt executable | conda `ipopt` executable works with `SolverFactory("ipopt")` when on `PATH`                                           |
| Suffix support                   |                 dual import/export, warm starts, scaling suffixes | declare `Suffix` objects explicitly with correct direction                                                            |

---

## 0.4 What Ipopt is not

### Not a MILP / MIP solver

Ipopt does **not** branch on integer variables. The legacy Pyomo Ipopt plugin marks integer capability as false, while linear and quadratic objective/constraint capability flags are present through the NL interface. ([Pyomo Documentation][5])

Bad agent output:

```python
m.z = pyo.Var(domain=pyo.Binary)
pyo.SolverFactory("ipopt").solve(m)   # wrong solver class for binary optimization
```

Correct routing:

```python
# MILP / MIQP / MIP
pyo.SolverFactory("highs")    # or cbc, gurobi, cplex, scip, etc.

# MINLP
pyo.SolverFactory("bonmin")   # local MINLP, if installed
pyo.SolverFactory("couenne")  # global-ish MINLP, if installed/appropriate
```

### Not a nonsmooth optimizer

Avoid or reformulate:

```python
abs(x)
max(a, b)
min(a, b)
if value(x) > 0: ...
floor(x)
ceil(x)
round(x)
```

Smooth substitutes / reformulation patterns:

```python
# abs(x) smooth approximation
eps = 1e-6
smooth_abs = pyo.sqrt(x**2 + eps)

# max(a,b) via epigraph if compatible
m.t = pyo.Var()
m.max_a = pyo.Constraint(expr=m.t >= a)
m.max_b = pyo.Constraint(expr=m.t >= b)
# minimize m.t if objective semantics match
```

### Not a global optimizer

Ipopt targets a **local** solution of the NLP; its documentation explicitly describes the method as aiming to find a local solution. ([COIN-OR][4])

Agent consequence:

```python
# For nonconvex NLP:
for seed in starts:
    set_initial_values(m, seed)
    results = opt.solve(m)
    record(local_solution)
# Compare local solutions; do not claim global optimality from one Ipopt run.
```

---

## 0.5 Local optimality and nonconvexity expectations

### Expected result class

Ipopt returns points satisfying first-order KKT-like convergence criteria when successful. In convex NLPs, a KKT point may be globally optimal under standard convexity/constraint-qualification assumptions. In nonconvex NLPs, a KKT point can be:

* local minimum,
* saddle-like stationary point,
* poor basin solution,
* feasible point with weak local quality,
* locally infeasible point if Ipopt cannot find feasibility.

### Agent-safe language

Use:

```text
Ipopt found a locally optimal / stationary NLP solution, conditional on model smoothness,
derivative correctness, scaling, initialization, and termination status.
```

Do **not** use:

```text
Ipopt proved the global optimum.
```

unless paired with an external global certificate, convexity proof, or global solver.

### Multi-start skeleton

```python
def solve_from_start(model, x0):
    for var, val in x0.items():
        var.set_value(val, skip_validation=True)
    opt = pyo.SolverFactory("ipopt")
    opt.options.update({
        "tol": 1e-8,
        "max_iter": 1000,
    })
    res = opt.solve(model, tee=False, load_solutions=True)
    return res, pyo.value(model.obj)

starts = [...]
solutions = [solve_from_start(m.clone(), s) for s in starts]
best = min(solutions, key=lambda item: item[1])
```

---

## 0.6 Core algorithm mental model

Ipopt implements an **interior point line-search filter method**. ([COIN-OR][4])

### Algorithmic objects agents must recognize

| Object                       | Meaning                                                       | Common option/log surface                                    |
| ---------------------------- | ------------------------------------------------------------- | ------------------------------------------------------------ |
| primal variables `x`         | model decision variables                                      | Pyomo `Var`, initial `.value`, bounds                        |
| slack variables              | internal inequality-bound handling                            | not usually explicit in Pyomo                                |
| dual variables / multipliers | constraint/bound KKT multipliers                              | Pyomo `dual`, `ipopt_zL_*`, `ipopt_zU_*` suffixes            |
| barrier parameter `mu`       | interior-point centrality / complementarity control           | `mu_strategy`, `mu_init`, log column `lg(mu)`                |
| filter                       | globalization mechanism balancing objective and infeasibility | iteration step tags `f`, `h`; nonmonotone objective possible |
| restoration phase            | feasibility-recovery mode                                     | log restoration markers; `Restoration_Failed` exit           |
| sparse KKT linear system     | Newton step core numerical burden                             | `linear_solver`, MUMPS/HSL/Pardiso/SPRAL options             |

### Why objective may increase

Interior-point filter methods are not “objective descent at every iteration” algorithms. Feasibility, barrier terms, and filter acceptance can dominate a local step. Agent log parsers must not flag objective increases as solver failure by themselves.

### Standard iteration columns

Ipopt’s output page defines the default iteration table, including `objective`, `inf_pr`, `inf_du`, `lg(mu)`, step norms, primal/dual step sizes, and line-search count. ([COIN-OR][6])

```text
iter    objective    inf_pr   inf_du lg(mu)  ||d||  lg(rg) alpha_du alpha_pr  ls
```

Agent interpretation baseline:

```text
inf_pr  -> primal infeasibility / constraint violation signal
inf_du  -> dual infeasibility / stationarity signal
lg(mu)  -> log10 barrier parameter
||d||   -> step norm
lg(rg)  -> regularization magnitude, if any
alpha_* -> step sizes
ls      -> line-search trials
```

---

## 0.7 Pyomo responsibility versus Ipopt responsibility

### Pyomo contributes: symbolic modeling layer

Pyomo handles:

* Python algebraic model construction.
* Component graph: `ConcreteModel`, `Var`, `Param`, `Expression`, `Objective`, `Constraint`, `Suffix`.
* Expression trees for nonlinear expressions.
* File generation for solver interfaces.
* Solver option forwarding.
* Suffix import/export.
* Result object creation and solution loading.

### Ipopt contributes: numerical NLP solve

Ipopt handles:

* NLP iteration sequence.
* Barrier/filter/restoration logic.
* Sparse linear solves.
* KKT system regularization and step computation.
* Convergence tests.
* Local solution production.
* Solver-native log and exit status.

### Boundary contract

```text
Pyomo model
  -> Pyomo expression representation
  -> NL writer / solver interface
  -> .nl file + optional .row/.col + suffix data
  -> ipopt executable
  -> .sol/results
  -> Pyomo result parsing + variable/suffix loading
```

The legacy Pyomo Ipopt plugin is registered as `SolverFactory("ipopt")`, uses the AMPL Solver Library, accepts only NL problem format, and returns SOL-format results for that problem format. ([Pyomo Documentation][5])

---

## 0.8 Pyomo syntax: minimal canonical solve

```python
import pyomo.environ as pyo

m = pyo.ConcreteModel()
m.x = pyo.Var(bounds=(0, None), initialize=1.0)
m.y = pyo.Var(bounds=(0, None), initialize=1.0)

m.obj = pyo.Objective(expr=(m.x - 1)**2 + (m.y - 2)**2)
m.con = pyo.Constraint(expr=m.x * m.y >= 1.0)

opt = pyo.SolverFactory("ipopt")
opt.options["tol"] = 1e-8
opt.options["max_iter"] = 500

res = opt.solve(m, tee=True)

print(res.solver.status)
print(res.solver.termination_condition)
print(pyo.value(m.x), pyo.value(m.y), pyo.value(m.obj))
```

Pyomo’s solver recipe docs show `tee=True` for solver log streaming, `opt.options[...]` for persistent solver-object options, `solve(..., options={...})` for solve-local options, and `executable=` when the solver executable is not on `PATH`. ([Pyomo Documentation][7])

---

## 0.9 Pyomo syntax: deployment-robust solver factory

```python
from pathlib import Path
import pyomo.environ as pyo

def make_ipopt(
    executable: str | Path | None = None,
    *,
    tol: float = 1e-8,
    max_iter: int = 1000,
    print_level: int = 5,
) -> pyo.SolverFactory:
    kwargs = {}
    if executable is not None:
        kwargs["executable"] = str(executable)

    opt = pyo.SolverFactory("ipopt", **kwargs)

    if not opt.available(exception_flag=False):
        raise RuntimeError(
            "Ipopt executable not available. Install with conda-forge/micromamba "
            "or pass executable='/absolute/path/to/ipopt'."
        )

    opt.options.update({
        "tol": tol,
        "max_iter": max_iter,
        "print_level": print_level,
    })
    return opt
```

---

## 0.10 New Pyomo Ipopt interface mental model

Pyomo also documents a newer `pyomo.contrib.solver.solvers.ipopt.Ipopt` class. Its config includes `tee`, `working_dir`, `load_solutions`, `symbolic_solver_labels`, `time_limit`, `solver_options`, `executable`, and `writer_config`; `executable` defaults to searching `PATH` for `ipopt`. ([Pyomo Documentation][8])

```python
from pyomo.contrib.solver.solvers.ipopt import Ipopt

solver = Ipopt()
res = solver.solve(
    m,
    tee=True,
    solver_options={
        "tol": 1e-8,
        "max_iter": 1000,
    },
    symbolic_solver_labels=True,
)
```

Writer-level controls matter for debugging and reproducibility. The Ipopt interface documentation exposes NL-writer controls such as deterministic file writing, symbolic labels, scaling via `scaling_factor` suffix, row/column ordering, exported nonlinear variables, defined-variable export, and linear presolve. ([Pyomo Documentation][9])

---

## 0.11 Suffix mental model: Pyomo ↔ Ipopt metadata channel

Pyomo `Suffix` objects carry extra solver/model metadata. Pyomo documents suffix directions as `LOCAL`, `IMPORT`, `EXPORT`, and `IMPORT_EXPORT`, with common uses including importing solver solution data such as duals/reduced costs and exporting warm-start or algorithmic information. ([Pyomo Documentation][10])

### Dual import

```python
m.dual = pyo.Suffix(direction=pyo.Suffix.IMPORT)

res = opt.solve(m)

print(m.dual[m.con])  # constraint multiplier, if solver/interface returns it
```

### Ipopt warm-start suffix skeleton

```python
m.dual = pyo.Suffix(direction=pyo.Suffix.IMPORT_EXPORT)

# Bound multipliers from Ipopt
m.ipopt_zL_out = pyo.Suffix(direction=pyo.Suffix.IMPORT)
m.ipopt_zU_out = pyo.Suffix(direction=pyo.Suffix.IMPORT)

# Bound multipliers sent back to Ipopt
m.ipopt_zL_in = pyo.Suffix(direction=pyo.Suffix.EXPORT)
m.ipopt_zU_in = pyo.Suffix(direction=pyo.Suffix.EXPORT)
```

Pyomo’s suffix docs specifically identify `dual` as special for constraint multiplier initialization through the NL interface and show Ipopt warm-start suffix names `ipopt_zL_out`, `ipopt_zU_out`, `ipopt_zL_in`, `ipopt_zU_in`, plus `dual`. ([Pyomo Documentation][10])

---

## 0.12 Scope classifier for LLM agents

### Choose Ipopt when

```text
continuous variables only
AND smooth objective/constraints
AND derivatives available through Pyomo or callbacks
AND local optimum acceptable
AND sparse NLP structure exists or model is medium-scale
AND no discrete combinatorial search required
```

### Do not choose Ipopt when

```text
binary/integer variables are essential
OR global optimality certificate required for nonconvex model
OR nonsmooth black-box objective
OR simulation-only objective without derivatives
OR discontinuous if/else logic
OR stochastic/noisy objective evaluations
OR constraint functions undefined near iterates
```

### Reformulate before Ipopt when

```text
piecewise-linear expression -> smooth approximation or MILP/GDP reformulation
absolute value -> smooth approximation or epigraph with compatible objective
max/min -> epigraph/hypograph if convex-compatible
indicator logic -> GDP/MIP transformation or smooth relaxation
complementarity -> MPEC transformation or regularization
integer design -> fix integers, decompose, or switch to MINLP solver
```

---

## 0.13 Best-practice deployment advisory

### Environment

```bash
micromamba create -n opt -c conda-forge python=3.11 pyomo ipopt
micromamba activate opt
```

Pin for reproducibility:

```yaml
channels:
  - conda-forge
dependencies:
  - python=3.11
  - pyomo
  - ipopt=3.14.19
```

### Verification commands

```bash
ipopt -= | head -100
python - <<'PY'
import pyomo.environ as pyo
opt = pyo.SolverFactory("ipopt")
print(opt.available())
print(opt.version())
PY
```

### Runtime checks in generated code

```python
opt = pyo.SolverFactory("ipopt")
if not opt.available(exception_flag=False):
    raise RuntimeError("Ipopt not available: install conda-forge::ipopt or pass executable=...")
```

### Debug-first options

```python
opt.options.update({
    "print_level": 5,
    "tol": 1e-8,
    "max_iter": 1000,
})
```

### Production log-light options

```python
opt.options.update({
    "print_level": 0,
    "sb": "yes",
})
```

### Agent default: avoid hiding logs until model is validated

Use:

```python
opt.solve(m, tee=True)
```

during model bring-up. Suppress logs only after convergence behavior, scaling, and termination conditions are known.

---

## 0.14 Mental-model checksum

An LLM agent should be able to derive these statements mechanically:

```text
Pyomo is not the nonlinear optimizer.
Ipopt is not the algebraic modeling language.
Pyomo builds an algebraic NLP and serializes it through a solver interface.
Ipopt numerically solves the continuous smooth NLP.
Ipopt returns local NLP solutions, not global certificates.
Conda installs an Ipopt executable/build; feature availability is build-specific.
Ipopt requires smooth functions; nonsmooth/discrete constructs require reformulation or different solvers.
Suffixes are the Pyomo-side metadata channel for duals, bound multipliers, scaling, and warm starts.
Solver options are passed either through opt.options, solve(options={...}), or ipopt.opt / executable-level mechanisms.
```

[1]: https://anaconda.org/conda-forge/ipopt "ipopt - conda-forge | Anaconda.org"
[2]: https://pyomo.readthedocs.io/en/latest/getting_started/installation.html "Installation — Pyomo 6.10.1.dev0 documentation"
[3]: https://coin-or.github.io/Ipopt/OPTIONS.html "Ipopt: Ipopt Options"
[4]: https://coin-or.github.io/Ipopt/ "Ipopt: Documentation"
[5]: https://pyomo.readthedocs.io/en/6.9.3/_modules/pyomo/solvers/plugins/solvers/IPOPT.html "pyomo.solvers.plugins.solvers.IPOPT — Pyomo 6.9.3 documentation"
[6]: https://coin-or.github.io/Ipopt/OUTPUT.html "Ipopt: Ipopt Output"
[7]: https://pyomo.readthedocs.io/en/latest/howto/solver_recipes.html "Solver Recipes — Pyomo 6.10.1.dev0 documentation"
[8]: https://pyomo.readthedocs.io/en/stable/api/pyomo.contrib.solver.solvers.ipopt.Ipopt.html "Ipopt — Pyomo 6.10.0 documentation"
[9]: https://pyomo.readthedocs.io/en/6.8.1/api/pyomo.contrib.solver.ipopt.Ipopt.html "Ipopt — Pyomo 6.8.1 documentation"
[10]: https://pyomo.readthedocs.io/en/6.8.0/pyomo_modeling_components/Suffixes.html "Suffixes — Pyomo 6.8.0 documentation"

# Ipopt Advanced — Section 1: installation and environment deployment with conda / micromamba

Style target: dense advanced technical catalog. 

## 1.0 Deployment invariant

**Target stack**

```text
Pyomo model code
→ Pyomo NL writer / AMPL Solver Library interface
→ ipopt executable from active conda/micromamba env
→ Ipopt shared libraries + sparse linear solver dependencies
→ .sol/result parse back into Pyomo
```

**Agent rule:** for standard Pyomo usage, install **`pyomo` + `ipopt`** in the same active conda-compatible environment. Do **not** install `cyipopt` unless direct Python callback access to Ipopt is required. Pyomo docs state that solvers are not installed with Pyomo and show installing `ipopt` separately via conda-forge; conda-forge currently publishes `ipopt` 3.14.19 for Linux, macOS, and Windows 64-bit platforms. ([Pyomo Documentation][1])

---

## 1.1 Recommended environment creation: micromamba

### Named environment

```bash
micromamba create -n nlp -c conda-forge python=3.11 pyomo ipopt
micromamba activate nlp
```

### Explicit prefix environment: CI / Docker / HPC-safe

```bash
micromamba create -p "$PWD/.envs/nlp" -c conda-forge python=3.11 pyomo ipopt
micromamba activate "$PWD/.envs/nlp"
```

### No shell activation: CI-safe execution

```bash
micromamba run -n nlp python solve.py
micromamba run -n nlp ipopt -=
```

Micromamba is a small statically linked package manager with a separate CLI, no default Python/base environment, and a `micromamba run` workflow that is useful when shell activation is awkward in CI/Docker contexts. ([Mamba][2])

**Agent preference order**

```text
local interactive dev     -> micromamba create -n nlp ...
CI / Docker / HPC         -> micromamba create -p /explicit/prefix ...
notebook kernel           -> install ipykernel inside same env; register kernel
reproducible deployment   -> environment.yml or explicit lockfile
```

---

## 1.2 Recommended environment creation: conda

### Named environment

```bash
conda create -n nlp -c conda-forge python=3.11 pyomo ipopt
conda activate nlp
```

### Strict conda-forge priority

```bash
conda config --env --set channel_priority strict
conda install -c conda-forge pyomo ipopt
```

### Existing env install

```bash
conda activate nlp
conda install -c conda-forge pyomo ipopt
```

Pyomo’s current installation docs list supported CPython versions and show `conda install -c conda-forge pyomo` plus solver installation using `conda install -c conda-forge ipopt glpk`; the explicit implication is that `pyomo` and solver executables are separate installables. ([Pyomo Documentation][1])

---

## 1.3 Environment YAML: reproducible baseline

```yaml
name: nlp
channels:
  - conda-forge
channel_priority: strict
dependencies:
  - python=3.11
  - pyomo
  - ipopt=3.14.19
```

Create:

```bash
micromamba env create -f environment.yml
# or
conda env create -f environment.yml
```

Update:

```bash
micromamba env update -n nlp -f environment.yml --prune
# or
conda env update -n nlp -f environment.yml --prune
```

Export history-only spec:

```bash
conda env export --from-history > environment.from-history.yml
micromamba env export -n nlp > environment.full.yml
```

**Agent rule:** pin `ipopt` for production reproducibility; leave unpinned only for exploratory notebooks or scheduled “latest stack” CI jobs.

---

## 1.4 Verification matrix: shell, executable, Pyomo, options, linear solvers

### Package installed

```bash
conda list ipopt
conda list pyomo
```

### Executable resolution

Linux/macOS:

```bash
which ipopt
ipopt -v
ipopt -=
```

Windows:

```powershell
where ipopt
ipopt -v
ipopt -=
```

Ipopt’s AMPL executable supports `-=` to print the AMPL-interface option list; `--print-options` / `print_options_documentation` provide option documentation, and Ipopt explicitly warns that availability/defaults for some linear-solver options depend on the installed build. ([COIN-OR][3])

### Pyomo solver availability

```bash
python - <<'PY'
import pyomo.environ as pyo

opt = pyo.SolverFactory("ipopt")
print("available:", opt.available(exception_flag=False))
print("version:", opt.version() if hasattr(opt, "version") else None)
print("executable:", opt.executable() if hasattr(opt, "executable") else None)
PY
```

### Minimal NLP smoke test

```bash
python - <<'PY'
import pyomo.environ as pyo

m = pyo.ConcreteModel()
m.x = pyo.Var(bounds=(0, None), initialize=2.0)
m.obj = pyo.Objective(expr=(m.x - 1.0)**2)

opt = pyo.SolverFactory("ipopt")
assert opt.available(exception_flag=False), "Ipopt unavailable to Pyomo"
res = opt.solve(m, tee=False)

print(res.solver.status)
print(res.solver.termination_condition)
print("x =", pyo.value(m.x))
PY
```

### Linear solver probe: legacy Pyomo interface

```bash
python - <<'PY'
import pyomo.environ as pyo

opt = pyo.SolverFactory("ipopt")
for ls in ["mumps", "spral", "ma27", "ma57", "pardiso", "pardisomkl"]:
    try:
        ok = opt.has_linear_solver(ls)
    except Exception as e:
        ok = f"ERROR: {type(e).__name__}: {e}"
    print(f"{ls:12s} {ok}")
PY
```

Pyomo’s legacy Ipopt plugin exposes `has_linear_solver(linear_solver)` by solving a small model with `options={'linear_solver': linear_solver}` and checking whether the solver reports that it is running with that linear solver. ([Pyomo Documentation][4])

### Linear solver probe: newer Pyomo contrib interface

```bash
python - <<'PY'
from pyomo.contrib.solver.solvers.ipopt import Ipopt

solver = Ipopt()
print("available:", bool(solver.available()))
print("version:", solver.version())

for ls in ["mumps", "spral", "ma27", "ma57", "pardiso", "pardisomkl"]:
    try:
        print(f"{ls:12s}", solver.has_linear_solver(ls))
    except Exception as e:
        print(f"{ls:12s}", type(e).__name__, e)
PY
```

The newer Pyomo Ipopt interface is NL-file based, defaults to searching `PATH` for an `ipopt` executable, exposes `available()`, `version()`, and `has_linear_solver()`, and supports config items such as `tee`, `working_dir`, `load_solutions`, `symbolic_solver_labels`, `time_limit`, `solver_options`, and `executable`. ([Pyomo Documentation][5])

---

## 1.5 Conda package anatomy: what `conda-forge::ipopt` installs

### Current conda-forge package identity

```text
package      ipopt
version      3.14.19
license      EPL-1.0
platforms    linux-64, linux-aarch64, linux-ppc64le, osx-64, osx-arm64, win-64
summary      Software package for large-scale nonlinear optimization
```

The conda-forge package page lists `ipopt` 3.14.19, installation via `conda install conda-forge::ipopt`, EPL-1.0 license metadata, and supported 64-bit Linux/macOS/Windows platforms. ([Anaconda][6])

### Variant dependency pattern

Current `prefix.dev` metadata for conda-forge `ipopt` 3.14.19 shows:

```text
common:
  ampl-asl
  libblas
  liblapack
  mumps-seq

linux:
  libgcc
  libstdcxx
  libspral
  __glibc

macOS:
  libcxx
  __osx

windows:
  ucrt
  vc
  vc14_runtime
```

For the current `linux-64` 3.14.19 build, dependencies include `ampl-asl`, `libblas`, `liblapack`, `libspral`, `libstdcxx`, and `mumps-seq`; for Windows and macOS variants, the displayed dependency set includes `ampl-asl`, BLAS/LAPACK, and `mumps-seq`, with platform runtime libraries. ([prefix.dev][7])

### Functional meaning

| Artifact / dependency         | Deployment meaning                                   | Pyomo relevance                                              |
| ----------------------------- | ---------------------------------------------------- | ------------------------------------------------------------ |
| `ipopt` executable            | command-line AMPL/NL solver executable               | `SolverFactory("ipopt")` invokes it                          |
| `libipopt` shared library     | Ipopt compiled solver library                        | used by executable; useful for compiled/direct interfaces    |
| headers / pkg-config metadata | compile-time integration                             | relevant for `cyipopt` or C/C++ builds                       |
| `ampl-asl`                    | AMPL Solver Library / NL interface support           | required for Pyomo NL-file executable workflow               |
| `libblas`, `liblapack`        | dense linear algebra kernels                         | performance-sensitive dependency                             |
| `mumps-seq`                   | sparse direct linear solver                          | common open-source Ipopt linear solver                       |
| `libspral`                    | sparse linear solver library on current Linux builds | optional `linear_solver=spral` only if executable can use it |
| platform runtimes             | compiler/runtime ABI support                         | must match active conda env                                  |

Ipopt’s installation docs emphasize that Ipopt uses external packages such as ASL, BLAS/LAPACK, and at least one sparse symmetric-indefinite linear solver; they also state that most runtime is often spent solving the linear system and that linear-solver choice impacts speed and robustness. ([COIN-OR][8])

---

## 1.6 `ipopt` versus `cyipopt`

### `ipopt`

```bash
conda install -c conda-forge ipopt
```

Provides:

```text
ipopt executable
libipopt shared library
Ipopt headers / metadata where packaged
ASL-enabled executable path for .nl solving
linear solver dependencies from package build
```

Use when:

```python
opt = pyo.SolverFactory("ipopt")
res = opt.solve(model)
```

### `cyipopt`

```bash
conda install -c conda-forge cyipopt
```

Provides:

```text
Python Cython wrapper around Ipopt
direct Python callback interface
scipy-compatible minimize_ipopt interface
not required for Pyomo SolverFactory("ipopt")
```

The cyipopt docs define cyipopt as a Python wrapper around Ipopt, and the conda-forge cyipopt page identifies it as a Cython wrapper; by contrast, Pyomo’s standard Ipopt path uses the external `ipopt` executable through an NL-file interface, not cyipopt. ([Cyipopt][9])

### Agent decision table

| Need                                           | Install                                     | Interface                         |
| ---------------------------------------------- | ------------------------------------------- | --------------------------------- |
| Pyomo model solve via `SolverFactory("ipopt")` | `pyomo ipopt`                               | external executable               |
| Direct Python callback NLP without Pyomo       | `cyipopt`                                   | Python wrapper                    |
| C++/C embedding                                | `ipopt` + dev artifacts / source build      | linked library                    |
| Custom HSL/Pardiso/MKL Ipopt                   | source build or custom binary               | executable/library                |
| Repeated Pyomo solve with NL-file interface    | `pyomo ipopt`                               | external executable               |
| Persistent in-memory Ipopt callbacks           | not standard Pyomo `SolverFactory("ipopt")` | consider cyipopt/custom interface |

---

## 1.7 Pyomo solver wiring semantics

### Classic interface

```python
import pyomo.environ as pyo

opt = pyo.SolverFactory("ipopt")
opt.options["tol"] = 1e-8
opt.options["max_iter"] = 1000
res = opt.solve(model, tee=True)
```

### Explicit executable

```python
opt = pyo.SolverFactory("ipopt", executable="/abs/path/to/ipopt")
```

Pyomo’s solver recipe docs state that `tee=True` streams solver output, `optimizer.options[...]` stores persistent solver-object options, `solve(..., options={...})` passes solve-local temporary options, and `SolverFactory(..., executable=...)` sets a solver executable path when it is not on `PATH`. ([Pyomo Documentation][10])

### Solve-local options

```python
res = opt.solve(
    model,
    tee=True,
    options={
        "tol": 1e-8,
        "linear_solver": "mumps",
        "print_user_options": "yes",
    },
)
```

### Persistent options

```python
opt = pyo.SolverFactory("ipopt")
opt.options.update({
    "tol": 1e-8,
    "max_iter": 2000,
})
res1 = opt.solve(m1)
res2 = opt.solve(m2)   # same options persist
```

### Option file options through legacy Pyomo interface

```python
opt = pyo.SolverFactory("ipopt")

# Writes an Ipopt options file entry, not just command-line key=value.
opt.options["OF_output_file"] = "ipopt.log"
opt.options["OF_file_print_level"] = 5

res = opt.solve(model, tee=True)
```

Pyomo’s Ipopt plugin code maps normal options to command-line/env options and handles `OF_`-prefixed options by creating a temporary Ipopt option file; it also warns/handles conflicts with `ipopt.opt` and `option_file_name`. ([Pyomo Documentation][4])

---

## 1.8 `ipopt.opt` deployment pattern

### Local option file

```text
# ipopt.opt
tol 1e-8
max_iter 1000
print_user_options yes
linear_solver mumps
```

### Direct executable check

```bash
ipopt my_model.nl
```

Ipopt option files are named `ipopt.opt` by default; each non-comment line is `option_name whitespace value`; and Ipopt notes that `ipopt.opt` is given preference when overriding options set elsewhere in AMPL/executable contexts. ([COIN-OR][3])

### Agent rule

```text
small script / notebook       -> opt.options[...] or solve(options={...})
version-controlled workflow   -> ipopt.opt beside run script / working_dir
Pyomo legacy OF_ file options -> use opt.options["OF_<option>"]
avoid ambiguity               -> do not mix cwd ipopt.opt + OF_ options casually
```

---

## 1.9 BLAS/LAPACK deployment considerations

### Conda default

```bash
conda list "libblas|liblapack|openblas|mkl|blis"
```

### OpenBLAS-style conda-forge baseline

```yaml
dependencies:
  - libblas=*=*openblas
  - liblapack=*=*openblas
  - ipopt
  - pyomo
```

### MKL-style conda variant, when compatible/available

```yaml
dependencies:
  - libblas=*=*mkl
  - liblapack=*=*mkl
  - ipopt
  - pyomo
```

Ipopt’s source-install docs recommend efficient BLAS/LAPACK tailored to hardware and give explicit MKL linking examples for source builds; the conda-forge package itself depends on abstract `libblas`/`liblapack`, so the actual implementation is selected by the environment’s BLAS variant constraints. ([COIN-OR][8])

### Agent guidance

```text
single-user reproducibility > raw speed:
  pin BLAS variant in env yaml

performance benchmarking:
  compare OpenBLAS vs MKL on representative NLPs

cluster deployment:
  avoid uncontrolled thread oversubscription:
    OMP_NUM_THREADS=1
    OPENBLAS_NUM_THREADS=1
    MKL_NUM_THREADS=1
```

---

## 1.10 Linear solver deployment considerations

### Built-in / conda-packaged baseline

```python
opt.options["linear_solver"] = "mumps"
```

MUMPS is included in current conda-forge `ipopt` dependency metadata and is the safest cross-platform first choice in conda-forge environments. ([prefix.dev][7])

### Linux SPRAL possibility

```python
opt.options["linear_solver"] = "spral"
```

Current conda-forge Linux builds list `libspral` as a dependency, but agents should still probe `has_linear_solver("spral")` before emitting solver options, because Ipopt’s option availability/defaults are build-specific. ([prefix.dev][7])

### HSL runtime-loading pattern

```text
linear_solver ma57
hsllib /path/to/libhsl.so
```

Ipopt docs state that HSL routines may be loaded at runtime through `hsllib` if an HSL solver is selected, allowing MA27/MA57/MA77/MA86/MA97/MC19 usage without recompiling Ipopt, subject to having the appropriate shared library and license. ([COIN-OR][8])

### Pardiso runtime-loading pattern

```text
linear_solver pardiso
pardisolib /path/to/libpardiso.so
```

Ipopt 3.14 distinguishes `pardiso` for Pardiso Project and `pardisomkl` for Intel MKL Pardiso; the docs state that Pardiso Project is loaded at runtime via `pardisolib`, while MKL Pardiso is selected with `linear_solver=pardisomkl` when Ipopt was compiled with MKL support. ([COIN-OR][8])

### Solver-name surface

```text
linear_solver ∈ {
  ma27, ma57, ma77, ma86, ma97,
  pardiso, pardisomkl,
  spral,
  wsmp,
  mumps,
  custom
}
```

Ipopt’s options reference lists these values for `linear_solver`, but installed availability depends on build configuration. ([COIN-OR][3])

---

## 1.11 When conda-forge is enough

Use conda-forge `ipopt` when:

```text
Pyomo SolverFactory("ipopt") workflow
standard .nl-file solve
MUMPS acceptable
Linux SPRAL availability acceptable after probe
no proprietary sparse solver dependency
no custom Ipopt patches
no special integer-size / precision build
no direct compiled embedding beyond conda-provided ABI
fast reproducible cross-platform setup valued over absolute peak NLP speed
```

Value case:

```text
one-command install
cross-platform artifacts
ASL-enabled executable
MUMPS included
Pyomo-compatible executable on PATH
managed BLAS/LAPACK ABI
no compiler toolchain required
good default for LLM-generated deployment recipes
```

Conda-forge publishes ready-to-install `ipopt` builds and Pyomo documents conda-forge as a solver installation source; cyipopt’s install docs also state that Conda Forge supplies a basic Ipopt build suitable for many use cases. ([Pyomo Documentation][1])

---

## 1.12 When source/custom builds are required

Source/custom binary required or strongly justified when:

```text
need HSL linked or runtime-loaded with controlled deployment
need MA57 / MA97 for robustness/performance benchmarks
need Pardiso Project integration
need Intel MKL Pardiso via pardisomkl
need WSMP
need custom BLAS/LAPACK link flags
need 64-bit integer build
need single-precision Ipopt build
need custom Ipopt patch / debug instrumentation
need custom compiler ABI or static linking
need embedded library integration with strict ABI constraints
```

Ipopt’s install guide covers source compilation, dependencies, ASL, BLAS/LAPACK, HSL, MUMPS, Pardiso Project, MKL Pardiso, SPRAL, WSMP, single-precision builds, and 64-bit integer builds; it also states that third-party solver licensing is the user’s responsibility. ([COIN-OR][8])

### Source-build dependency sketch

```bash
# Linux system-level sketch, not conda-only
sudo apt-get install gcc g++ gfortran git patch wget pkg-config liblapack-dev libmetis-dev
```

Ipopt’s Linux source-install instructions list compilers, git, patch, wget, pkg-config, LAPACK, and METIS-related dependencies as typical prerequisites. ([COIN-OR][8])

### Custom HSL source-build sketch

```bash
# pseudo-flow
git clone https://github.com/coin-or-tools/ThirdParty-HSL.git
# obtain HSL separately under license; follow ThirdParty-HSL instructions

git clone https://github.com/coin-or/Ipopt.git
cd Ipopt
mkdir build && cd build
../configure --with-hsl-cflags="..." --with-hsl-lflags="..."
make -j
make test
make install
```

### Runtime HSL with conda Ipopt: verify, do not assume

```text
ipopt.opt:
  linear_solver ma57
  hsllib /absolute/path/to/libhsl.so
```

Then:

```bash
ipopt -= | grep -i hsl
python - <<'PY'
import pyomo.environ as pyo
opt = pyo.SolverFactory("ipopt")
print(opt.has_linear_solver("ma57"))
PY
```

**Agent warning:** licensing, shared-library search path, ABI compatibility, and Ipopt build support determine success. Do not emit `linear_solver=ma57` without a probe.

---

## 1.13 Notebooks and kernels: common failure mode

### Failure signature

```text
shell:
  which ipopt -> /.../envs/nlp/bin/ipopt

notebook:
  SolverFactory("ipopt").available() -> False
```

Cause:

```text
Jupyter kernel is not running inside the same conda/micromamba env.
```

Fix:

```bash
micromamba activate nlp
python -m pip install ipykernel
python -m ipykernel install --user --name nlp --display-name "Python (nlp)"
```

Notebook check:

```python
import sys, shutil
import pyomo.environ as pyo

print(sys.executable)
print(shutil.which("ipopt"))

opt = pyo.SolverFactory("ipopt")
print(opt.available(exception_flag=False))
```

---

## 1.14 Windows deployment notes

### Install

```powershell
conda create -n nlp -c conda-forge python=3.11 pyomo ipopt
conda activate nlp
where ipopt
ipopt -v
```

### Pyomo executable override

```python
opt = pyo.SolverFactory(
    "ipopt",
    executable=r"C:\Users\USER\miniforge3\envs\nlp\Library\bin\ipopt.exe",
)
```

### Windows-specific agent cautions

```text
use raw string paths or pathlib.Path
prefer conda-forge package over pip ipopt attempts
ensure activated env modifies PATH
check Library\bin is visible
do not mix python.org Python with conda-built Ipopt unless you know ABI/path implications
```

The conda-forge `ipopt` page lists Windows 64-bit builds, and the cyipopt Windows source-build docs explicitly recommend conda/Miniconda-style distributions over python.org Python for this ecosystem because Python/C-extension/Ipopt binary integration can be issue-prone. ([Anaconda][6])

---

## 1.15 macOS deployment notes

### Apple Silicon

```bash
micromamba create -n nlp -c conda-forge python=3.11 pyomo ipopt
micromamba activate nlp
python -c "import platform; print(platform.machine())"
which ipopt
```

### Avoid arch mixing

```text
arm64 Python + arm64 ipopt       -> ok
x86_64 Python under Rosetta + x86_64 ipopt -> ok
arm64 Python + x86_64 ipopt      -> bad
```

### Inspect package subdir

```bash
conda list ipopt
python - <<'PY'
import platform, sys
print(platform.platform())
print(platform.machine())
print(sys.executable)
PY
```

Conda-forge publishes both `osx-arm64` and `osx-64` Ipopt builds, so architecture consistency must be treated as part of environment correctness. ([Anaconda][6])

---

## 1.16 Linux / HPC deployment notes

### Prefix install outside `$HOME` quota

```bash
export MAMBA_ROOT_PREFIX=/scratch/$USER/micromamba
micromamba create -p /scratch/$USER/envs/nlp -c conda-forge python=3.11 pyomo ipopt
micromamba run -p /scratch/$USER/envs/nlp python solve.py
```

### Thread containment

```bash
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
```

### Batch-job self-check

```bash
set -euo pipefail
micromamba run -p /scratch/$USER/envs/nlp python - <<'PY'
import shutil
import pyomo.environ as pyo
print("ipopt path:", shutil.which("ipopt"))
opt = pyo.SolverFactory("ipopt")
print("available:", opt.available(exception_flag=False))
print("version:", opt.version())
PY
```

### MPI caution

For scenario-parallel Pyomo jobs, run multiple independent Ipopt processes rather than assuming the conda `mumps-seq` build is MPI-safe. Ipopt’s install notes discuss MUMPS MPI/non-MPI behavior and potential MPI symbol interactions for non-MPI MUMPS builds. ([COIN-OR][8])

---

## 1.17 Docker deployment pattern

### Micromamba Dockerfile skeleton

```dockerfile
FROM mambaorg/micromamba:2.0.0

COPY --chown=$MAMBA_USER:$MAMBA_USER environment.yml /tmp/environment.yml

RUN micromamba install -y -n base -f /tmp/environment.yml \
    && micromamba clean --all --yes

COPY --chown=$MAMBA_USER:$MAMBA_USER . /app
WORKDIR /app

ENTRYPOINT ["micromamba", "run", "-n", "base"]
CMD ["python", "solve.py"]
```

### `environment.yml`

```yaml
channels:
  - conda-forge
channel_priority: strict
dependencies:
  - python=3.11
  - pyomo
  - ipopt=3.14.19
```

### Runtime smoke

```bash
docker run --rm image-name python - <<'PY'
import shutil
import pyomo.environ as pyo
print(shutil.which("ipopt"))
print(pyo.SolverFactory("ipopt").available(exception_flag=False))
PY
```

---

## 1.18 Failure-mode map

### `ApplicationError: No executable found for solver 'ipopt'`

Root causes:

```text
ipopt package not installed
wrong env active
Jupyter kernel mismatch
PATH missing env bin/Library/bin
using pip-installed Pyomo without solver executable
```

Diagnostics:

```bash
python - <<'PY'
import sys, shutil
import pyomo.environ as pyo

print("python:", sys.executable)
print("ipopt:", shutil.which("ipopt"))
opt = pyo.SolverFactory("ipopt")
print("available:", opt.available(exception_flag=False))
PY
```

Fixes:

```bash
conda install -c conda-forge ipopt
# or
micromamba install -n nlp -c conda-forge ipopt
```

or:

```python
opt = pyo.SolverFactory("ipopt", executable="/absolute/path/to/ipopt")
```

Pyomo’s Ipopt plugin searches for executable name `ipopt` and disables the solver if it cannot locate it. ([Pyomo Documentation][4])

### `Selected linear solver ... not available`

Root causes:

```text
linear_solver option names a solver not compiled/loaded in installed Ipopt
HSL/Pardiso shared library missing
library path missing
license-protected binary not deployed
```

Diagnostics:

```bash
ipopt --print-options | grep -i linear_solver -A20
```

```python
print(opt.has_linear_solver("mumps"))
print(opt.has_linear_solver("ma57"))
```

Fix:

```python
opt.options["linear_solver"] = "mumps"
```

or deploy proper `hsllib` / `pardisolib` with license/ABI/path checks.

### `ipopt.opt` ignored or conflicting

Root causes:

```text
working directory different from expected
Pyomo wrote temporary OF_ option file
option_file_name override
solver working_dir mismatch
```

Diagnostics:

```python
import os
print(os.getcwd())
print(os.path.exists("ipopt.opt"))
```

Fix:

```python
opt.options["option_file_name"] = "/absolute/path/to/ipopt.opt"
```

or avoid `ipopt.opt` and use `opt.options`.

### `conda install ipopt` succeeds, Pyomo unavailable

Root causes:

```text
model code runs under different Python executable
PATH not updated
IDE interpreter not env interpreter
notebook kernel mismatch
```

Fix:

```python
import sys
print(sys.executable)
```

Then select the correct interpreter/kernel.

---

## 1.19 Agent-ready installation validator

```python
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from typing import Any

import pyomo.environ as pyo


@dataclass
class IpoptEnvReport:
    python: str
    ipopt_path: str | None
    pyomo_solver_available: bool
    pyomo_solver_version: Any
    ipopt_v_stdout: str
    mumps_available: Any
    spral_available: Any


def _run(cmd: list[str]) -> str:
    try:
        return subprocess.run(
            cmd,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=20,
        ).stdout.strip()
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"


def inspect_ipopt_env() -> IpoptEnvReport:
    ipopt_path = shutil.which("ipopt")
    opt = pyo.SolverFactory("ipopt")

    available = bool(opt.available(exception_flag=False))
    version = None
    try:
        version = opt.version()
    except Exception as exc:
        version = f"{type(exc).__name__}: {exc}"

    def has_ls(name: str) -> Any:
        try:
            return opt.has_linear_solver(name)
        except Exception as exc:
            return f"{type(exc).__name__}: {exc}"

    return IpoptEnvReport(
        python=sys.executable,
        ipopt_path=ipopt_path,
        pyomo_solver_available=available,
        pyomo_solver_version=version,
        ipopt_v_stdout=_run(["ipopt", "-v"]) if ipopt_path else "",
        mumps_available=has_ls("mumps") if available else None,
        spral_available=has_ls("spral") if available else None,
    )


if __name__ == "__main__":
    print(json.dumps(asdict(inspect_ipopt_env()), indent=2, default=str))
```

Usage:

```bash
python inspect_ipopt_env.py
```

Hard fail variant:

```python
report = inspect_ipopt_env()
if not report.pyomo_solver_available:
    raise SystemExit(
        "Ipopt unavailable to Pyomo. Install conda-forge::ipopt into the active "
        "environment or pass executable=... to SolverFactory."
    )
```

---

## 1.20 Deployment checklist for LLM agents

```text
[ ] Create isolated conda/micromamba env.
[ ] Use conda-forge channel; prefer strict channel priority.
[ ] Install pyomo and ipopt in same env.
[ ] Verify python executable, ipopt executable, SolverFactory availability.
[ ] Run minimal NLP smoke test.
[ ] Print installed option surface with ipopt -= or --print-options.
[ ] Probe linear solvers before selecting non-MUMPS solvers.
[ ] Pin ipopt version for production.
[ ] Avoid cyipopt unless direct Python Ipopt wrapper behavior is required.
[ ] Avoid source builds unless custom HSL/Pardiso/MKL/SPRAL/ABI/build flags are required.
[ ] Register notebook kernel from the same env if using Jupyter.
[ ] On Windows, verify Library\bin and raw executable path if needed.
[ ] On macOS, avoid arm64/x86_64 architecture mixing.
[ ] On HPC, use explicit prefixes, micromamba run, and thread caps.
```

[1]: https://pyomo.readthedocs.io/en/latest/getting_started/installation.html "Installation — Pyomo 6.10.1.dev0 documentation"
[2]: https://mamba.readthedocs.io/en/latest/user_guide/micromamba.html?utm_source=chatgpt.com "Micromamba User Guide — documentation"
[3]: https://coin-or.github.io/Ipopt/OPTIONS.html "Ipopt: Ipopt Options"
[4]: https://pyomo.readthedocs.io/en/6.9.3/_modules/pyomo/solvers/plugins/solvers/IPOPT.html "pyomo.solvers.plugins.solvers.IPOPT — Pyomo 6.9.3 documentation"
[5]: https://pyomo.readthedocs.io/en/stable/api/pyomo.contrib.solver.solvers.ipopt.Ipopt.html "Ipopt — Pyomo 6.10.0 documentation"
[6]: https://anaconda.org/conda-forge/ipopt "ipopt - conda-forge | Anaconda.org"
[7]: https://prefix.dev/channels/conda-forge/packages/ipopt "ipopt - conda-forge"
[8]: https://coin-or.github.io/Ipopt/INSTALL.html "Ipopt: Installing Ipopt"
[9]: https://cyipopt.readthedocs.io/ "Welcome to cyipopt’s documentation! — cyipopt 1.7.0 documentation"
[10]: https://pyomo.readthedocs.io/en/latest/howto/solver_recipes.html "Solver Recipes — Pyomo 6.10.1.dev0 documentation"

# Ipopt Advanced — Section 2: packaging reality: “installed Ipopt” versus “all Ipopt features”

Style target: advanced technical catalog / agent-ready reference. 

## 2.0 Core invariant

```text id="80q8fr"
Ipopt documentation enumerates the theoretical option surface.
The installed Ipopt executable exposes the compiled / linked / runtime-loadable feature surface.
Pyomo only sees what the executable can actually run.
```

**Agent rule:** never emit `linear_solver=ma57`, `linear_solver=spral`, `linear_solver=pardiso`, or `linear_solver=pardisomkl` solely because the Ipopt docs list the option. Ipopt’s own options reference states that availability/default values of some linear-solver options depend on the configuration used to build Ipopt, and recommends using printed option documentation for the particular build. ([COIN-OR][1])

---

## 2.1 Feature-surface taxonomy

| Capability class           | Build/runtime dependency                         | Inspection method                                                      | Agent action                                    |
| -------------------------- | ------------------------------------------------ | ---------------------------------------------------------------------- | ----------------------------------------------- |
| Ipopt executable exists    | `ipopt` binary on `PATH` or explicit path        | `which ipopt`, `where ipopt`, `SolverFactory("ipopt").available()`     | hard-fail if absent                             |
| AMPL / `.nl` solve path    | ASL-enabled executable                           | solve a Pyomo smoke NLP                                                | required for standard Pyomo workflow            |
| Linear solver availability | linked or runtime-loadable solver library        | `has_linear_solver(...)`, solver log, `--print-options`                | probe before selecting                          |
| Linear solver defaults     | compile configuration                            | solver log: “running with linear solver ...”                           | record in environment report                    |
| Option availability        | build configuration                              | `ipopt --print-options`, `ipopt -=`, `print_options_documentation=yes` | do not assume global option list                |
| Runtime library loading    | loader enabled + shared library path + ABI match | HSL/Pardiso test solve                                                 | deploy `hsllib` / `pardisolib` only after probe |
| License validity           | Ipopt license + third-party solver license       | package metadata + vendor/license terms                                | user/org responsibility                         |

---

## 2.2 Installed build versus documented option universe

### Documented `linear_solver` option universe

Ipopt’s options reference lists these possible values for `linear_solver`:

```text id="w5tdn9"
ma27
ma57
ma77
ma86
ma97
pardiso
pardisomkl
spral
wsmp
mumps
custom
```

The same section defines `linear_solver` as the package used for solving the augmented linear system to obtain search directions; the listed values include HSL solvers, Pardiso Project, Intel MKL Pardiso, SPRAL, WSMP, MUMPS, and custom solvers. ([COIN-OR][1])

### Installed executable reality

```text id="zp52fi"
listed in documentation  ≠ accepted by current executable
accepted by option parser ≠ linked successfully at runtime
linked successfully       ≠ numerically best for this model class
```

**Best-practice agent behavior**

```python id="b59t4i"
def choose_linear_solver(probe_results: dict[str, bool]) -> str:
    # Conservative default for conda-forge deployments.
    if probe_results.get("mumps"):
        return "mumps"
    raise RuntimeError("No verified Ipopt linear solver available.")
```

Do not silently fall through to HSL/Pardiso values unless an explicit deployment spec includes shared-library paths, licensing confirmation, and a successful `has_linear_solver(...)` probe.

---

## 2.3 Conda-forge practical baseline

### Current package identity

Current conda-forge metadata lists `ipopt` version **3.14.19**, license metadata **EPL-1.0**, and platforms including `linux-64`, `linux-aarch64`, `linux-ppc64le`, `osx-64`, `osx-arm64`, and `win-64`. ([prefix.dev][2])

### Current dependency pattern

Current conda-forge metadata shows `mumps-seq`, `libblas`, `liblapack`, and `ampl-asl` across major platform variants; current Linux variants also list `libspral` as a dependency, while macOS and Windows variants shown list `mumps-seq` but not `libspral`. ([prefix.dev][2])

```text id="2i4mb9"
conda-forge ipopt practical baseline:
  broadly expect:
    ampl-asl
    libblas
    liblapack
    mumps-seq

  current Linux metadata additionally shows:
    libspral

  do not blindly expect:
    HSL MA27/MA57/MA77/MA86/MA97
    Pardiso Project
    MKL Pardiso
    WSMP
```

### Agent deployment rule

```text id="e1w2ss"
Conda-forge default recommendation:
  linear_solver=mumps, or omit linear_solver and let installed default run.

Linux optimization experiment:
  probe spral; if true, benchmark mumps vs spral on representative model family.

HSL/Pardiso/MKL:
  require explicit deployment path + license + probe.
```

---

## 2.4 Inspecting the actual installed Ipopt build

### Shell-level audit

Linux/macOS:

```bash id="m45vji"
which ipopt
ipopt -v
ipopt -=
ipopt --print-options > ipopt.print-options.txt
```

Windows:

```powershell id="26k6nl"
where ipopt
ipopt -v
ipopt -=
ipopt --print-options > ipopt.print-options.txt
```

Ipopt’s options docs state that the AMPL solver executable supports `-=` to print AMPL-available options and `--print-options` to generate the option documentation for the executable; `print_options_documentation=yes` also prints algorithmic options before solving. ([COIN-OR][1])

### Pyomo-level audit: legacy solver interface

```python id="mycnd4"
import pyomo.environ as pyo

opt = pyo.SolverFactory("ipopt")

print("available:", opt.available(exception_flag=False))
print("executable:", opt.executable())
print("version:", opt.version())

for name in [
    "mumps",
    "spral",
    "ma27",
    "ma57",
    "ma77",
    "ma86",
    "ma97",
    "pardiso",
    "pardisomkl",
    "wsmp",
]:
    try:
        print(f"{name:12s}", opt.has_linear_solver(name))
    except Exception as exc:
        print(f"{name:12s}", f"{type(exc).__name__}: {exc}")
```

Pyomo’s classic Ipopt API exposes `available()`, `executable()`, `version()`, and `has_linear_solver(linear_solver)` methods. ([Pyomo Documentation][3])

### Pyomo-level audit: newer contrib solver interface

```python id="7b1gcd"
from pyomo.contrib.solver.solvers.ipopt import Ipopt

solver = Ipopt()

print("available:", bool(solver.available()))
print("version:", solver.version())

for name in [
    "mumps",
    "spral",
    "ma27",
    "ma57",
    "ma77",
    "ma86",
    "ma97",
    "pardiso",
    "pardisomkl",
    "wsmp",
]:
    try:
        print(f"{name:12s}", solver.has_linear_solver(name))
    except Exception as exc:
        print(f"{name:12s}", f"{type(exc).__name__}: {exc}")
```

The newer Pyomo Ipopt interface documents `has_linear_solver(linear_solver)` as a method that solves a small problem to determine whether the Ipopt executable has access to a specified linear solver; it also exposes `available()`, `version()`, `solver_options`, and an `executable` config that defaults to searching `PATH` for `ipopt`. ([Pyomo Documentation][4])

---

## 2.5 Solver-log inspection

### Force log verbosity and user option echo

```python id="9zk16b"
import pyomo.environ as pyo

opt = pyo.SolverFactory("ipopt")
opt.options.update({
    "print_level": 5,
    "print_user_options": "yes",
    "linear_solver": "mumps",
})

res = opt.solve(model, tee=True)
```

`print_user_options=yes` causes Ipopt to print user-set options, their values, and whether they have been used, although the docs warn that this information may be incorrect in some internal-flow cases. ([COIN-OR][1])

### Capture solver log to file: Pyomo-level

```python id="juodoe"
res = opt.solve(
    model,
    tee=True,
    logfile="ipopt.solve.log",
)
```

### Capture solver log to file: Ipopt option-file-only output option

```text id="decrvt"
# ipopt.opt
output_file ipopt_file_output.log
file_print_level 5
print_user_options yes
```

Ipopt documents that `output_file` and `file_print_level` only work when read from `ipopt.opt`; `output_file` writes a file, and `file_print_level` controls file verbosity. ([COIN-OR][1])

### Log evidence to preserve

```text id="na5az2"
Ipopt version
linear solver actually used
user options marked used / unused
MUMPS / SPRAL / HSL / Pardiso startup messages
termination status
linear-solver error messages
restoration / numerical failure markers
```

---

## 2.6 Runtime-loadable solvers: HSL and Pardiso

### Loader capability

Ipopt’s install guide states that Ipopt can load HSL or Pardiso libraries at runtime and that this feature can be disabled at build time via `--disable-linear-solver-loader`. ([COIN-OR][5])

### HSL option surface

```text id="d2hyrr"
linear_solver ma57
hsllib /absolute/path/to/libhsl.so
```

Ipopt’s options reference defines `hsllib` as the name of the library containing HSL routines for runtime loading; the default names are `libhsl.so` on Linux, `libhsl.dylib` on macOS, and `libhsl.dll` on Windows, and the value may contain a path. ([COIN-OR][1])

### Pardiso Project option surface

```text id="73ei3c"
linear_solver pardiso
pardisolib /absolute/path/to/libpardiso.so
```

Ipopt’s options reference defines `pardisolib` as the name of the Pardiso Project library for runtime loading, and the option value may be any acceptable filename, including a path. ([COIN-OR][1])

### MKL Pardiso surface

```text id="vnzj1m"
linear_solver pardisomkl
```

Ipopt’s changelog distinguishes Pardiso Project from Intel MKL Pardiso: Pardiso Project is selected by `linear_solver=pardiso`, MKL Pardiso by `linear_solver=pardisomkl`, and MKL-specific options use names such as `pardisomkl_msglvl` and `pardisomkl_order`. ([COIN-OR][6])

### Runtime-loaded HSL test

```python id="i2rdzk"
import pyomo.environ as pyo

opt = pyo.SolverFactory("ipopt")
opt.options.update({
    "linear_solver": "ma57",
    "hsllib": "/absolute/path/to/libhsl.so",
    "print_user_options": "yes",
})

res = opt.solve(model, tee=True)
```

### Runtime-loaded Pardiso Project test

```python id="4o0p9q"
opt = pyo.SolverFactory("ipopt")
opt.options.update({
    "linear_solver": "pardiso",
    "pardisolib": "/absolute/path/to/libpardiso.so",
    "print_user_options": "yes",
})
res = opt.solve(model, tee=True)
```

### Runtime-loader failure classes

```text id="ttfiur"
option not recognized:
  loader not compiled / old Ipopt / unavailable interface

invalid linear_solver setting:
  solver interface not built into executable

shared library cannot be opened:
  bad path, bad extension, missing runtime path, OS loader issue

symbol lookup failure:
  wrong HSL/Pardiso version, ABI mismatch, compiler/runtime mismatch

license/legal failure:
  missing or invalid third-party license or redistribution permission

numerical failure:
  solver loads but fails on model; benchmark/tune or choose different solver
```

---

## 2.7 Licensing implications

### Ipopt package license

Current conda-forge metadata lists `ipopt` under **EPL-1.0**. ([prefix.dev][2])

### Third-party solver licensing

Ipopt’s install guide states that external packages such as ASL, BLAS, LAPACK, and sparse linear solvers are not all part of the Ipopt source distribution; it also states that third-party components have licenses different from Ipopt and that users are responsible for ensuring their download and usage complies with those licenses. ([COIN-OR][5])

### Agent-safe licensing matrix

| Component         | Typical role                | Packaging expectation                | Agent licensing stance                         |
| ----------------- | --------------------------- | ------------------------------------ | ---------------------------------------------- |
| Ipopt             | NLP algorithm               | conda-forge package                  | EPL-1.0 package metadata                       |
| ASL / `ampl-asl`  | `.nl` executable interface  | conda dependency                     | use package metadata/license from environment  |
| BLAS/LAPACK       | dense kernels               | conda dependency                     | respect selected implementation license        |
| MUMPS             | sparse linear solver        | conda dependency                     | conda-packaged baseline                        |
| SPRAL             | sparse linear solver        | current conda-forge Linux dependency | probe before use                               |
| HSL               | sparse linear solver family | usually separately obtained          | require explicit license confirmation          |
| Pardiso Project   | sparse linear solver        | separately obtained                  | require vendor license + `pardisolib` path     |
| Intel MKL Pardiso | sparse linear solver        | MKL-linked build required            | require MKL distribution/license compatibility |
| WSMP              | sparse linear solver        | separately obtained                  | require vendor license/build                   |

**Agent rule:** do not include HSL/Pardiso shared libraries in generated repositories, Docker images, or conda packages unless the user explicitly confirms redistribution rights.

---

## 2.8 Capability audit script: one-command build fingerprint

```python id="5sxhme"
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pyomo.environ as pyo


LINEAR_SOLVER_CANDIDATES = [
    "mumps",
    "spral",
    "ma27",
    "ma57",
    "ma77",
    "ma86",
    "ma97",
    "pardiso",
    "pardisomkl",
    "wsmp",
]


@dataclass
class LinearSolverProbe:
    name: str
    available: bool | None
    error: str | None = None


@dataclass
class IpoptCapabilityReport:
    python_executable: str
    ipopt_path: str | None
    pyomo_ipopt_available: bool
    pyomo_ipopt_executable: str | None
    pyomo_ipopt_version: Any
    ipopt_version_output: str
    option_dump_path: str | None
    linear_solvers: list[LinearSolverProbe]


def run_text(cmd: list[str], timeout: int = 60) -> str:
    try:
        return subprocess.run(
            cmd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
        ).stdout
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"


def write_option_dump(ipopt_path: str | None, out: Path) -> str | None:
    if ipopt_path is None:
        return None
    out.write_text(run_text([ipopt_path, "--print-options"], timeout=120))
    return str(out)


def probe_linear_solvers(opt) -> list[LinearSolverProbe]:
    probes: list[LinearSolverProbe] = []
    for name in LINEAR_SOLVER_CANDIDATES:
        try:
            probes.append(LinearSolverProbe(name=name, available=bool(opt.has_linear_solver(name))))
        except Exception as exc:
            probes.append(
                LinearSolverProbe(
                    name=name,
                    available=None,
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
    return probes


def collect_report(option_dump_file: str = "ipopt.print-options.txt") -> IpoptCapabilityReport:
    ipopt_path = shutil.which("ipopt")
    opt = pyo.SolverFactory("ipopt")

    available = bool(opt.available(exception_flag=False))

    try:
        executable = str(opt.executable())
    except Exception:
        executable = None

    try:
        version = opt.version()
    except Exception as exc:
        version = f"{type(exc).__name__}: {exc}"

    return IpoptCapabilityReport(
        python_executable=sys.executable,
        ipopt_path=ipopt_path,
        pyomo_ipopt_available=available,
        pyomo_ipopt_executable=executable,
        pyomo_ipopt_version=version,
        ipopt_version_output=run_text([ipopt_path, "-v"]) if ipopt_path else "",
        option_dump_path=write_option_dump(ipopt_path, Path(option_dump_file)),
        linear_solvers=probe_linear_solvers(opt) if available else [],
    )


if __name__ == "__main__":
    report = collect_report()
    print(json.dumps(asdict(report), indent=2, default=str))
```

Usage:

```bash id="k8it6s"
python ipopt_capability_report.py > ipopt_capability_report.json
```

Commit artifacts for reproducibility:

```text id="zy5eqn"
ipopt_capability_report.json
ipopt.print-options.txt
environment.yml
conda list --explicit output
representative solver log
```

---

## 2.9 Option-surface parser: detect whether an option name appears

```python id="94zfax"
from pathlib import Path

def option_dump_contains(option_dump: str | Path, option_name: str) -> bool:
    text = Path(option_dump).read_text() if isinstance(option_dump, (str, Path)) else option_dump
    needle = f"{option_name}:"
    return needle in text or f"▸ {option_name}:" in text

assert option_dump_contains("ipopt.print-options.txt", "linear_solver")
```

**Use case**

```text id="h1782w"
preflight:
  if "hsllib" absent from option dump:
      do not attempt runtime HSL loading
  if "pardisolib" absent:
      do not attempt Pardiso Project runtime loading
  if "pardisomkl_*" absent:
      do not emit MKL-Pardiso tuning options
```

---

## 2.10 Safe solver-option selection pattern

```python id="n1fobq"
import pyomo.environ as pyo

def configure_ipopt_for_installed_build(
    *,
    preferred: list[str] = ("spral", "mumps"),
    strict: bool = False,
):
    opt = pyo.SolverFactory("ipopt")
    if not opt.available(exception_flag=False):
        raise RuntimeError("Ipopt executable unavailable to Pyomo.")

    availability: dict[str, bool] = {}
    for ls in preferred:
        try:
            availability[ls] = bool(opt.has_linear_solver(ls))
        except Exception:
            availability[ls] = False

    chosen = next((ls for ls in preferred if availability.get(ls)), None)

    if chosen is None:
        if strict:
            raise RuntimeError(f"No preferred Ipopt linear solver available: {availability}")
        # Omit linear_solver; let Ipopt installed default run.
        chosen = ""

    if chosen:
        opt.options["linear_solver"] = chosen

    opt.options.update({
        "tol": 1e-8,
        "print_user_options": "yes",
    })

    return opt, availability
```

**Agent behavior modes**

```text id="f7oos3"
strict deployment:
  fail if required solver unavailable

portable conda deployment:
  prefer mumps; optionally try spral on Linux if verified

benchmark deployment:
  run probe matrix; solve representative model with each available solver; store logs

custom solver deployment:
  require explicit shared-library path + successful smoke solve
```

---

## 2.11 HSL deployment advisory

### Minimal `ipopt.opt`

```text id="c3ske1"
linear_solver ma57
hsllib /opt/hsl/lib/libhsl.so
print_user_options yes
```

### Pyomo options equivalent

```python id="mktyat"
opt.options.update({
    "linear_solver": "ma57",
    "hsllib": "/opt/hsl/lib/libhsl.so",
    "print_user_options": "yes",
})
```

### Preflight

```bash id="34psb5"
test -f /opt/hsl/lib/libhsl.so
ipopt --print-options | grep -E "hsllib|linear_solver"
```

```python id="w4y9dc"
assert opt.has_linear_solver("ma57")
```

### Deployment failure prevention

```text id="r6pysv"
[ ] confirm HSL license and redistribution rights
[ ] confirm shared library extension for OS
[ ] confirm ABI / compiler runtime compatibility
[ ] use absolute path in hsllib
[ ] run tiny NLP probe with ma57
[ ] run representative model benchmark
[ ] record exact HSL library filename/hash outside public logs if required
```

---

## 2.12 Pardiso deployment advisory

### Pardiso Project

```text id="l9hlrl"
linear_solver pardiso
pardisolib /opt/pardiso/libpardiso.so
```

### Intel MKL Pardiso

```text id="2535tf"
linear_solver pardisomkl
```

**Distinction:** Ipopt separates Pardiso Project and Intel MKL Pardiso: Pardiso Project is selected by `linear_solver=pardiso` and loaded through `pardisolib`; Intel MKL Pardiso is selected by `linear_solver=pardisomkl` and has option names prefixed with `pardisomkl_`. ([COIN-OR][6])

### Agent routing

```text id="zug4if"
if user provides Pardiso Project .so/.dll/.dylib:
  use linear_solver=pardiso + pardisolib=<path>

if user provides MKL-linked Ipopt build:
  use linear_solver=pardisomkl

if user only has conda-forge ipopt:
  do not assume pardiso or pardisomkl
```

---

## 2.13 Build-dependent defaults: why logs matter

Ipopt’s options reference lists default `linear_solver` as `ma27`, but immediately notes that option availability/defaults related to linear solvers depend on how Ipopt was built. ([COIN-OR][1])

**Agent rule:** never document “Ipopt default linear solver is X” without qualifying:

```text id="9k9v9f"
The documented default in the generic Ipopt options page is not necessarily the runtime default
for a packaged executable; inspect the installed executable and solver log.
```

### Runtime detection by log scrape

```python id="rlq06l"
import io
import re
import pyomo.environ as pyo

buf = io.StringIO()

opt = pyo.SolverFactory("ipopt")
res = opt.solve(model, tee=buf)

log = buf.getvalue()
match = re.search(r"linear solver\s+([A-Za-z0-9_]+)", log, flags=re.I)
print(match.group(1) if match else "not detected")
```

For robust production reporting, prefer explicit `linear_solver=<verified solver>` plus `print_user_options=yes` over trying to infer defaults from logs.

---

## 2.14 Packaging smoke-test model for solver probes

```python id="eehocv"
import pyomo.environ as pyo

def small_nlp():
    m = pyo.ConcreteModel()
    m.x = pyo.Var(bounds=(0.1, 10.0), initialize=1.0)
    m.y = pyo.Var(bounds=(0.1, 10.0), initialize=1.5)
    m.obj = pyo.Objective(expr=(m.x - 1.0)**2 + (m.y - 2.0)**2)
    m.con = pyo.Constraint(expr=m.x * m.y >= 1.0)
    return m

def solve_with_linear_solver(linear_solver: str):
    m = small_nlp()
    opt = pyo.SolverFactory("ipopt")
    opt.options.update({
        "linear_solver": linear_solver,
        "tol": 1e-8,
        "print_user_options": "yes",
    })
    res = opt.solve(m, tee=True)
    return res, pyo.value(m.obj)

for ls in ["mumps", "spral", "ma57", "pardiso", "pardisomkl"]:
    try:
        print("TEST", ls)
        solve_with_linear_solver(ls)
    except Exception as exc:
        print("FAILED", ls, type(exc).__name__, exc)
```

**Use case:** human-readable smoke test when `has_linear_solver(...)` behavior is unavailable, too opaque, or divergent across Pyomo versions.

---

## 2.15 Best-practice feature-selection policy

### Portable conda-forge policy

```python id="qnamy7"
opt = pyo.SolverFactory("ipopt")
opt.options.update({
    "linear_solver": "mumps",
    "tol": 1e-8,
})
```

**Value case:** maximizes cross-platform reproducibility because current conda-forge metadata shows MUMPS as a dependency across major platform variants. ([prefix.dev][2])

### Linux conda-forge experiment policy

```python id="8q8xvq"
if opt.has_linear_solver("spral"):
    opt.options["linear_solver"] = "spral"
else:
    opt.options["linear_solver"] = "mumps"
```

**Value case:** uses current Linux `libspral` dependency where it actually works, but remains safe on macOS/Windows or older builds.

### Performance-benchmark policy

```text id="ebisfx"
for each verified linear solver:
  solve warm model family
  solve cold model family
  record objective, termination condition, iteration count, CPU/wall time, memory if available
  preserve solver log
select by benchmark, not solver reputation
```

Ipopt’s install guide states that a large fraction of Ipopt runtime is usually spent solving the linear system and that the selected linear solver affects speed and robustness, so benchmarking on representative model classes is justified. ([COIN-OR][5])

### Custom-license policy

```text id="6zk3xq"
HSL/Pardiso/WSMP/MKL:
  require:
    license confirmation
    library path / build provenance
    deployment environment
    successful smoke probe
    representative benchmark
```

---

## 2.16 Anti-patterns for LLM agents

```text id="rwk6y5"
BAD: opt.options["linear_solver"] = "ma57"  # because docs list it
GOOD: if opt.has_linear_solver("ma57"): opt.options["linear_solver"] = "ma57"

BAD: "conda-forge Ipopt has all solvers"
GOOD: "conda-forge Ipopt has packaged dependencies; probe actual solver availability"

BAD: "SPRAL available everywhere"
GOOD: "current Linux metadata lists libspral; probe before use"

BAD: "Pardiso and pardisomkl are the same"
GOOD: pardiso -> Pardiso Project via pardisolib; pardisomkl -> Intel MKL Pardiso

BAD: ship libhsl.so in generated Dockerfile
GOOD: require user-supplied HSL library path and license confirmation

BAD: infer option support from generic docs
GOOD: store ipopt --print-options for the exact executable
```

---

## 2.17 Agent-ready final checklist

```text id="1ahya1"
[ ] Capture conda package version and platform.
[ ] Capture ipopt path.
[ ] Capture ipopt -v output.
[ ] Capture ipopt --print-options output.
[ ] Capture ipopt -= output if AMPL option surface matters.
[ ] Run Pyomo SolverFactory("ipopt").available().
[ ] Run Pyomo opt.version().
[ ] Probe has_linear_solver("mumps").
[ ] Probe has_linear_solver("spral") on Linux.
[ ] Probe HSL/Pardiso only when shared libraries and licenses are supplied.
[ ] Record actual solver log for one smoke NLP.
[ ] Avoid using documented linear_solver values as proof of installed support.
[ ] Use MUMPS as the portable conda-forge baseline.
[ ] Treat HSL/Pardiso/MKL/WSMP as custom deployment features.
```

[1]: https://coin-or.github.io/Ipopt/OPTIONS.html "Ipopt: Ipopt Options"
[2]: https://prefix.dev/channels/conda-forge/packages/ipopt "ipopt - conda-forge"
[3]: https://pyomo.readthedocs.io/en/latest/api/pyomo.solvers.plugins.solvers.IPOPT.IPOPT.html "IPOPT — Pyomo 6.10.1.dev0 documentation"
[4]: https://pyomo.readthedocs.io/en/stable/api/pyomo.contrib.solver.solvers.ipopt.Ipopt.html "Ipopt — Pyomo 6.10.0 documentation"
[5]: https://coin-or.github.io/Ipopt/INSTALL.html "Ipopt: Installing Ipopt"
[6]: https://coin-or.github.io/Ipopt/md_ChangeLog.html "Ipopt: ChangeLog"

# Ipopt Advanced — Section 3: core NLP modeling contract

Style target: dense advanced technical catalog / agent-ready implementation reference. 

## 3.0 Contract invariant

```text id="xi9v3x"
Ipopt input contract:
  smooth continuous NLP
  finite-dimensional real variable vector x
  scalar objective f(x)
  vector constraint map g(x)
  lower/upper bounds on variables
  lower/upper bounds on constraints
  first/second derivative information from interface
  local KKT-style convergence target
```

Ipopt’s documented NLP form is `min f(x)` subject to `gL ≤ g(x) ≤ gU` and `xL ≤ x ≤ xU`, with `x ∈ R^n`; `f` and `g` may be linear or nonlinear and convex or nonconvex, but should be twice continuously differentiable. ([COIN-OR][1])

---

## 3.1 Canonical mathematical form

```text id="7lu51n"
minimize        f(x)

subject to      g_L <= g(x) <= g_U
                x_L <= x    <= x_U

where           x ∈ R^n
                f: R^n → R
                g: R^n → R^m
                x_L ∈ (R ∪ {-∞})^n
                x_U ∈ (R ∪ {+∞})^n
                g_L ∈ (R ∪ {-∞})^m
                g_U ∈ (R ∪ {+∞})^m
```

**Agent normalization rule**

```text id="wcaqux"
Any Pyomo objective/constraint system passed to Ipopt must serialize to:
  one scalar active objective
  zero or more continuous variables
  zero or more algebraic constraints
  each variable with lb/ub
  each constraint with lb/body/ub
```

**Internal representation mental model**

```text id="sb63hv"
variable bound:
  x_L[j] <= x[j] <= x_U[j]

upper-only constraint:
  g_i(x) <= u
  ⇔ g_L[i] = -∞, g_U[i] = u

lower-only constraint:
  l <= g_i(x)
  ⇔ g_L[i] = l, g_U[i] = +∞

equality constraint:
  g_i(x) = r
  ⇔ g_L[i] = r, g_U[i] = r

ranged constraint:
  l <= g_i(x) <= u
  ⇔ g_L[i] = l, g_U[i] = u
```

Equality constraints in Ipopt’s direct TNLP interface are represented by setting the lower and upper constraint bounds equal; bounds beyond the configured infinity thresholds are interpreted as absent lower/upper bounds. ([COIN-OR][2])

---

## 3.2 Pyomo variable contract: `Var` → `x`, `xL`, `xU`, initial point

### Scalar continuous variable

```python id="lr1fmg"
import pyomo.environ as pyo

m = pyo.ConcreteModel()

m.x = pyo.Var(
    domain=pyo.Reals,
    bounds=(0.0, 10.0),
    initialize=1.0,
)
```

Pyomo `Var` is a numeric variable that may be indexed; `domain` defaults to `Reals`, `bounds` is a `(lower, upper)` tuple or rule and defaults to `(None, None)`, and `initialize` supplies the starting value. ([Pyomo Documentation][3])

### Indexed continuous variable with data-dependent bounds

```python id="g64ohv"
m.I = pyo.Set(initialize=["A", "B", "C"])

lb = {"A": 0.0, "B": -5.0, "C": None}
ub = {"A": 10.0, "B": 5.0, "C": None}
x0 = {"A": 1.0, "B": 0.0, "C": 2.5}

def x_bounds(m, i):
    return (lb[i], ub[i])

def x_init(m, i):
    return x0[i]

m.x = pyo.Var(m.I, domain=pyo.Reals, bounds=x_bounds, initialize=x_init)
```

### Bound/domain anti-patterns

```python id="qbk9vr"
# BAD for Ipopt: discrete domain
m.z = pyo.Var(domain=pyo.Binary)

# BAD for Ipopt: integer domain
m.k = pyo.Var(domain=pyo.NonNegativeIntegers)

# GOOD for Ipopt: continuous relaxation
m.z_relaxed = pyo.Var(bounds=(0.0, 1.0), initialize=0.5)
```

**Agent rule:** `Binary`, `Integers`, `NonNegativeIntegers`, `PositiveIntegers`, and mixed discrete domains violate the continuous NLP contract unless deliberately relaxed or fixed before solve.

---

## 3.3 Pyomo constraint contract: `Constraint` → `g(x)`, `gL`, `gU`

Pyomo constraints are normally specified with equality or inequality expressions constructed by functions/rules, and Pyomo also supports explicit lower/body/upper constraint forms in kernel-style constraints. ([Pyomo Documentation][4])

### Equality

```python id="l56ee5"
m.eq = pyo.Constraint(expr=m.x["A"] + m.x["B"] == 3.0)
```

Ipopt representation:

```text id="2go18g"
g_i(x) = x_A + x_B
g_L[i] = 3.0
g_U[i] = 3.0
```

### Upper-only inequality

```python id="hgfbvf"
m.ub_con = pyo.Constraint(expr=m.x["A"]**2 + m.x["B"] <= 25.0)
```

Ipopt representation:

```text id="obtfga"
g_i(x) = x_A^2 + x_B
g_L[i] = -∞
g_U[i] = 25.0
```

### Lower-only inequality

```python id="8tm3i5"
m.lb_con = pyo.Constraint(expr=m.x["A"] * m.x["B"] >= 1.0)
```

Ipopt representation:

```text id="m6sb8x"
g_i(x) = x_A * x_B
g_L[i] = 1.0
g_U[i] = +∞
```

### Ranged inequality

```python id="tmq0a2"
m.range_con = pyo.Constraint(expr=pyo.inequality(1.0, m.x["A"] + m.x["B"], 5.0))
```

Equivalent tuple-style rule pattern:

```python id="6u0i2p"
def range_rule(m):
    return (1.0, m.x["A"] + m.x["B"], 5.0)

m.range_con_2 = pyo.Constraint(rule=range_rule)
```

Kernel-style explicit lower/body/upper form:

```python id="x94rf8"
import pyomo.core.kernel as pmo

x = pmo.variable()
c = pmo.constraint(lb=-1.0, body=0.5 * x, ub=1.0)
```

Pyomo kernel constraints document `lb`, `body`, `ub`, and `rhs`; `lb=None` is equivalent to `-inf`, `ub=None` is equivalent to `+inf`, and `rhs` implies equality. ([Pyomo Documentation][5])

---

## 3.4 Infinite bounds: Pyomo `None` versus Ipopt infinity thresholds

### Pyomo-side unbounded syntax

```python id="n7t4ur"
m.free = pyo.Var(bounds=(None, None), initialize=0.0)
m.lower_only = pyo.Var(bounds=(0.0, None), initialize=1.0)
m.upper_only = pyo.Var(bounds=(None, 100.0), initialize=10.0)

m.c_upper = pyo.Constraint(expr=m.free <= 10.0)
m.c_lower = pyo.Constraint(expr=m.free >= -10.0)
```

Pyomo `Var(bounds=...)` defaults to `(None, None)` for no explicit finite variable bound; Pyomo kernel constraints similarly treat `lb=None` as `-inf` and `ub=None` as `+inf`. ([Pyomo Documentation][3])

### Ipopt-side infinity interpretation

```text id="z9vowo"
nlp_lower_bound_inf:
  any bound <= this value is treated as -∞

nlp_upper_bound_inf:
  any bound >= this value is treated as +∞
```

Ipopt’s option reference gives default values around `-1e19` and `1e19` for `nlp_lower_bound_inf` and `nlp_upper_bound_inf`, respectively; the TNLP reference states that lower bounds at or below the lower threshold imply no lower bound and upper bounds at or above the upper threshold imply no upper bound. ([COIN-OR][6])

### Critical modeling pitfall: large finite physical bounds

```python id="m4y98u"
# DANGEROUS if Ipopt nlp_upper_bound_inf default is 1e19:
m.x = pyo.Var(bounds=(0.0, 1e20), initialize=1.0)
```

Ipopt may interpret `1e20` as `+∞` under the default `nlp_upper_bound_inf` threshold. Use a smaller physically meaningful bound, rescale units, or explicitly change the infinity threshold only when the model truly needs finite magnitudes near `1e20`.

```python id="llx672"
opt = pyo.SolverFactory("ipopt")
opt.options.update({
    "nlp_upper_bound_inf": 1e30,
    "nlp_lower_bound_inf": -1e30,
})
```

**Agent best practice**

```text id="ot8k96"
Prefer:
  units-rescaled variables with finite bounds O(1) ... O(1e6)

Avoid:
  fake infinity bounds like 1e20, 1e30, 1e100

Use:
  None for truly unbounded variables/constraints
  finite physical bounds for real physical limits
  explicit nlp_*_bound_inf only with documented reason
```

---

## 3.5 Objective contract

### Single active scalar objective

```python id="qp6x9o"
m.obj = pyo.Objective(
    expr=(m.x["A"] - 1.0)**2 + (m.x["B"] - 2.0)**2,
    sense=pyo.minimize,
)
```

### Maximization

```python id="nuwd0o"
m.obj = pyo.Objective(expr=profit_expr, sense=pyo.maximize)
```

Pyomo’s NL writer handles objective sense; avoid using negative `obj_scaling_factor` as a primary modeling construct unless intentionally controlling Ipopt internals. Ipopt’s `obj_scaling_factor` scales the objective internally while reporting the unscaled objective, and a negative value makes Ipopt maximize instead of minimize. ([COIN-OR][6])

### Multiple objectives anti-pattern

```python id="y8j60g"
m.obj1 = pyo.Objective(expr=cost)
m.obj2 = pyo.Objective(expr=emissions)  # BAD if both active
```

Agent remediation:

```python id="kemvnc"
m.obj2.deactivate()

# or scalarize explicitly
m.obj = pyo.Objective(expr=cost + lam * emissions)
```

---

## 3.6 Smoothness contract: twice continuously differentiable `f` and `g`

Ipopt’s model class allows linear/nonlinear and convex/nonconvex functions, but expects objective and constraint functions to be twice continuously differentiable. ([COIN-OR][1])

### Ipopt-safe smooth primitives

```text id="iazhkr"
polynomial expressions
rational expressions with denominator bounded away from 0
exp
log with argument bounded away from 0
sin/cos/tan with valid domains
sqrt with argument bounded away from 0 if derivative required
smooth external functions with valid derivatives
```

### Nonsmooth / discontinuous anti-patterns

```python id="wtu6sc"
# nonsmooth at 0
m.obj = pyo.Objective(expr=abs(m.x))

# nonsmooth max/min
m.c = pyo.Constraint(expr=max(m.x, m.y) <= 10)

# Python branching on Var: invalid symbolic modeling pattern
if pyo.value(m.x) > 0:
    m.c = pyo.Constraint(expr=m.y >= 1)
```

### Smooth approximations

```python id="0l7te2"
eps = 1e-6

smooth_abs_x = pyo.sqrt(m.x**2 + eps)

softplus_x = eps * pyo.log(1 + pyo.exp(m.x / eps))

smooth_max_xy = 0.5 * (
    m.x + m.y + pyo.sqrt((m.x - m.y)**2 + eps)
)
```

### Exact reformulation patterns

```python id="vbfbla"
# |x| in a minimization objective: epigraph
m.t = pyo.Var(bounds=(0, None), initialize=1.0)
m.abs_pos = pyo.Constraint(expr=m.t >= m.x)
m.abs_neg = pyo.Constraint(expr=m.t >= -m.x)
m.obj = pyo.Objective(expr=m.t)
```

**Agent rule**

```text id="3e0jif"
If expression is nonsmooth:
  exact convex epigraph reformulation if compatible
  smooth approximation if local NLP acceptable
  GDP/MIP/MINLP formulation if logic/discreteness essential
  different solver if black-box/nonsmooth objective is primary
```

---

## 3.7 Convex versus nonconvex behavior

### Convex NLP

```text id="17y7ex"
convex objective
convex inequality constraints in compatible direction
affine equality constraints
continuous variables
regularity conditions
```

Ipopt local KKT point is often adequate for convex NLP workflows, but Ipopt itself is not a convexity certifier.

### Nonconvex NLP

```text id="7s4cdk"
nonconvex objective or constraints
multiple local minima possible
initialization-dependent result
KKT point may not be global optimum
multi-start / continuation / domain-specific validation needed
```

Ipopt explicitly supports convex and nonconvex smooth functions in the modeling class, but the documentation describes Ipopt as a local optimizer for nonlinear programming. ([COIN-OR][1])

### Multi-start agent pattern

```python id="bkqugl"
import pyomo.environ as pyo

def solve_from_start(base_model, start):
    m = base_model.clone()
    for comp_name, value in start.items():
        var = getattr(m, comp_name)
        var.set_value(value, skip_validation=True)

    opt = pyo.SolverFactory("ipopt")
    opt.options.update({
        "tol": 1e-8,
        "max_iter": 1000,
        "print_level": 0,
    })
    res = opt.solve(m, tee=False)
    return {
        "model": m,
        "status": res.solver.status,
        "termination_condition": res.solver.termination_condition,
        "objective": pyo.value(m.obj),
    }

starts = [
    {"x": 0.1, "y": 0.1},
    {"x": 1.0, "y": 1.0},
    {"x": 10.0, "y": 10.0},
]

runs = [solve_from_start(m, s) for s in starts]
runs_sorted = sorted(runs, key=lambda r: r["objective"])
```

**Agent language constraint**

```text id="0b2eed"
Say:
  "Ipopt returned a locally optimal/stationary solution."

Do not say:
  "Ipopt proved global optimality."

Unless:
  convexity proof, global solver certificate, or exhaustive global argument exists.
```

---

## 3.8 Feasibility contract and infeasible starting points

### Feasible solution target

```text id="cqsi0b"
variable bounds satisfied:
  x_L <= x <= x_U

constraint bounds satisfied:
  g_L <= g(x) <= g_U

stationarity and complementarity satisfied:
  KKT residuals within tolerances
```

Ipopt’s termination options include `tol`, `dual_inf_tol`, `constr_viol_tol`, and `compl_inf_tol`; successful termination requires scaled NLP error below `tol` and absolute dual infeasibility, constraint/bound violation, and complementarity criteria below their thresholds. ([COIN-OR][6])

### Infeasible start is allowed; undefined start is not

```python id="4krjo8"
# acceptable: constraint-infeasible start
m.x = pyo.Var(bounds=(0, 10), initialize=0.1)
m.y = pyo.Var(bounds=(0, 10), initialize=0.1)
m.c = pyo.Constraint(expr=m.x * m.y >= 5.0)

# unacceptable: expression undefined at start
m.z = pyo.Var(bounds=(0, None), initialize=0.0)
m.bad = pyo.Constraint(expr=pyo.log(m.z) >= -1.0)
```

Interior-point methods can work from points that violate nonlinear constraints, but function values and derivatives must be evaluable at iterates. Ipopt also modifies initial primal/slack values to be sufficiently inside bounds using options such as `bound_push`, `bound_frac`, `slack_bound_push`, and `slack_bound_frac`. ([COIN-OR][6])

### Initialization best-practice rules

```text id="79r87d"
[ ] initialize every nonlinear variable
[ ] avoid exact variable bound starts when possible
[ ] initialize log/sqrt/division arguments strictly inside domain
[ ] initialize denominators away from zero
[ ] initialize products/exponentials with realistic magnitudes
[ ] provide feasible-ish starts for highly nonlinear equality systems
[ ] use continuation/homotopy for hard nonconvex feasibility
```

### Bound-interior helper

```python id="ig6z3k"
def safe_initial_value(lb, ub, default=1.0, frac=0.1):
    if lb is not None and ub is not None:
        return lb + frac * (ub - lb)
    if lb is not None:
        return lb + max(1.0, abs(lb)) * frac
    if ub is not None:
        return ub - max(1.0, abs(ub)) * frac
    return default
```

---

## 3.9 Restoration phase and local infeasibility

### Restoration semantics

```text id="j0e8lm"
restoration phase:
  feasibility-recovery subproblem
  attempts to reduce constraint violation
  can return locally infeasible point
  useful for diagnosing incompatible constraints
```

Ipopt’s output documentation states that when restoration converges to a minimizer of constraint violation in the `l1` norm but not a feasible point for the original problem, the problem may be infeasible or the algorithm may be stuck at a locally infeasible point; the returned point can help identify problematic constraints. ([COIN-OR][7])

### Agent interpretation

```text id="n6fmbg"
Infeasible_Problem_Detected:
  not always formal global infeasibility certificate
  often local infeasibility / restoration-phase failure signal
  diagnose constraints at returned point
  test alternate starts
  check scaling
  check sign conventions
  check impossible bounds
```

### Feasibility diagnostics in Pyomo

```python id="15w4gc"
import pyomo.environ as pyo

def constraint_residuals(model, tol=1e-7):
    rows = []
    for c in model.component_data_objects(pyo.Constraint, active=True):
        body = pyo.value(c.body, exception=False)
        lb = pyo.value(c.lower, exception=False) if c.lower is not None else None
        ub = pyo.value(c.upper, exception=False) if c.upper is not None else None

        if body is None:
            rows.append((c.name, "body_eval_failed", None, lb, ub, None))
            continue

        lower_violation = 0.0 if lb is None else max(0.0, lb - body)
        upper_violation = 0.0 if ub is None else max(0.0, body - ub)
        violation = max(lower_violation, upper_violation)

        if violation > tol:
            rows.append((c.name, "violated", body, lb, ub, violation))

    return sorted(rows, key=lambda r: r[-1] or 0.0, reverse=True)

for row in constraint_residuals(m):
    print(row)
```

### Bound diagnostics in Pyomo

```python id="su4jnr"
def variable_bound_residuals(model, tol=1e-7):
    rows = []
    for v in model.component_data_objects(pyo.Var, active=True):
        val = pyo.value(v, exception=False)
        if val is None:
            rows.append((v.name, "no_value", None, v.lb, v.ub, None))
            continue

        lb = pyo.value(v.lb, exception=False) if v.lb is not None else None
        ub = pyo.value(v.ub, exception=False) if v.ub is not None else None

        lower_violation = 0.0 if lb is None else max(0.0, lb - val)
        upper_violation = 0.0 if ub is None else max(0.0, val - ub)
        violation = max(lower_violation, upper_violation)

        if violation > tol:
            rows.append((v.name, "bound_violated", val, lb, ub, violation))

    return sorted(rows, key=lambda r: r[-1] or 0.0, reverse=True)
```

---

## 3.10 Constraint violation output: original versus internal

```python id="yqxmnf"
opt.options["inf_pr_output"] = "original"
```

Ipopt’s `inf_pr_output` controls what appears in the `inf_pr` column: `original` prints the maximal constraint violation in the original NLP, while `internal` prints violation in Ipopt’s reformulated/scaled internal equality system; the default is `original`. ([COIN-OR][6])

**Agent rule**

```text id="09385g"
When debugging model feasibility:
  use inf_pr_output=original
  inspect returned Pyomo constraint residuals
  do not rely only on internal infeasibility measures
```

---

## 3.11 Scaling contract: units, magnitudes, derivatives, residuals

### Scaling failure signatures

```text id="sf4to7"
objective magnitude:          1e12
constraint residual target:   1e-8
variable x in Pa:             1e6
variable y in kmol/s:         1e-5
Jacobian columns:             mixed 1e-12 to 1e12
Hessian regularization:       frequent
tiny step / restoration:      recurrent
dual infeasibility:           stuck
```

Ipopt’s `nlp_scaling_method` default is `gradient-based`; it can also be `none`, `user-scaling`, or `equilibration-based`, with gradient-based scaling attempting to scale the problem so the maximum gradient at the starting point equals `nlp_scaling_max_gradient`. ([COIN-OR][6])

### Recommended model-scale targets

```text id="rmlpwo"
variables at solution:           O(1) to O(1e3)
constraint body magnitudes:      O(1) to O(1e3)
active constraint residuals:     meaningful under constr_viol_tol
objective magnitude:             O(1) to O(1e6), unless intentionally large
Jacobian nonzeros:               avoid extreme >1e8 or <1e-8 where practical
physical units:                  rescale before algebra, not after failure
```

### Manual nondimensionalization pattern

Bad:

```python id="co1ply"
# Pressure in Pa, flow in mol/s, energy in J: large mixed scales.
m.P = pyo.Var(bounds=(1e5, 1e7), initialize=1e6)
m.F = pyo.Var(bounds=(1e-6, 1e-2), initialize=1e-4)
m.E = pyo.Var(bounds=(0, 1e9), initialize=1e6)
```

Better:

```python id="vxhe98"
# Dimensionless / scaled variables.
P_ref = 1e6
F_ref = 1e-4
E_ref = 1e6

m.P_hat = pyo.Var(bounds=(0.1, 10.0), initialize=1.0)
m.F_hat = pyo.Var(bounds=(0.01, 100.0), initialize=1.0)
m.E_hat = pyo.Var(bounds=(0.0, 1000.0), initialize=1.0)

P = P_ref * m.P_hat
F = F_ref * m.F_hat
E = E_ref * m.E_hat
```

### Ipopt automatic scaling options

```python id="smhr0z"
opt.options.update({
    "nlp_scaling_method": "gradient-based",
    "nlp_scaling_max_gradient": 100.0,
})
```

Alternative:

```python id="8z5flk"
opt.options["nlp_scaling_method"] = "none"
```

Alternative with user scaling:

```python id="mrerfk"
m.scaling_factor = pyo.Suffix(direction=pyo.Suffix.EXPORT)

m.scaling_factor[m.x] = 0.01
m.scaling_factor[m.c] = 100.0

opt.options["nlp_scaling_method"] = "user-scaling"
```

Ipopt’s scaling options include `nlp_scaling_method`, `obj_scaling_factor`, `nlp_scaling_max_gradient`, target objective/constraint gradient options, and `nlp_scaling_min_value`; user scaling can be supplied from the NLP via `scaling_factor` suffixes in AMPL-style interfaces. ([COIN-OR][6])

### Scaling anti-patterns

```text id="qeojxa"
BAD:
  use 1e20 as fake upper bound
  use raw SI units blindly in all variables
  combine cost term 1e9 with penalty term 1e-6
  set tol=1e-12 on poorly scaled model
  interpret scaled convergence as physical accuracy without checking unscaled residuals
  disable scaling as first troubleshooting step without residual analysis

GOOD:
  nondimensionalize variables
  scale constraints by expected body magnitude
  keep finite bounds physically tight
  set tolerances consistent with units and data accuracy
  compare solver residuals to domain-specific feasibility thresholds
```

---

## 3.12 Bound relaxation and fixed variables

Ipopt’s `constr_viol_tol` applies to constraint and variable-bound violation, and the option reference states that if `bound_relax_factor` is nonzero, Ipopt relaxes variable bounds with the absolute amount restricted by `constr_viol_tol`. ([COIN-OR][6])

### Fixed variable syntax

```python id="1sh5ho"
m.x.fix(3.0)
```

Equivalent bound form:

```python id="nhoqeg"
m.x.setlb(3.0)
m.x.setub(3.0)
```

### Ipopt fixed-variable treatment options

```python id="wiy6da"
opt.options["fixed_variable_treatment"] = "make_parameter"
```

Ipopt’s option reference says `fixed_variable_treatment` controls how fixed variables are handled, with choices including removing fixed variables from the optimization variables, adding equality constraints, or relaxing fixing bound constraints. ([COIN-OR][6])

**Agent guidance**

```text id="ly1qms"
default fixed_variable_treatment=make_parameter:
  usually good for fixed design variables

need multipliers for fixed variables:
  inspect make_constraint / make_parameter_nodual behavior

debugging bound relaxation:
  check bound_relax_factor
  check constr_viol_tol
  evaluate final variable bound residuals manually
```

---

## 3.13 Model-contract validation helper

```python id="rcrymc"
import math
import pyomo.environ as pyo


def validate_ipopt_contract(model, *, require_initial_values=True):
    errors = []
    warnings = []

    objectives = list(model.component_data_objects(pyo.Objective, active=True))
    if len(objectives) != 1:
        errors.append(f"Expected exactly one active Objective; found {len(objectives)}.")

    for v in model.component_data_objects(pyo.Var, active=True):
        if v.is_binary() or v.is_integer():
            errors.append(f"Discrete variable not valid for Ipopt NLP: {v.name}")

        if require_initial_values and (not v.fixed) and v.value is None:
            warnings.append(f"No initial value for nonlinear solve variable: {v.name}")

        val = pyo.value(v, exception=False)
        if val is not None and not math.isfinite(float(val)):
            errors.append(f"Nonfinite initial value: {v.name}={val}")

        lb = pyo.value(v.lb, exception=False) if v.lb is not None else None
        ub = pyo.value(v.ub, exception=False) if v.ub is not None else None

        if lb is not None and ub is not None and lb > ub:
            errors.append(f"Inconsistent variable bounds: {v.name}: lb={lb}, ub={ub}")

        if ub is not None and abs(ub) >= 1e19:
            warnings.append(f"Upper bound may be treated as Ipopt +inf: {v.name}: ub={ub}")

        if lb is not None and abs(lb) >= 1e19:
            warnings.append(f"Lower bound may be treated as Ipopt -inf: {v.name}: lb={lb}")

    for c in model.component_data_objects(pyo.Constraint, active=True):
        lb = pyo.value(c.lower, exception=False) if c.lower is not None else None
        ub = pyo.value(c.upper, exception=False) if c.upper is not None else None

        if lb is not None and ub is not None and lb > ub:
            errors.append(f"Inconsistent constraint bounds: {c.name}: lb={lb}, ub={ub}")

        if ub is not None and abs(ub) >= 1e19:
            warnings.append(f"Constraint upper bound may be treated as Ipopt +inf: {c.name}: ub={ub}")

        if lb is not None and abs(lb) >= 1e19:
            warnings.append(f"Constraint lower bound may be treated as Ipopt -inf: {c.name}: lb={lb}")

        body = pyo.value(c.body, exception=False)
        if body is None:
            warnings.append(f"Constraint body not evaluable at current start: {c.name}")

    return errors, warnings


errors, warnings = validate_ipopt_contract(m)
for msg in warnings:
    print("WARNING:", msg)
for msg in errors:
    print("ERROR:", msg)

if errors:
    raise RuntimeError("Model violates basic Ipopt NLP contract.")
```

---

## 3.14 Agent modeling decision table

| Modeling construct                         |                      Ipopt status | Correct agent action                               |
| ------------------------------------------ | --------------------------------: | -------------------------------------------------- |
| Continuous `Var(bounds=(lb, ub))`          |                            native | use directly                                       |
| Free continuous `Var(bounds=(None, None))` | native but risky if poorly scaled | initialize and scale                               |
| Equality `expr == rhs`                     |                            native | maps to `gL == gU`                                 |
| Upper inequality `expr <= ub`              |                            native | maps to `gU` finite                                |
| Lower inequality `expr >= lb`              |                            native | maps to `gL` finite                                |
| Ranged inequality `lb <= expr <= ub`       |                            native | use `pyo.inequality` or tuple rule                 |
| Binary/integer variable                    |                    not native NLP | relax, fix, reformulate, or use MINLP/MIP solver   |
| `abs`, `max`, `min`                        |                         nonsmooth | reformulate or smooth                              |
| `log(x)`                                   |           smooth only for `x > 0` | enforce positive lower bound and positive start    |
| `sqrt(x)`                                  |      derivative singular at `x=0` | lower-bound away from zero or reformulate          |
| huge fake bound `1e20`                     |         may become Ipopt infinity | use `None`, rescale, or adjust `nlp_*_bound_inf`   |
| infeasible start                           |              allowed if evaluable | provide robust initialization; inspect restoration |
| undefined start                            |                           invalid | fix initialization/domain before solve             |
| nonconvex smooth NLP                       |                       local solve | multi-start / continuation / validate locally      |

---

## 3.15 Minimal robust Pyomo + Ipopt NLP skeleton

```python id="wa8s3w"
import pyomo.environ as pyo

m = pyo.ConcreteModel()

# Scaled continuous variables
m.x = pyo.Var(bounds=(0.01, 100.0), initialize=1.0)
m.y = pyo.Var(bounds=(0.01, 100.0), initialize=2.0)

# Smooth objective
m.obj = pyo.Objective(expr=(m.x - 3.0)**2 + (m.y - 4.0)**2)

# Smooth equality
m.mass_balance = pyo.Constraint(expr=m.x * m.y == 12.0)

# Smooth upper inequality
m.capacity = pyo.Constraint(expr=m.x**2 + m.y**2 <= 100.0)

# Smooth ranged inequality
m.operating_window = pyo.Constraint(expr=pyo.inequality(1.0, m.x + m.y, 20.0))

opt = pyo.SolverFactory("ipopt")
opt.options.update({
    "tol": 1e-8,
    "constr_viol_tol": 1e-6,
    "max_iter": 1000,
    "nlp_scaling_method": "gradient-based",
    "inf_pr_output": "original",
    "print_user_options": "yes",
})

results = opt.solve(m, tee=True)
print(results.solver.status)
print(results.solver.termination_condition)
print(pyo.value(m.obj), pyo.value(m.x), pyo.value(m.y))
```

---

## 3.16 Final contract checklist

```text id="m6d5fk"
[ ] Exactly one active scalar objective.
[ ] All Ipopt decision variables continuous.
[ ] Every nonlinear variable initialized.
[ ] Variable bounds physically meaningful, not fake infinity.
[ ] Constraint bounds consistent: lower <= upper.
[ ] Equality constraints represented by identical lower/upper target.
[ ] Infinite bounds represented by None in Pyomo, not arbitrary huge constants.
[ ] Expressions twice continuously differentiable on the region Ipopt may visit.
[ ] log/sqrt/division domains protected by bounds and starts.
[ ] Nonsmooth max/min/abs/if-else reformulated or smoothed.
[ ] Nonconvexity acknowledged as local optimization.
[ ] Infeasible starts allowed only if all functions evaluate safely.
[ ] Restoration/local infeasibility treated as diagnostic, not always proof.
[ ] Scaling reviewed before tightening tolerances.
[ ] `inf_pr_output=original` used for feasibility debugging.
[ ] Large physical units nondimensionalized or explicitly scaled.
```

[1]: https://coin-or.github.io/Ipopt/ "Ipopt: Documentation"
[2]: https://coin-or.github.io/Ipopt/classIpopt_1_1TNLP.html "Ipopt: Ipopt::TNLP Class Reference"
[3]: https://pyomo.readthedocs.io/en/6.9.0/api/pyomo.core.base.var.Var.html "Var — Pyomo 6.9.0 documentation"
[4]: https://pyomo.readthedocs.io/en/6.9.2/explanation/modeling/math_programming/constraints.html "Constraints — Pyomo 6.9.2 documentation"
[5]: https://pyomo.readthedocs.io/en/6.6.2/library_reference/kernel/constraint.html "Constraints — Pyomo 6.6.2 documentation"
[6]: https://coin-or.github.io/Ipopt/OPTIONS.html "Ipopt: Ipopt Options"
[7]: https://coin-or.github.io/Ipopt/OUTPUT.html "Ipopt: Ipopt Output"

# Ipopt Advanced — Section 4: algorithmic control surface

Style target: dense advanced technical catalog / agent-ready implementation reference. 

## 4.0 Control-surface invariant

```text id="l2wxpq"
Ipopt algorithmic control surface =
  barrier parameter policy
  line-search / filter globalization
  step computation / KKT linear solve behavior
  restoration-phase behavior
  termination thresholds
  diagnostic output interpretation
```

Ipopt implements an **interior-point line-search filter method** for smooth NLPs and targets a local solution; the main user-facing algorithm controls are Ipopt options, passed through Pyomo’s solver options, an `ipopt.opt` file, or direct executable options. Ipopt options are string-named values of type Number, Integer, or String, and `ipopt.opt` lines use `option_name value` syntax with `#` comments. ([COIN-OR][1])

---

## 4.1 Option deployment syntax: Pyomo, solve-local, `ipopt.opt`

### Persistent Pyomo options

```python id="t4ta8w"
import pyomo.environ as pyo

opt = pyo.SolverFactory("ipopt")
opt.options.update({
    "tol": 1e-8,
    "max_iter": 1000,
    "mu_strategy": "adaptive",
    "linear_solver": "mumps",
    "print_level": 5,
})

results = opt.solve(model, tee=True)
```

Pyomo solver options can be attached to the solver object through `optimizer.options[...]`; these options persist across solves until deleted or overwritten. `tee=True` is Pyomo-level log streaming, not an Ipopt option. ([Pyomo Documentation][2])

### Solve-local temporary options

```python id="nad72u"
results = opt.solve(
    model,
    tee=True,
    options={
        "tol": 1e-7,
        "acceptable_tol": 1e-5,
        "max_wall_time": 300.0,
    },
)
```

Pyomo’s `solve(..., options={...})` passes options only for that solve and temporarily overrides matching persistent solver-object options. ([Pyomo Documentation][2])

### `ipopt.opt`

```text id="sq51bn"
# ipopt.opt
tol 1e-8
acceptable_tol 1e-6
mu_strategy adaptive
max_iter 1000
print_user_options yes
```

Ipopt reads `ipopt.opt` line-by-line as option name plus whitespace plus value, and the Ipopt docs explicitly show examples such as `nlp_scaling_method none`, `mu_init 1e-2`, and `max_iter 500`. ([COIN-OR][3])

---

## 4.2 Barrier method control: `mu_*`

### Barrier-parameter mental model

```text id="1vbk98"
mu = barrier parameter
large mu  -> centrality / interior behavior emphasized
small mu  -> complementarity target tightened
lg(mu)    -> log10(mu), printed in Ipopt iteration table
```

Ipopt’s output table includes `lg(mu)`, defined as `log10` of the barrier parameter. The same table also reports primal/dual infeasibility, step norms, and step acceptance diagnostics, so `lg(mu)` should be interpreted together with `inf_pr`, `inf_du`, `alpha_pr`, and `ls`. ([COIN-OR][4])

### Primary options

```python id="xe19ek"
opt.options.update({
    "mu_strategy": "monotone",  # default
    "mu_init": 1e-1,
})
```

```python id="oh3wz6"
opt.options.update({
    "mu_strategy": "adaptive",
    "mu_oracle": "quality-function",
    "mu_min": 1e-11,
})
```

| Option                          |   Type | Primary use                                              | Default / behavior                                                        |
| ------------------------------- | -----: | -------------------------------------------------------- | ------------------------------------------------------------------------- |
| `mu_strategy`                   | String | choose barrier update mode                               | `monotone`; choices `monotone`, `adaptive`                                |
| `mu_init`                       | Number | initial barrier parameter in monotone mode               | default `0.1`; relevant for monotone Fiacco-McCormick mode                |
| `mu_oracle`                     | String | adaptive free-mode `mu` proposal                         | default `quality-function`; choices `probing`, `loqo`, `quality-function` |
| `fixed_mu_oracle`               | String | first `mu` when adaptive switches to monotone mode       | default `average_compl`                                                   |
| `mu_min`                        | Number | lower bound on `mu` in adaptive mode                     | default around `1e-11` / formula involving `tol` and `compl_inf_tol`      |
| `barrier_tol_factor`            | Number | per-barrier subproblem tolerance factor in monotone mode | default `10`                                                              |
| `mu_linear_decrease_factor`     | Number | linear decrease factor in monotone update                | default `0.2`                                                             |
| `mu_superlinear_decrease_power` | Number | superlinear decrease power in monotone update            | default `1.5`                                                             |

Ipopt documents `mu_strategy=monotone|adaptive`, `mu_oracle` choices for adaptive mode, `mu_init` relevance to monotone mode, and monotone decrease controls such as `barrier_tol_factor`, `mu_linear_decrease_factor`, and `mu_superlinear_decrease_power`. ([COIN-OR][3])

### `monotone` versus `adaptive`

```text id="qxvboy"
mu_strategy=monotone:
  conservative Fiacco-McCormick-style barrier sequence
  uses mu_init directly
  often stable default
  simpler diagnostics

mu_strategy=adaptive:
  free-mode barrier updates via mu_oracle
  may reduce mu more aggressively
  can switch to monotone mode for globalization
  introduces adaptive_mu_* controls
```

For adaptive mode, Ipopt uses globalization logic that can switch to monotone mode when convergence appears insufficient; options include `adaptive_mu_globalization`, `adaptive_mu_restore_previous_iterate`, and `adaptive_mu_monotone_init_factor`. ([COIN-OR][3])

### Agent defaults

```python id="ctar3v"
# Stable baseline: leave barrier policy mostly default.
opt.options.update({
    "mu_strategy": "monotone",
    "tol": 1e-8,
})
```

```python id="fjqofh"
# Common performance experiment: adaptive barrier.
opt.options.update({
    "mu_strategy": "adaptive",
    "mu_oracle": "quality-function",
    "tol": 1e-8,
})
```

**Agent rule:** tune `mu_strategy` before tuning advanced `adaptive_mu_*` internals. Treat `adaptive_mu_*`, `quality_function_*`, `sigma_*`, and `tau_min` as expert-level controls unless the failure mode clearly points to barrier progression.

---

## 4.3 Line search and filter method controls

### Globalization mental model

```text id="t651y8"
Ipopt step proposal:
  solve sparse KKT system
  compute primal/dual search direction
  backtracking line search
  filter or penalty acceptor decides trial point
  restoration phase if acceptable progress cannot be found
```

Ipopt’s default line-search globalization method is `filter`; the docs state that only the `filter` choice is officially supported, while `cg-penalty` and `penalty` are alternatives that may sometimes work. ([COIN-OR][3])

### Core line-search options

```python id="1tcb22"
opt.options.update({
    "line_search_method": "filter",
    "alpha_red_factor": 0.5,
})
```

| Option                            | Meaning                                         | Default / caution                                                                 |
| --------------------------------- | ----------------------------------------------- | --------------------------------------------------------------------------------- |
| `line_search_method`              | globalization method in backtracking search     | default `filter`; only `filter` officially supported                              |
| `alpha_red_factor`                | step-size shrink factor in backtracking         | default `0.5`                                                                     |
| `accept_every_trial_step`         | accept first trial step                         | default `no`; `yes` disables line search and removes global convergence guarantee |
| `accept_after_max_steps`          | force accept after N backtracks                 | default `-1`; advanced escape hatch                                               |
| `watchdog_shortened_iter_trigger` | trigger watchdog after repeated shortened steps | default `10`; `0` disables watchdog                                               |
| `watchdog_trial_iter_max`         | maximum watchdog trial iterations               | default `3`                                                                       |

`accept_every_trial_step=yes` effectively disables line search and makes Ipopt take aggressive steps without global convergence guarantees, so agents should not use it as a generic speed option. ([COIN-OR][3])

### Filter-specific advanced options

```python id="i7g9ht"
# Expert-only: rarely needed in generated application code.
opt.options.update({
    "theta_max_fact": 1e4,
    "theta_min_fact": 1e-4,
    "gamma_phi": 1e-8,
    "gamma_theta": 1e-5,
})
```

| Option                           | Role                                                     |
| -------------------------------- | -------------------------------------------------------- |
| `theta_max_fact`                 | upper bound for constraint violation in filter           |
| `theta_min_fact`                 | switching threshold between h-type and f-type iterations |
| `eta_phi`                        | Armijo relaxation factor                                 |
| `delta`                          | constraint-violation multiplier in switching rule        |
| `s_phi`, `s_theta`               | exponents in switching rule                              |
| `gamma_phi`, `gamma_theta`       | filter-margin relaxation factors                         |
| `constraint_violation_norm_type` | norm used for line-search constraint violation           |

Ipopt documents these as advanced line-search/filter controls; `theta_max_fact` sets the filter’s upper constraint-violation bound, and `theta_min_fact` influences h-type versus f-type switching. ([COIN-OR][3])

### Output tags: filter versus penalty interpretation

```text id="6sarpa"
alpha_pr suffix:
  f  filter f-type, no SOC
  F  filter f-type, with SOC
  h  filter h-type, no SOC
  H  filter h-type, with SOC
  k  penalty unchanged, no SOC
  K  penalty unchanged, with SOC
  n  penalty updated, no SOC
  N  penalty updated, with SOC
  R  restoration phase just started
  w  watchdog procedure
  s/S soft restoration accepted
  t/T tiny step accepted
  r  previous iterate restored
```

Ipopt’s output documentation defines the `alpha_pr` diagnostic suffixes and notes that the printed objective and `inf_pr` may worsen even when the internal step-acceptance mechanism is satisfied, because globalization uses the barrier objective and internal scaled/slack reformulation rather than exactly the printed columns. ([COIN-OR][4])

---

## 4.4 Restoration phase controls

### Restoration mental model

```text id="69rqg3"
Restoration phase =
  feasibility recovery mode
  invoked when line search/filter cannot find acceptable progress
  solves auxiliary restoration problem
  may return locally infeasible point
  may fail if derivatives/model/constraint qualification are poor
```

Ipopt iteration numbers get an appended `r` in restoration phase, and `alpha_pr` tag `R` marks restoration phase start. `Restoration_Failed` means the restoration phase failed to find a feasible point acceptable to the original filter line search; Ipopt lists degeneracy, constraint-qualification failure, or incorrect derivatives as possible causes. ([COIN-OR][4])

### Restoration options

```python id="drby52"
opt.options.update({
    "expect_infeasible_problem": "no",
    "required_infeasibility_reduction": 0.9,
    "max_resto_iter": 3000000,
})
```

| Option                                | Meaning                                                                     | Agent use                                                  |
| ------------------------------------- | --------------------------------------------------------------------------- | ---------------------------------------------------------- |
| `expect_infeasible_problem`           | activate heuristics for suspected infeasible problems                       | use for feasibility-diagnosis runs, not default production |
| `expect_infeasible_problem_ctol`      | disables infeasible heuristics below constraint-violation threshold         | tune only in infeasibility workflows                       |
| `expect_infeasible_problem_ytol`      | multiplier threshold for entering restoration under infeasibility heuristic | expert                                                     |
| `start_with_resto`                    | enter restoration at first iteration                                        | diagnostic only; fails if initial point is feasible        |
| `soft_resto_pderror_reduction_factor` | required primal-dual error reduction in soft restoration                    | advanced                                                   |
| `max_soft_resto_iters`                | maximum consecutive soft-restoration iterations                             | advanced                                                   |
| `required_infeasibility_reduction`    | required infeasibility reduction before leaving restoration                 | useful for infeasibility diagnosis                         |
| `max_resto_iter`                      | maximum successive restoration iterations                                   | safety bound                                               |
| `evaluate_orig_obj_at_resto_trial`    | evaluate original objective at restoration trial points                     | default `yes`; helps catch objective evaluation failures   |

Ipopt documents `expect_infeasible_problem` as a heuristic to enter restoration more quickly and require more constraint-violation reduction when infeasibility is expected; `required_infeasibility_reduction` controls how much infeasibility must be reduced before leaving restoration. ([COIN-OR][3])

### Infeasibility diagnostic bundle

```python id="fv2bql"
opt.options.update({
    "expect_infeasible_problem": "yes",
    "required_infeasibility_reduction": 0.99,
    "max_resto_iter": 5000,
    "print_level": 7,
    "inf_pr_output": "original",
})
```

Use when:

```text id="d3hmh4"
model suspected infeasible
restoration entered repeatedly
large constraint violations persist
need returned locally infeasible point for constraint triage
```

Do not use as a generic convergence accelerator.

---

## 4.5 Step calculation: primal/dual steps, SOC, KKT solve, multiplier steps

### KKT step computation

```text id="59ij9t"
At each major iteration:
  build derivative information
  solve sparse augmented KKT linear system
  compute primal step dx and slack step ds
  compute dual/bound multiplier steps
  optionally apply second-order correction
  line search accepts/rejects trial step
```

Ipopt’s `linear_solver` option selects the sparse linear algebra package used to solve the augmented linear system for search directions; possible documented values include HSL solvers, Pardiso variants, SPRAL, WSMP, MUMPS, and custom. Actual availability is build-dependent. ([COIN-OR][3])

### Linear-solver step options

```python id="z0y0nd"
opt.options.update({
    "linear_solver": "mumps",
    "min_refinement_steps": 1,
    "max_refinement_steps": 10,
})
```

| Option                     | Meaning                                                |
| -------------------------- | ------------------------------------------------------ |
| `linear_solver`            | sparse linear solver for augmented KKT system          |
| `fast_step_computation`    | skip residual verification for faster step computation |
| `min_refinement_steps`     | enforce minimum iterative refinement steps             |
| `max_refinement_steps`     | cap iterative refinement                               |
| `linear_system_scaling`    | symmetric scaling of augmented system                  |
| `linear_scaling_on_demand` | only scale linear system if needed                     |

Ipopt documents `fast_step_computation=no` by default; setting it to `yes` assumes the linear system has been solved well enough and skips residual checks, so it is a performance-risk option rather than a safe default. ([COIN-OR][3])

### Constraint multiplier step: `alpha_for_y`

```python id="usygqr"
opt.options.update({
    "alpha_for_y": "primal",   # default
})
```

Choices include:

```text id="it362n"
primal
bound-mult
min
max
full
min-dual-infeas
safer-min-dual-infeas
primal-and-full
dual-and-full
acceptor
```

`alpha_for_y` controls the step size for equality constraint multipliers; the default is `primal`, while alternatives such as `full`, `min-dual-infeas`, and safeguarded variants can materially change dual update behavior. ([COIN-OR][3])

### Second-order correction

```python id="c3dg91"
opt.options.update({
    "max_soc": 4,       # default
    "kappa_soc": 0.99,
})
```

| Option      | Meaning                                                             |
| ----------- | ------------------------------------------------------------------- |
| `max_soc`   | maximum number of second-order correction trial steps per iteration |
| `kappa_soc` | required constraint-violation reduction for more SOC attempts       |

`max_soc=0` disables second-order corrections; the default is `4`. Ipopt’s output marks second-order correction in the `alpha_pr` tag by uppercase `F`, `H`, `K`, or `N`. ([COIN-OR][3])

### Tiny-step behavior

```python id="9zslna"
# Usually leave defaults.
opt.options.update({
    "tiny_step_tol": 2.22045e-15,
    "tiny_step_y_tol": 0.01,
})
```

Ipopt accepts a full step without line search when primal search directions are numerically insignificant under `tiny_step_tol`; repeated tiny steps plus small multiplier steps can lead to tiny-step termination. ([COIN-OR][3])

### Mehrotra algorithm caution

```python id="zf5bqh"
# Expert / LP-QP-like experiment only.
opt.options["mehrotra_algorithm"] = "yes"
```

`mehrotra_algorithm=yes` disables line search, selects unglobalized adaptive `mu` with probing oracle, uses affine corrector behavior without safeguards, and is documented as usually useful for LPs and convex QPs; agents should not enable it for general nonlinear Pyomo models. ([COIN-OR][3])

---

## 4.6 Termination tests: desired convergence

### Desired termination bundle

```python id="lkh0ey"
opt.options.update({
    "tol": 1e-8,
    "dual_inf_tol": 1.0,
    "constr_viol_tol": 1e-4,
    "compl_inf_tol": 1e-4,
    "max_iter": 3000,
})
```

| Option            | Meaning                                                    |            Default |
| ----------------- | ---------------------------------------------------------- | -----------------: |
| `tol`             | desired relative/scaled NLP error tolerance                |             `1e-8` |
| `dual_inf_tol`    | absolute unscaled dual infeasibility threshold             |                `1` |
| `constr_viol_tol` | absolute unscaled constraint and bound violation threshold |             `1e-4` |
| `compl_inf_tol`   | absolute unscaled complementarity threshold                |             `1e-4` |
| `max_iter`        | maximum iterations                                         |             `3000` |
| `max_wall_time`   | wall-clock limit, checked during convergence checks        | very large default |
| `max_cpu_time`    | CPU-time limit, checked during convergence checks          | very large default |

Ipopt terminates successfully at desired tolerance only when the scaled NLP error is below `tol` and the absolute criteria `dual_inf_tol`, `constr_viol_tol`, and `compl_inf_tol` are also satisfied; `constr_viol_tol` applies to constraint and variable-bound violation and also restricts bound relaxation when `bound_relax_factor` is nonzero. ([COIN-OR][3])

### Strict high-accuracy solve

```python id="pjp07s"
opt.options.update({
    "tol": 1e-10,
    "dual_inf_tol": 1e-8,
    "constr_viol_tol": 1e-8,
    "compl_inf_tol": 1e-8,
    "max_iter": 5000,
})
```

Use only when:

```text id="ug0rfg"
model scaled well
derivatives correct
linear solver robust
data accuracy justifies tolerance
solution sensitivity requires tight KKT residuals
```

### Practical engineering solve

```python id="m9o1w8"
opt.options.update({
    "tol": 1e-7,
    "constr_viol_tol": 1e-6,
    "compl_inf_tol": 1e-6,
    "acceptable_tol": 1e-5,
    "acceptable_constr_viol_tol": 1e-5,
    "acceptable_compl_inf_tol": 1e-5,
    "max_iter": 1000,
})
```

Use when:

```text id="f1k7c4"
engineering accuracy sufficient
data uncertain
model moderately scaled
nonconvex solve might stall near best attainable point
```

---

## 4.7 Acceptable convergence: secondary stopping criterion

### Acceptable termination semantics

```text id="hcyiv3"
desired convergence:
  tol + dual_inf_tol + constr_viol_tol + compl_inf_tol satisfied
  exit message: Optimal Solution Found

acceptable convergence:
  acceptable_tol + acceptable_* thresholds satisfied for acceptable_iter consecutive iterations
  exit message: Solved To Acceptable Level
```

Ipopt has two levels of termination criteria: desired tolerances trigger immediate success; if `acceptable_iter` consecutive iterates satisfy the acceptable criteria, Ipopt terminates before desired convergence, useful when desired accuracy is not achievable for the problem. ([COIN-OR][3])

### Acceptable options

```python id="e7xuqx"
opt.options.update({
    "acceptable_tol": 1e-6,
    "acceptable_iter": 15,
    "acceptable_dual_inf_tol": 1e10,
    "acceptable_constr_viol_tol": 1e-2,
    "acceptable_compl_inf_tol": 1e-2,
    "acceptable_obj_change_tol": 1e20,
})
```

| Option                       | Meaning                                         |       Default |
| ---------------------------- | ----------------------------------------------- | ------------: |
| `acceptable_tol`             | acceptable scaled overall optimality error      |        `1e-6` |
| `acceptable_iter`            | consecutive acceptable iterates before stopping |          `15` |
| `acceptable_dual_inf_tol`    | acceptable dual infeasibility threshold         |        `1e10` |
| `acceptable_constr_viol_tol` | acceptable constraint violation threshold       |        `1e-2` |
| `acceptable_compl_inf_tol`   | acceptable complementarity threshold            |        `1e-2` |
| `acceptable_obj_change_tol`  | acceptable objective-change criterion           | large default |

`acceptable_obj_change_tol` can be useful with quasi-Newton / limited-memory Hessian settings when dual infeasibility is hard to reduce, because it can satisfy part of acceptable termination via small relative objective change. ([COIN-OR][3])

### Disable acceptable termination

```python id="ei0lp4"
opt.options["acceptable_iter"] = 0
```

Use when:

```text id="llk5bu"
strict benchmark
regression test requiring desired termination only
KKT residual contract cannot accept secondary tolerance
```

### Make acceptable termination operationally explicit

```python id="08uesf"
from pyomo.opt import TerminationCondition

res = opt.solve(model, tee=True, load_solutions=False)

tc = res.solver.termination_condition
if tc == TerminationCondition.optimal:
    model.solutions.load_from(res)
elif str(tc).lower() in {"locallyoptimal", "optimal"}:
    model.solutions.load_from(res)
elif "acceptable" in str(res.solver).lower():
    # optional policy: load but flag degraded convergence
    model.solutions.load_from(res)
else:
    raise RuntimeError(f"Ipopt did not meet required termination policy: {tc}")
```

Pyomo exposes solver status and termination condition through the result object, and Pyomo’s recipes show checking `results.solver.status` and `results.solver.termination_condition` before loading or trusting a solution. ([Pyomo Documentation][2])

---

## 4.8 Time and iteration limits

### Hard iteration/time cap

```python id="ycmc9h"
opt.options.update({
    "max_iter": 500,
    "max_wall_time": 600.0,
    "max_cpu_time": 600.0,
})
```

`max_iter` stops after an iteration count is exceeded; `max_wall_time` and `max_cpu_time` are checked during convergence checks and terminate with corresponding messages if exceeded. ([COIN-OR][3])

### Agent use cases

```text id="ot8v84"
max_iter:
  deterministic iteration cap
  useful for CI, multi-start, decomposition subproblems

max_wall_time:
  operational wall-clock budget
  useful for services, notebooks, batch jobs

max_cpu_time:
  CPU accounting budget
  may differ from wall time under threading / I/O / scheduling
```

### Subproblem/decomposition profile

```python id="uifb51"
opt.options.update({
    "tol": 1e-6,
    "acceptable_tol": 1e-4,
    "acceptable_iter": 5,
    "max_iter": 200,
    "max_wall_time": 60.0,
    "print_level": 0,
})
```

---

## 4.9 Output interpretation: algorithm-state columns

```text id="v0twb9"
iter      iteration number; r suffix => restoration phase
objective unscaled original objective
inf_pr    unscaled original constraint violation by default
inf_du    scaled dual infeasibility
lg(mu)    log10 barrier parameter
||d||     infinity norm of primal step
lg(rg)    log10 Hessian regularization term; '-' if none
alpha_du  dual step size
alpha_pr  primal step size + diagnostic suffix
ls        number of backtracking line-search steps
```

Ipopt’s output docs define each iteration column and state that the printed objective/constraint violation may worsen at an accepted iterate because step acceptance uses the barrier objective and internal problem formulation, not necessarily the printed objective and `inf_pr`. ([COIN-OR][4])

### Agent log heuristics

```text id="hgnro2"
repeated high ls:
  line search struggling
  check scaling, derivatives, nonsmoothness, bounds

r-suffixed iter:
  restoration phase active
  check feasibility, scaling, derivative validity

lg(rg) large / frequent:
  Hessian/KKT regularization
  check rank deficiency, poor scaling, linear solver

tiny step tags t/T:
  step too small
  check optimality residuals, scaling, degeneracy

R then Restoration_Failed:
  restoration could not find acceptable feasible point
  check infeasibility, constraint qualification, derivatives
```

---

## 4.10 Deployment bundles

### Safe default bundle

```python id="x8v4xo"
opt.options.update({
    "tol": 1e-8,
    "max_iter": 3000,
    "mu_strategy": "monotone",
    "line_search_method": "filter",
    "print_level": 5,
})
```

Value case:

```text id="2tw4j5"
minimal deviation from Ipopt defaults
stable first solve
good diagnostic log
low risk of disabling globalization
```

### Faster exploratory solve

```python id="jr6al2"
opt.options.update({
    "tol": 1e-6,
    "acceptable_tol": 1e-4,
    "acceptable_iter": 5,
    "max_iter": 500,
    "mu_strategy": "adaptive",
    "print_level": 4,
})
```

Value case:

```text id="vmvg7l"
quick model iteration
nonconvex multi-start screening
decomposition subproblem early stopping
```

### Strict final solve

```python id="lvcikd"
opt.options.update({
    "tol": 1e-9,
    "dual_inf_tol": 1e-8,
    "constr_viol_tol": 1e-8,
    "compl_inf_tol": 1e-8,
    "acceptable_iter": 0,
    "max_iter": 5000,
    "print_user_options": "yes",
})
```

Value case:

```text id="dvkluu"
final report
benchmarking
sensitivity analysis
post-optimality checks
```

### Restoration diagnostics

```python id="ql6wjz"
opt.options.update({
    "expect_infeasible_problem": "yes",
    "required_infeasibility_reduction": 0.99,
    "max_resto_iter": 10000,
    "inf_pr_output": "original",
    "print_level": 7,
})
```

Value case:

```text id="e1y9sl"
identify infeasible/locally infeasible model
extract returned point for constraint residual triage
debug badly initialized NLP
```

### Line-search failure debugging

```python id="ha8igx"
opt.options.update({
    "print_level": 7,
    "print_user_options": "yes",
    "line_search_method": "filter",
    "alpha_red_factor": 0.5,
    "watchdog_shortened_iter_trigger": 10,
})
```

Do **not** fix line-search failure by defaulting to `accept_every_trial_step=yes`; Ipopt documents that this disables line search and removes global convergence guarantees. ([COIN-OR][3])

---

## 4.11 Agent anti-patterns

```text id="k9cqzh"
BAD:
  accept_every_trial_step yes
as generic speed tuning.

GOOD:
  leave filter globalization on; fix scaling/derivatives/model domains.

BAD:
  tol 1e-12 on raw badly scaled SI-unit model.

GOOD:
  scale model first; tighten tol only after residual diagnostics.

BAD:
  max_iter 20 then claim infeasible.

GOOD:
  report iteration-limited run as inconclusive.

BAD:
  Solved_To_Acceptable_Level == Optimal Solution Found.

GOOD:
  record acceptable termination as degraded / secondary convergence.

BAD:
  start_with_resto yes for normal solve.

GOOD:
  use start_with_resto only for targeted feasibility diagnostics.

BAD:
  tune theta/gamma/filter internals before checking derivative correctness.

GOOD:
  run derivative test, check scaling, inspect log tags.
```

---

## 4.12 Agent decision table

| Symptom                        | First checks                                    | Candidate controls                                                                    |
| ------------------------------ | ----------------------------------------------- | ------------------------------------------------------------------------------------- |
| many backtracks `ls`           | scaling, nonsmoothness, bad derivatives         | `print_level`, derivative test, maybe `alpha_red_factor` only after model checks      |
| repeated restoration `r`       | infeasibility, bad start, bad derivatives       | `expect_infeasible_problem`, `required_infeasibility_reduction`, residual diagnostics |
| `Restoration_Failed`           | degeneracy, CQ failure, derivative errors       | derivative checker, constraint residuals, alternate starts, scaling                   |
| `Maximum_Iterations_Exceeded`  | convergence trend, residual levels              | raise `max_iter`, loosen `acceptable_tol`, improve scaling/start                      |
| tiny-step termination          | residuals, scaling, degeneracy                  | check `tiny_step_*` only after model diagnostics                                      |
| high `inf_pr` stuck            | infeasible constraints or scaling               | `inf_pr_output=original`, residual report, restoration diagnostics                    |
| high `inf_du` stuck            | stationarity/dual problem, Hessian/linear solve | scaling, Hessian approximation check, linear solver probe                             |
| objective worsens              | not necessarily failure                         | inspect filter/globalization tags and residuals                                       |
| nonconvex inconsistent results | local minima                                    | multi-start, continuation, bound tightening                                           |

---

## 4.13 Minimal algorithm-control scaffold for Pyomo agents

```python id="vtd6cr"
import pyomo.environ as pyo
from pyomo.opt import SolverStatus, TerminationCondition

def make_ipopt_for_nlp(
    *,
    accuracy: str = "engineering",
    time_limit: float | None = None,
    max_iter: int | None = None,
    linear_solver: str | None = "mumps",
):
    opt = pyo.SolverFactory("ipopt")
    if not opt.available(exception_flag=False):
        raise RuntimeError("Ipopt executable unavailable.")

    base = {
        "print_user_options": "yes",
        "line_search_method": "filter",
        "mu_strategy": "monotone",
    }

    profiles = {
        "explore": {
            "tol": 1e-6,
            "acceptable_tol": 1e-4,
            "acceptable_iter": 5,
            "max_iter": 500,
            "print_level": 4,
        },
        "engineering": {
            "tol": 1e-8,
            "acceptable_tol": 1e-6,
            "acceptable_iter": 15,
            "max_iter": 3000,
            "print_level": 5,
        },
        "strict": {
            "tol": 1e-9,
            "dual_inf_tol": 1e-8,
            "constr_viol_tol": 1e-8,
            "compl_inf_tol": 1e-8,
            "acceptable_iter": 0,
            "max_iter": 5000,
            "print_level": 5,
        },
    }

    opt.options.update(base)
    opt.options.update(profiles[accuracy])

    if linear_solver:
        opt.options["linear_solver"] = linear_solver
    if time_limit is not None:
        opt.options["max_wall_time"] = float(time_limit)
    if max_iter is not None:
        opt.options["max_iter"] = int(max_iter)

    return opt


def solve_with_policy(model, *, accuracy="engineering", tee=True):
    opt = make_ipopt_for_nlp(accuracy=accuracy)
    results = opt.solve(model, tee=tee, load_solutions=False)

    status = results.solver.status
    tc = results.solver.termination_condition

    if status == SolverStatus.ok and tc == TerminationCondition.optimal:
        model.solutions.load_from(results)
        return results

    # Policy hook: optionally allow acceptable termination by string/log/status policy.
    raise RuntimeError(f"Ipopt failed required policy: status={status}, termination={tc}")
```

---

## 4.14 Final checklist

```text id="m4r1y8"
[ ] Pass options through opt.options or solve(options={...}) intentionally.
[ ] Keep line_search_method=filter unless expert experiment.
[ ] Do not use accept_every_trial_step as generic acceleration.
[ ] Start with mu_strategy=monotone; test adaptive as benchmark variant.
[ ] Tune mu_init only for monotone barrier experiments or warm-start profiles.
[ ] Interpret lg(mu), inf_pr, inf_du, alpha_pr tag, and ls together.
[ ] Treat restoration as feasibility-recovery mode, not ordinary progress.
[ ] Use expect_infeasible_problem only when infeasibility is plausible.
[ ] Use required_infeasibility_reduction for infeasibility diagnostics.
[ ] Use max_soc=0 only when deliberately disabling second-order correction.
[ ] Treat tol as scaled overall error plus absolute residual gates.
[ ] Tune dual_inf_tol, constr_viol_tol, compl_inf_tol according to physical residual needs.
[ ] Understand acceptable_tol as secondary/degraded convergence.
[ ] Set acceptable_iter=0 when acceptable termination is not allowed.
[ ] Prefer max_wall_time for operational budgets, max_iter for deterministic iteration caps.
[ ] Preserve tee logs for any non-default algorithm tuning.
```

[1]: https://coin-or.github.io/Ipopt/ "Ipopt: Documentation"
[2]: https://pyomo.readthedocs.io/en/latest/howto/solver_recipes.html "Solver Recipes — Pyomo 6.10.1.dev0 documentation"
[3]: https://coin-or.github.io/Ipopt/OPTIONS.html "Ipopt: Ipopt Options"
[4]: https://coin-or.github.io/Ipopt/OUTPUT.html "Ipopt: Ipopt Output"

# Ipopt Advanced — Section 5: option syntax and option deployment

Style target: dense advanced technical catalog / agent-ready reference. 

## 5.0 Option-system invariant

```text id="e2jqf2"
Ipopt option = string key + typed scalar value

value type ∈ {
  Number   # real-valued scalar: tolerances, times, perturbations, thresholds
  Integer  # integral scalar: iteration limits, print levels, counters
  String   # enumerated strings, yes/no toggles, filenames, solver names
}
```

Ipopt options are identified by string names; values are one of `Number`, `Integer`, or `String`; options can be set through calling code or by an `ipopt.opt` file in the execution directory. The `ipopt.opt` file is read line-by-line as option name, whitespace, then value, with `#` comments allowed. ([coin-or.github.io](https://coin-or.github.io/Ipopt/OPTIONS.html))

---

## 5.1 Core option syntax examples

### Number options

```text id="d650ae"
tol 1e-8
acceptable_tol 1e-6
mu_init 1e-2
max_wall_time 600.0
constr_viol_tol 1e-6
```

### Integer options

```text id="s8n47i"
max_iter 500
print_level 5
acceptable_iter 15
file_print_level 7
```

### String options

```text id="47ysee"
mu_strategy adaptive
linear_solver mumps
nlp_scaling_method gradient-based
hessian_approximation limited-memory
warm_start_init_point yes
print_user_options yes
```

**Agent rule:** `yes` / `no` toggles are **String** option values in Ipopt, not Python booleans at the solver level. In Pyomo, `True` may stringify in ways not intended by Ipopt; use `"yes"` / `"no"` for Ipopt string toggles.

---

## 5.2 Option deployment channels

```text id="r0b734"
Channel A: Pyomo persistent solver-object options
  opt.options["tol"] = 1e-8

Channel B: Pyomo solve-local options
  opt.solve(model, options={"tol": 1e-8})

Channel C: Ipopt option file
  ipopt.opt

Channel D: direct .nl executable command-line options
  ipopt model.nl -AMPL tol=1e-8 max_iter=500

Channel E: new Pyomo contrib Ipopt interface
  Ipopt().solve(model, solver_options={...})
```

Pyomo can pass solver options either by mutating the solver object’s `options` dictionary or by passing `options={...}` into `solve(...)`; persistent dictionary options remain across solves, while solve-local options temporarily override matching persistent entries. `tee=True` is Pyomo-level output streaming, not a solver option. ([pyomo.readthedocs.io](https://pyomo.readthedocs.io/en/latest/howto/solver_recipes.html))

---

## 5.3 Channel A: Pyomo persistent options

### Syntax

```python id="09r7n5"
import pyomo.environ as pyo

opt = pyo.SolverFactory("ipopt")

opt.options["tol"] = 1e-8
opt.options["max_iter"] = 1000
opt.options["mu_strategy"] = "adaptive"
opt.options["linear_solver"] = "mumps"
opt.options["print_user_options"] = "yes"

results = opt.solve(model, tee=True)
```

### Multiple persistent options

```python id="9s0nff"
opt.options.update({
    "tol": 1e-8,
    "acceptable_tol": 1e-6,
    "max_iter": 3000,
    "print_level": 5,
    "nlp_scaling_method": "gradient-based",
})
```

### Persistent option lifetime

```python id="s3qd38"
opt = pyo.SolverFactory("ipopt")
opt.options["tol"] = 1e-8

res1 = opt.solve(m1)  # uses tol=1e-8
res2 = opt.solve(m2)  # also uses tol=1e-8

del opt.options["tol"]
res3 = opt.solve(m3)  # no persistent tol override
```

Pyomo documents that directly modifying `optimizer.options` creates options that persist across every call to `optimizer.solve(...)` unless removed from the options dictionary. ([pyomo.readthedocs.io](https://pyomo.readthedocs.io/en/latest/howto/solver_recipes.html))

### Agent value case

```text id="mq2i40"
Use persistent options when:
  same solver profile reused across many solves
  object-level solver factory encapsulates deployment policy
  repeated solves should be homogeneous
  model-family benchmark needs identical options
```

---

## 5.4 Channel B: Pyomo solve-local options

### Syntax

```python id="4hv5yd"
results = opt.solve(
    model,
    tee=True,
    options={
        "tol": 1e-8,
        "max_iter": 500,
        "print_user_options": "yes",
    },
)
```

### Temporary override of persistent options

```python id="t1g7fa"
opt = pyo.SolverFactory("ipopt")
opt.options["tol"] = 1e-6
opt.options["max_iter"] = 1000

res = opt.solve(
    model,
    options={
        "tol": 1e-8,       # overrides only for this solve
        "max_iter": 2000,  # overrides only for this solve
    },
)

# next solve returns to tol=1e-6, max_iter=1000
res2 = opt.solve(model)
```

Pyomo’s solver recipe docs state that `solve(..., options={...})` options persist only within that solve and temporarily override matching entries in the solver object’s options dictionary. ([pyomo.readthedocs.io](https://pyomo.readthedocs.io/en/latest/howto/solver_recipes.html))

### Agent value case

```text id="e0a6al"
Use solve-local options when:
  one-off diagnostic solve
  temporary derivative checker
  temporary max_iter/time limit
  multi-start with profile-specific limits
  avoid mutating shared solver object
```

---

## 5.5 Channel C: `ipopt.opt` file

### Canonical file

```text id="m7ppnt"
# ipopt.opt

# Turn off NLP scaling
nlp_scaling_method none

# Initial barrier parameter
mu_init 1e-2

# Iteration limit
max_iter 500

# Audit user-set options
print_user_options yes
```

This is exactly the syntax Ipopt documents: comment lines use `#`; each active line contains option name, whitespace, then value; `nlp_scaling_method none`, `mu_init 1e-2`, and `max_iter 500` are valid examples. ([coin-or.github.io](https://coin-or.github.io/Ipopt/OPTIONS.html))

### File placement

```text id="46gpe7"
default option_file_name = ipopt.opt
default lookup context  = execution / working directory
```

`option_file_name` defaults to `ipopt.opt`; setting it before the option file is read selects another filename; setting it to an empty string disables reading an options file. Ipopt’s docs also state that it does not make sense to specify `option_file_name` inside the option file itself. ([coin-or.github.io](https://coin-or.github.io/Ipopt/OPTIONS.html))

### Explicit option file path through Pyomo

```python id="esyu2a"
opt = pyo.SolverFactory("ipopt")
opt.options["option_file_name"] = "/absolute/path/to/ipopt.opt"
res = opt.solve(model, tee=True)
```

### Disable option-file reading

```python id="qrr6ck"
opt.options["option_file_name"] = ""
```

### Agent value case

```text id="ci73d4"
Use ipopt.opt when:
  option profile should be version-controlled
  executable solve should be reproducible outside Python
  output_file / file_print_level / file_append required
  same profile shared across Pyomo, AMPL, direct .nl workflows
  deployment team wants solver knobs outside application code
```

---

## 5.6 Option-file-only output controls

```text id="psrg8j"
# ipopt.opt

output_file ipopt_run.log
file_print_level 7
file_append no
```

`output_file`, `file_print_level`, and `file_append` are documented as options that only work when read from the `ipopt.opt` options file; `output_file` names a file to write, `file_print_level` controls file verbosity, and `file_append` controls append versus truncate. ([coin-or.github.io](https://coin-or.github.io/Ipopt/OPTIONS.html))

### Wrong channel

```python id="e9e68p"
# Usually wrong / ineffective for Ipopt executable behavior:
opt.options["output_file"] = "ipopt_run.log"
opt.options["file_print_level"] = 7
```

### Correct Pyomo legacy workaround: `OF_` prefix

```python id="gzv5rk"
opt = pyo.SolverFactory("ipopt")

opt.options["OF_output_file"] = "ipopt_run.log"
opt.options["OF_file_print_level"] = 7
opt.options["OF_file_append"] = "no"

res = opt.solve(model, tee=True)
```

Pyomo’s legacy Ipopt plugin treats options whose keys start with `OF_` as Ipopt option-file entries, writes them to a temporary `.opt` file, and passes `option_file_name=<temporary file>` on the Ipopt command line; it raises an error if `OF_` options are mixed with an explicit `option_file_name`, and warns that a current-working-directory `ipopt.opt` will be ignored when generated `OF_` options are used. ([pyomo.readthedocs.io](https://pyomo.readthedocs.io/en/6.9.3/_modules/pyomo/solvers/plugins/solvers/IPOPT.html))

---

## 5.7 Channel D: direct `.nl` command-line options

### Direct solve with inline options

```bash id="ca1vjo"
ipopt model.nl -AMPL tol=1e-8 max_iter=500 print_level=5
```

### Direct solve with option file

```bash id="8avsnf"
cat > ipopt.opt <<'EOF'
tol 1e-8
max_iter 500
linear_solver mumps
print_user_options yes
EOF

ipopt model.nl -AMPL
```

### Direct option dump

```bash id="8yobxk"
ipopt -=
ipopt --print-options > ipopt.print-options.txt
```

The AMPL solver executable supports `-=` to print AMPL-available options, and `--print-options` generates option documentation for the installed executable. The Pyomo legacy Ipopt interface constructs a command line with the executable, the `.nl` problem file, `-AMPL`, and option strings appended as `key=value`. ([coin-or.github.io](https://coin-or.github.io/Ipopt/OPTIONS.html))

### Agent value case

```text id="iybe6i"
Use direct .nl command when:
  debugging Pyomo-generated .nl outside Python
  reproducing solver behavior from archived files
  comparing Pyomo interface versus executable behavior
  isolating solver option errors from model-construction errors
```

---

## 5.8 Channel E: new Pyomo contrib Ipopt interface

### Constructor / solve syntax

```python id="nhul3e"
from pyomo.contrib.solver.solvers.ipopt import Ipopt

solver = Ipopt()

results = solver.solve(
    model,
    tee=True,
    solver_options={
        "tol": 1e-8,
        "max_iter": 1000,
        "linear_solver": "mumps",
    },
)
```

### Config-style deployment

```python id="4gxcwi"
solver = Ipopt()
solver.config.executable = "/absolute/path/to/ipopt"
solver.config.solver_options = {
    "tol": 1e-8,
    "print_user_options": "yes",
}
solver.config.tee = True

results = solver.solve(model)
```

The newer Pyomo `Ipopt` interface is NL-file based and exposes configuration entries including `tee`, `working_dir`, `load_solutions`, `symbolic_solver_labels`, `time_limit`, `solver_options`, and `executable`; `executable` defaults to searching `PATH` for `ipopt`, and `has_linear_solver(...)` solves a small problem to test linear-solver availability. ([pyomo.readthedocs.io](https://pyomo.readthedocs.io/en/stable/api/pyomo.contrib.solver.solvers.ipopt.Ipopt.html))

### Agent value case

```text id="pqozqp"
Use contrib Ipopt interface when:
  codebase standardizes on Pyomo contrib solver API
  explicit solver configuration object desired
  working_dir / symbolic labels / load_solutions controls matter
  future-oriented Pyomo solver interface preferred
```

---

## 5.9 AMPL-style option strings

### AMPL syntax

```ampl id="jddq0s"
options ipopt_options "nlp_scaling_method=none mu_init=1e-2 max_iter=500";
```

Ipopt’s AMPL-interface docs show `options ipopt_options "nlp_scaling_method=none mu_init=1e-2 max_iter=500"` as a valid command, and state that `ipopt.opt` takes preference over options set in an executable or AMPL model. ([coin-or.github.io](https://coin-or.github.io/Ipopt/OPTIONS.html))

### Agent translation

```text id="q7v3gx"
ipopt.opt:
  nlp_scaling_method none
  mu_init 1e-2
  max_iter 500

AMPL / command-line style:
  nlp_scaling_method=none mu_init=1e-2 max_iter=500

Pyomo dict style:
  {"nlp_scaling_method": "none", "mu_init": 1e-2, "max_iter": 500}
```

---

## 5.10 Option precedence and collision rules

### Ipopt / AMPL-level precedence

```text id="zxd9lu"
ipopt.opt has preference over options set in a particular executable or AMPL model.
```

Ipopt explicitly documents that `ipopt.opt` is given preference, enabling users to override options set elsewhere by specifying new values in `ipopt.opt`. ([coin-or.github.io](https://coin-or.github.io/Ipopt/OPTIONS.html))

### Pyomo persistent versus solve-local

```text id="sdayl4"
solve(options={...}) temporarily overrides matching opt.options entries.
opt.options entries persist across future solves.
```

Pyomo explicitly documents this persistence and temporary-override behavior. ([pyomo.readthedocs.io](https://pyomo.readthedocs.io/en/latest/howto/solver_recipes.html))

### Pyomo `OF_` versus `option_file_name`

```text id="r2zmoq"
OF_* options + explicit option_file_name => Pyomo raises ValueError.
OF_* options + cwd ipopt.opt           => Pyomo warns cwd ipopt.opt ignored.
```

Pyomo’s legacy Ipopt plugin implements this behavior while generating a temporary option file for `OF_` options. ([pyomo.readthedocs.io](https://pyomo.readthedocs.io/en/6.9.3/_modules/pyomo/solvers/plugins/solvers/IPOPT.html))

### Recommended collision policy

```text id="bfip11"
one solve profile = one primary channel

Preferred:
  application code profile:
    opt.options / solve(options={...})

  reproducible executable profile:
    explicit ipopt.opt + option_file_name

  file-output profile from Pyomo legacy:
    OF_output_file / OF_file_print_level

Avoid:
  cwd ipopt.opt + opt.options + OF_* + option_file_name simultaneously
```

---

## 5.11 Option audit and installed-build documentation

### Build-specific option dump

```bash id="fes0eo"
ipopt --print-options > ipopt.print-options.txt
ipopt -= > ipopt.ampl-options.txt
```

Ipopt states that `--print-options` generates option documentation for the executable and warns that availability/default values of some linear-solver options depend on how Ipopt was built; therefore installed-build option documentation should be captured for reproducibility. ([coin-or.github.io](https://coin-or.github.io/Ipopt/OPTIONS.html))

### Runtime user-option audit

```python id="t0axdi"
opt.options.update({
    "print_user_options": "yes",
    "tol": 1e-8,
    "max_iter": 500,
})
res = opt.solve(model, tee=True)
```

`print_user_options=yes` prints user-set options, values, and whether they were used, with Ipopt’s documented caveat that usage reporting may be inaccurate in some internal-flow cases. ([coin-or.github.io](https://coin-or.github.io/Ipopt/OPTIONS.html))

### Full option docs through solve

```python id="cc0avu"
opt.options.update({
    "print_options_documentation": "yes",
    "print_options_mode": "text",
    "print_advanced_options": "yes",
})
res = opt.solve(model, tee=True)
```

Ipopt supports `print_options_documentation`, `print_options_mode` values such as `text`, `latex`, and `doxygen`, and `print_advanced_options` for printing advanced options. ([coin-or.github.io](https://coin-or.github.io/Ipopt/OPTIONS.html))

### Artifact set for advanced docs

```text id="z3x52y"
environment.yml
conda list --explicit
which/where ipopt output
ipopt -v output
ipopt --print-options output
ipopt -= output
small NLP smoke log with print_user_options=yes
linear solver probe report
```

---

## 5.12 Option type discipline for LLM agents

### Correct values

```python id="33o059"
options = {
    # Number
    "tol": 1e-8,
    "mu_init": 1e-2,
    "max_wall_time": 600.0,

    # Integer
    "max_iter": 1000,
    "print_level": 5,

    # String
    "mu_strategy": "adaptive",
    "nlp_scaling_method": "none",
    "warm_start_init_point": "yes",
}
```

### Avoid ambiguous Python booleans

```python id="rcw8n6"
# BAD
opt.options["warm_start_init_point"] = True
opt.options["print_user_options"] = True

# GOOD
opt.options["warm_start_init_point"] = "yes"
opt.options["print_user_options"] = "yes"
```

### Avoid quoted numeric strings unless needed

```python id="d2o3fv"
# Usually fine, but less type-clear:
opt.options["tol"] = "1e-8"

# Preferred:
opt.options["tol"] = 1e-8
```

### Avoid spaces in string values

```python id="eis3ro"
# Most Ipopt string enum values have no spaces.
opt.options["linear_solver"] = "mumps"
opt.options["hessian_approximation"] = "limited-memory"
```

Pyomo passes solver options through with little processing and does not validate whether the solver actually supports a given option; if an option is invalid for the solver, the solver will usually complain. ([pyomo.readthedocs.io](https://pyomo.readthedocs.io/en/latest/howto/solver_recipes.html))

---

## 5.13 Common option profiles

### Baseline audit profile

```python id="2rds05"
IPOPT_AUDIT = {
    "print_user_options": "yes",
    "print_level": 5,
    "tol": 1e-8,
    "max_iter": 1000,
}
```

### Quiet production profile

```python id="ptku4l"
IPOPT_QUIET = {
    "print_level": 0,
    "sb": "yes",
    "tol": 1e-8,
    "max_iter": 1000,
}
```

### Feasibility-debug profile

```python id="3baaby"
IPOPT_FEASIBILITY_DEBUG = {
    "print_level": 7,
    "print_user_options": "yes",
    "inf_pr_output": "original",
    "expect_infeasible_problem": "yes",
    "required_infeasibility_reduction": 0.99,
    "max_resto_iter": 5000,
}
```

### Derivative-check profile

```python id="t2h41g"
IPOPT_DERIVATIVE_CHECK = {
    "derivative_test": "first-order",
    "derivative_test_print_all": "yes",
    "max_iter": 0,
    "print_level": 7,
}
```

### Warm-start profile

```python id="n1jj3x"
IPOPT_WARM_START = {
    "warm_start_init_point": "yes",
    "warm_start_bound_push": 1e-6,
    "warm_start_mult_bound_push": 1e-6,
    "mu_init": 1e-4,
}
```

---

## 5.14 Option-profile deployment helper

```python id="85gp14"
from __future__ import annotations

import pyomo.environ as pyo


def make_ipopt(
    *,
    profile: str = "audit",
    executable: str | None = None,
    extra_options: dict[str, object] | None = None,
):
    profiles: dict[str, dict[str, object]] = {
        "audit": {
            "print_user_options": "yes",
            "print_level": 5,
            "tol": 1e-8,
            "max_iter": 1000,
        },
        "quiet": {
            "print_level": 0,
            "sb": "yes",
            "tol": 1e-8,
            "max_iter": 1000,
        },
        "debug": {
            "print_user_options": "yes",
            "print_level": 7,
            "inf_pr_output": "original",
            "tol": 1e-8,
            "max_iter": 1000,
        },
        "derivative_check": {
            "print_user_options": "yes",
            "print_level": 7,
            "derivative_test": "first-order",
            "derivative_test_print_all": "yes",
            "max_iter": 0,
        },
    }

    kwargs = {}
    if executable is not None:
        kwargs["executable"] = executable

    opt = pyo.SolverFactory("ipopt", **kwargs)
    if not opt.available(exception_flag=False):
        raise RuntimeError("Ipopt executable unavailable to Pyomo.")

    opt.options.update(profiles[profile])
    if extra_options:
        opt.options.update(extra_options)

    return opt
```

### Usage

```python id="moamms"
opt = make_ipopt(
    profile="audit",
    extra_options={
        "linear_solver": "mumps",
        "nlp_scaling_method": "gradient-based",
    },
)
res = opt.solve(model, tee=True)
```

---

## 5.15 `ipopt.opt` writer helper

```python id="2ndtfd"
from __future__ import annotations

from pathlib import Path
from typing import Mapping


def write_ipopt_opt(path: str | Path, options: Mapping[str, object]) -> Path:
    path = Path(path)
    lines = [
        "# Generated Ipopt option file",
        "# Syntax: option_name whitespace value",
        "",
    ]

    for key, value in options.items():
        if isinstance(value, bool):
            raise TypeError(
                f"Ipopt string toggles should be explicit 'yes'/'no', not bool: {key}={value}"
            )
        lines.append(f"{key} {value}")

    path.write_text("\n".join(lines) + "\n")
    return path
```

### Usage

```python id="r0boaf"
write_ipopt_opt(
    "ipopt.opt",
    {
        "tol": 1e-8,
        "max_iter": 500,
        "nlp_scaling_method": "none",
        "print_user_options": "yes",
        "output_file": "ipopt_run.log",
        "file_print_level": 5,
    },
)
```

---

## 5.16 Option validation against installed dump

### Dump

```bash id="ut8kz8"
ipopt --print-options > ipopt.print-options.txt
```

### Simple validator

```python id="nmm8s9"
from pathlib import Path


def load_ipopt_option_names(print_options_path: str | Path) -> set[str]:
    names: set[str] = set()
    for line in Path(print_options_path).read_text().splitlines():
        line = line.strip()
        if line.startswith("▸ "):
            # Example: "▸ tol: Desired convergence tolerance..."
            token = line[2:].split(":", 1)[0].strip()
            if token:
                names.add(token)
    return names


def validate_options_against_dump(options: dict[str, object], dump_path: str | Path):
    available = load_ipopt_option_names(dump_path)
    unknown = sorted(k for k in options if k not in available and not k.startswith("OF_"))
    if unknown:
        raise ValueError(f"Options not found in installed Ipopt option dump: {unknown}")
```

### Usage

```python id="luz3eq"
profile = {
    "tol": 1e-8,
    "max_iter": 500,
    "linear_solver": "mumps",
    "print_user_options": "yes",
}

validate_options_against_dump(profile, "ipopt.print-options.txt")
```

**Agent caveat:** option dumps prove parser-level option availability, not necessarily runtime availability of a selected linear solver. Use `has_linear_solver(...)` for linear-solver capability tests.

---

## 5.17 Linear-solver option deployment guard

```python id="07dk65"
def set_verified_linear_solver(opt, preferred=("mumps", "spral")):
    for name in preferred:
        try:
            if opt.has_linear_solver(name):
                opt.options["linear_solver"] = name
                return name
        except Exception:
            pass
    raise RuntimeError(f"No verified Ipopt linear solver from preferred list: {preferred}")
```

Ipopt’s options docs warn that availability/defaults for options concerning linear solvers depend on the Ipopt build, and the Pyomo contrib Ipopt API documents `has_linear_solver(...)` as solving a small problem to test whether the executable can access a specified linear solver. ([coin-or.github.io](https://coin-or.github.io/Ipopt/OPTIONS.html))

---

## 5.18 Direct `.nl` reproducibility bundle

### In Python: keep generated files

```python id="hgo7lc"
res = opt.solve(
    model,
    tee=True,
    keepfiles=True,
    symbolic_solver_labels=True,
)
```

### Re-run directly

```bash id="w871pq"
ipopt pyomo_model.nl -AMPL tol=1e-8 max_iter=500 linear_solver=mumps
```

### Re-run with `ipopt.opt`

```bash id="ivuyfa"
cat > ipopt.opt <<'EOF'
tol 1e-8
max_iter 500
linear_solver mumps
print_user_options yes
EOF

ipopt pyomo_model.nl -AMPL
```

**Agent value case**

```text id="xcplc8"
Use direct replay when:
  Pyomo solve fails and solver-side reproduction needed
  support ticket / benchmark artifact required
  exact .nl + options + log should be archived
  option parsing behavior must be isolated from Pyomo model generation
```

---

## 5.19 Option channel decision table

| Requirement                              | Recommended channel                        |
| ---------------------------------------- | ------------------------------------------ |
| quick notebook solve                     | `opt.options[...]`                         |
| one-off diagnostic                       | `solve(..., options={...})`                |
| reusable application profile             | wrapper function setting `opt.options`     |
| version-controlled solver profile        | `ipopt.opt`                                |
| Ipopt `output_file` / `file_print_level` | `ipopt.opt` or Pyomo legacy `OF_*`         |
| direct executable reproducibility        | `.nl` + `ipopt.opt`                        |
| Pyomo contrib solver API                 | `Ipopt().solve(..., solver_options={...})` |
| avoid hidden state                       | solve-local `options={...}`                |
| avoid command-line length issues         | `ipopt.opt`                                |
| installed-build audit                    | `ipopt --print-options`, `ipopt -=`        |

---

## 5.20 Anti-patterns for LLM agents

```text id="9vk0v3"
BAD:
  opt.options["print_user_options"] = True

GOOD:
  opt.options["print_user_options"] = "yes"

BAD:
  opt.options["output_file"] = "run.log"

GOOD:
  ipopt.opt:
    output_file run.log
    file_print_level 5

GOOD in Pyomo legacy:
  opt.options["OF_output_file"] = "run.log"
  opt.options["OF_file_print_level"] = 5

BAD:
  assume linear_solver=ma57 works because docs list ma57

GOOD:
  dump installed options + probe opt.has_linear_solver("ma57")

BAD:
  persistent opt.options mutated in a library function with hidden global side effects

GOOD:
  construct solver per solve profile or pass solve-local options

BAD:
  mix cwd ipopt.opt, option_file_name, OF_* options, and solve(options={...}) without documenting precedence

GOOD:
  one primary option channel per solve profile
```

---

## 5.21 Final checklist

```text id="u54zts"
[ ] Classify each option as Number / Integer / String.
[ ] Use "yes"/"no" strings for Ipopt toggles.
[ ] Use opt.options for persistent profile options.
[ ] Use solve(options={...}) for temporary per-solve options.
[ ] Use ipopt.opt for file-output options and executable-level reproducibility.
[ ] Use OF_* only when Pyomo legacy interface must generate an Ipopt option file.
[ ] Do not mix OF_* and option_file_name.
[ ] Capture ipopt --print-options for the installed executable.
[ ] Capture ipopt -= for AMPL-interface option surface.
[ ] Enable print_user_options=yes during option-profile development.
[ ] Treat Pyomo tee/logfile as Pyomo controls, not Ipopt options.
[ ] Validate installed option names for production profiles.
[ ] Probe linear_solver choices independently of parser-level option presence.
[ ] Archive option profile + solver log with model benchmark results.
```

# Ipopt Advanced — Section 6: Pyomo integration front doors

Style target: dense advanced technical catalog / agent-ready implementation reference. 

## 6.0 Integration-surface invariant

```text id="f8k3t9"
Pyomo → Ipopt integration options:

1. Classic Pyomo SolverFactory("ipopt")
   stable, common, executable/NL-file workflow

2. Explicit executable path
   same classic interface, deterministic binary selection

3. Newer Pyomo contrib solver interface
   pyomo.contrib.solver.solvers.ipopt.Ipopt
   NL-file-based interface with richer config object

4. APPSI Ipopt
   pyomo.contrib.appsi.solvers.Ipopt
   auto-persistent-style interface useful for repeated solves / model updates
```

**Agent rule:** default to classic `SolverFactory("ipopt")` for broad compatibility; use the newer contrib `Ipopt` interface when config-rich solve control is valuable; use APPSI when repeated solves with small model changes dominate runtime and the code can safely manage update semantics. Pyomo’s classic solver recipes document `tee`, solver `options`, solve-local `options={...}`, persistent solver-object options, and `executable=`; the newer Ipopt API documents config keys such as `tee`, `working_dir`, `load_solutions`, `symbolic_solver_labels`, `time_limit`, `solver_options`, and `executable`. ([Pyomo Documentation][1])

---

## 6.1 Classic front door: `pyo.SolverFactory("ipopt")`

### Minimal solve

```python id="nh7w6h"
import pyomo.environ as pyo

opt = pyo.SolverFactory("ipopt")
opt.options["tol"] = 1e-8

results = opt.solve(model, tee=True)
```

**Semantics**

```text id="zc6m0a"
SolverFactory("ipopt"):
  resolves Pyomo's classic Ipopt solver plugin
  expects an ipopt executable discoverable on PATH unless executable= supplied
  writes/uses NL-file-based solver interaction
  sends Ipopt options through solver option mechanisms
  parses solver result and normally loads primal values unless configured otherwise
```

Pyomo’s solver recipe docs show attaching options to the solver object through `optimizer.options[...]`, calling `solve(..., tee=True)`, and note that `tee` is a Pyomo option independent of the solver. ([Pyomo Documentation][1])

### Persistent options on solver object

```python id="mvuvfe"
opt = pyo.SolverFactory("ipopt")

opt.options.update({
    "tol": 1e-8,
    "max_iter": 1000,
    "linear_solver": "mumps",
    "print_user_options": "yes",
})

res1 = opt.solve(model_1, tee=True)
res2 = opt.solve(model_2, tee=True)  # same options persist
```

Pyomo documents that directly modifying the solver object’s `options` dictionary creates options that persist across every `optimizer.solve(...)` call until removed. ([Pyomo Documentation][1])

### Solve-local temporary options

```python id="aw6qaf"
opt = pyo.SolverFactory("ipopt")
opt.options["tol"] = 1e-6

results = opt.solve(
    model,
    tee=True,
    options={
        "tol": 1e-8,        # temporary override
        "max_iter": 500,    # temporary for this solve only
    },
)

# opt.options["tol"] remains 1e-6 for future solves
```

Pyomo documents that `solve(..., options={...})` options persist only within that solve and temporarily override matching entries in the solver object’s options dictionary. ([Pyomo Documentation][1])

### Classic interface value case

```text id="qyv9jg"
Use classic SolverFactory("ipopt") when:
  maximum Pyomo compatibility desired
  examples/tutorials should be familiar
  conda-forge ipopt executable is on PATH
  NL-file workflow is acceptable
  solve count is modest
  model is rebuilt or cloned between solves
  implementation simplicity beats advanced interface control
```

---

## 6.2 Explicit executable path

### Syntax

```python id="pn2bvv"
opt = pyo.SolverFactory(
    "ipopt",
    executable="/absolute/path/to/ipopt",
)
```

Windows:

```python id="08ftvj"
opt = pyo.SolverFactory(
    "ipopt",
    executable=r"C:\Users\user\miniforge3\envs\nlp\Library\bin\ipopt.exe",
)
```

Relative path:

```python id="tu2zif"
opt = pyo.SolverFactory("ipopt", executable="../bin/ipopt")
```

Pyomo documents `executable=` as the keyword to set an absolute or relative path when the solver executable is not on `PATH`. ([Pyomo Documentation][1])

### Robust factory

```python id="fclrlh"
from pathlib import Path
import pyomo.environ as pyo


def make_classic_ipopt(
    *,
    executable: str | Path | None = None,
    options: dict[str, object] | None = None,
):
    kwargs = {}
    if executable is not None:
        kwargs["executable"] = str(executable)

    opt = pyo.SolverFactory("ipopt", **kwargs)

    if not opt.available(exception_flag=False):
        raise RuntimeError(
            "Ipopt is not available to Pyomo. Install conda-forge::ipopt "
            "in the active environment or pass executable=/path/to/ipopt."
        )

    if options:
        opt.options.update(options)

    return opt
```

### Deployment value case

```text id="gbq7f5"
Use executable= when:
  multiple Ipopt binaries exist
  notebook PATH differs from shell PATH
  CI uses explicit toolchain path
  Windows Library/bin path not active
  custom HSL/Pardiso/MKL build should be selected
  reproducibility requires exact executable provenance
```

---

## 6.3 Availability, version, executable, linear-solver probes

### Classic interface probe

```python id="7elmj0"
import pyomo.environ as pyo

opt = pyo.SolverFactory("ipopt")

print("available:", opt.available(exception_flag=False))
print("executable:", opt.executable())
print("version:", opt.version())

for linear_solver in ["mumps", "spral", "ma57", "pardiso", "pardisomkl"]:
    try:
        print(linear_solver, opt.has_linear_solver(linear_solver))
    except Exception as exc:
        print(linear_solver, type(exc).__name__, exc)
```

The classic Ipopt API documents `available()`, `executable()`, `version()`, and `has_linear_solver(linear_solver)`; the newer Ipopt API also documents `has_linear_solver(...)` as solving a small problem to determine whether the executable has access to the specified linear solver. ([Pyomo Documentation][2])

### Agent rule

```text id="8u2tzx"
Before setting non-default linear_solver:
  probe has_linear_solver(...)
  or run a tiny NLP with print_user_options=yes
```

---

## 6.4 Streaming, log capture, and output destinations

### `tee=True`

```python id="7htaq1"
results = opt.solve(model, tee=True)
```

`tee=True` streams solver output; Pyomo notes that `tee` is a Pyomo option and solver-independent. ([Pyomo Documentation][1])

### `logfile=...`

```python id="ix2cp0"
results = opt.solve(
    model,
    tee=True,
    logfile="ipopt.solve.log",
)
```

### Ipopt file-output options through generated option file

```python id="4r3vv1"
opt.options["OF_output_file"] = "ipopt_file_output.log"
opt.options["OF_file_print_level"] = 5
```

**Agent rule**

```text id="shugyb"
tee=True:
  human/CI console diagnostics

logfile=...:
  Pyomo-captured solver process log

OF_output_file / ipopt.opt output_file:
  Ipopt-native output file options
```

---

## 6.5 Result loading and termination policy

### Default load behavior: classic interface

```python id="bmgi8h"
results = opt.solve(model, tee=True)
# variable values normally loaded into model if solve returns normally
```

### Manual load policy

```python id="5kp53d"
from pyomo.opt import SolverStatus, TerminationCondition

results = opt.solve(model, tee=True, load_solutions=False)

status = results.solver.status
tc = results.solver.termination_condition

if status == SolverStatus.ok and tc == TerminationCondition.optimal:
    model.solutions.load_from(results)
else:
    raise RuntimeError(f"Untrusted solve result: status={status}, termination={tc}")
```

**Value case**

```text id="hi7w3c"
load_solutions=False:
  inspect termination before mutating model values
  avoid loading infeasible / failed / time-limited result accidentally
  support degraded-result policies explicitly
```

Pyomo’s solver recipes show checking `results.solver.status` and `results.solver.termination_condition` to determine how to handle solver output. ([Pyomo Documentation][1])

---

## 6.6 Classic interface: option profile wrapper

```python id="drkut4"
import pyomo.environ as pyo


IPOPT_PROFILES = {
    "debug": {
        "print_user_options": "yes",
        "print_level": 7,
        "inf_pr_output": "original",
        "tol": 1e-8,
        "max_iter": 1000,
    },
    "production": {
        "print_level": 0,
        "sb": "yes",
        "tol": 1e-8,
        "max_iter": 1000,
    },
    "derivative_check": {
        "derivative_test": "first-order",
        "derivative_test_print_all": "yes",
        "max_iter": 0,
        "print_level": 7,
    },
}


def solve_with_ipopt_classic(
    model,
    *,
    profile: str = "debug",
    executable: str | None = None,
    tee: bool = True,
    extra_options: dict[str, object] | None = None,
    load_solutions: bool = True,
):
    kwargs = {}
    if executable is not None:
        kwargs["executable"] = executable

    opt = pyo.SolverFactory("ipopt", **kwargs)

    if not opt.available(exception_flag=False):
        raise RuntimeError("Ipopt executable unavailable to classic Pyomo interface.")

    opt.options.update(IPOPT_PROFILES[profile])
    if extra_options:
        opt.options.update(extra_options)

    return opt.solve(model, tee=tee, load_solutions=load_solutions)
```

---

## 6.7 Newer Pyomo contrib Ipopt interface

### Import

```python id="zqesce"
from pyomo.contrib.solver.solvers.ipopt import Ipopt
```

### Minimal solve

```python id="y1ykp6"
solver = Ipopt()

results = solver.solve(
    model,
    tee=True,
    solver_options={
        "tol": 1e-8,
        "max_iter": 1000,
    },
)
```

The documented `pyomo.contrib.solver.solvers.ipopt.Ipopt` interface solves a model using Ipopt and exposes keyword arguments including `tee`, `working_dir`, `load_solutions`, `raise_exception_on_nonoptimal_result`, `symbolic_solver_labels`, `time_limit`, `solver_options`, `executable`, and `writer_config`. ([Pyomo Documentation][2])

### Config-object style

```python id="gq18kl"
from pathlib import Path
from pyomo.contrib.solver.solvers.ipopt import Ipopt

solver = Ipopt()

solver.config.executable = "/absolute/path/to/ipopt"
solver.config.tee = True
solver.config.working_dir = Path("solver-work")
solver.config.load_solutions = False
solver.config.symbolic_solver_labels = True
solver.config.time_limit = 300.0
solver.config.solver_options = {
    "tol": 1e-8,
    "max_iter": 1000,
    "linear_solver": "mumps",
}

results = solver.solve(model)

# Explicit loading policy if needed:
# solver/result API is newer; use documented result handling for your Pyomo version.
```

### Solve-call style

```python id="m7mmvs"
results = solver.solve(
    model,
    tee=True,
    working_dir="solver-work",
    load_solutions=False,
    symbolic_solver_labels=True,
    time_limit=300.0,
    solver_options={
        "tol": 1e-8,
        "print_user_options": "yes",
    },
    executable="/absolute/path/to/ipopt",
)
```

`tee=True` maps to `sys.stdout`; `working_dir` controls where generated files are saved; `load_solutions=True` loads primal variable values; `symbolic_solver_labels=True` uses Pyomo component names in solver-facing names; `time_limit` is a solver time limit in seconds; and `executable` defaults to searching `PATH` for `ipopt`. ([Pyomo Documentation][2])

### New interface through factory names

```python id="z0nkth"
import pyomo.environ as pyo

status = pyo.SolverFactory("ipopt_v2").solve(
    model,
    solver_options={"max_iter": 100},
)
```

Pyomo’s redesigned-solver preview docs list Ipopt as registered under `ipopt` in the new contrib solver factory and `ipopt_v2` in the legacy solver factory, and show both backward-compatible `options={...}` and forward-compatible `solver_options={...}` for the v2-style interface. ([Pyomo Documentation][3])

### New interface value case

```text id="rv9g9d"
Use pyomo.contrib.solver.solvers.ipopt.Ipopt when:
  config object preferred over ad hoc kwargs
  working_dir should replace keepfiles-style behavior
  symbolic_solver_labels should be explicit and reproducible
  time_limit should be represented in solver config
  result object / new solver API behavior is desired
  future-facing Pyomo solver interface is acceptable
```

---

## 6.8 Newer Ipopt interface: writer configuration

### Writer-config sketch

```python id="511blr"
from pyomo.contrib.solver.solvers.ipopt import Ipopt

solver = Ipopt()

results = solver.solve(
    model,
    tee=True,
    writer_config={
        "symbolic_solver_labels": True,
        # Additional NLWriter config keys are Pyomo-version dependent.
    },
    solver_options={
        "tol": 1e-8,
    },
)
```

Pyomo’s newer Ipopt API exposes `writer_config` for the NL writer, and the experimental solver-interface docs state that the new interface provides access to newer problem-writer capabilities such as linear presolve and scaling options through `writer_config`. ([Pyomo Documentation][2])

**Agent rule:** use `symbolic_solver_labels=True` for debugging and reproducible symbol diagnostics; disable it for large production runs when label verbosity/file size matters.

---

## 6.9 APPSI Ipopt front door

### Import

```python id="xscxk5"
import pyomo.environ as pyo
from pyomo.contrib import appsi
```

### Minimal APPSI solve

```python id="13q8lv"
solver = appsi.solvers.Ipopt()

solver.ipopt_options.update({
    "tol": 1e-8,
    "max_iter": 1000,
    "linear_solver": "mumps",
})

results = solver.solve(model)

if results.termination_condition != appsi.base.TerminationCondition.optimal:
    raise RuntimeError(results.termination_condition)

solver.load_vars()
```

The APPSI Ipopt API documents `solve(model)`, `config`, `ipopt_options`, `get_primals`, `get_duals`, `get_reduced_costs`, `get_slacks`, `load_vars`, `set_instance`, `update_params`, `update_variables`, and persistent-style add/remove/update methods. ([Pyomo Documentation][4])

### APPSI repeated mutable-parameter solve

```python id="z5j7mr"
import numpy as np
import pyomo.environ as pyo
from pyomo.contrib import appsi

m = pyo.ConcreteModel()
m.x = pyo.Var(initialize=0.0)
m.y = pyo.Var(initialize=1.0)
m.p = pyo.Param(mutable=True, initialize=1.0)

m.obj = pyo.Objective(expr=m.x**2 + m.y**2)
m.c1 = pyo.Constraint(expr=m.y >= pyo.exp(m.x))
m.c2 = pyo.Constraint(expr=m.y >= (m.x - m.p)**2)

opt = appsi.solvers.Ipopt()
opt.ipopt_options["tol"] = 1e-8

for p_val in np.linspace(1.0, 10.0, 100):
    m.p.value = float(p_val)
    res = opt.solve(m)

    if res.termination_condition != appsi.base.TerminationCondition.optimal:
        raise RuntimeError(res.termination_condition)

    opt.load_vars()
    print(res.best_feasible_objective)
```

APPSI docs state that APPSI interfaces are designed to work similarly to most Pyomo solver interfaces but are efficient for resolving the same model with small changes, with example use cases including Benders decomposition, optimization-based bounds tightening, progressive hedging, and outer approximation; the docs show repeatedly changing a mutable `Param` and calling `opt.solve(m)`. ([Pyomo Documentation][5])

### APPSI update-config optimization

```python id="6ohxwe"
opt = appsi.solvers.Ipopt()

# Only safe when model structure is fixed:
opt.update_config.check_for_new_or_removed_constraints = False
opt.update_config.check_for_new_or_removed_vars = False
opt.update_config.update_constraints = False
opt.update_config.update_vars = False

for p_val in grid:
    m.p.value = float(p_val)
    res = opt.solve(m)
```

Pyomo’s APPSI example explicitly disables checks for new/removed constraints and variables, and disables constraint/variable updates, after demonstrating repeated solves with a mutable parameter. ([Pyomo Documentation][5])

### APPSI value case

```text id="nweysh"
Use APPSI Ipopt when:
  same model instance solved repeatedly
  only mutable Params or variable values change
  decomposition loop calls many NLP subproblems
  OBBT / scenario loops / continuation / parametric sweeps dominate
  primals, duals, reduced costs, slacks needed programmatically
  persistent-style update controls are worth managing
```

### APPSI caution

```text id="llol43"
APPSI speed controls are correctness-sensitive:
  if variables/constraints/objective structure changes,
  do not disable update checks casually.

Safe:
  mutable Param changes only
  same active constraint/objective/variable structure
  explicit update_params or full solve update path

Unsafe:
  add/remove constraints with checks disabled
  deactivate/activate constraints with checks disabled
  replace objective without set_objective or full reset
```

---

## 6.10 Interface comparison table

| Front door            | Import                                       | Option key                                       | Output key                      | Repeated-solve posture               | Best fit                            |
| --------------------- | -------------------------------------------- | ------------------------------------------------ | ------------------------------- | ------------------------------------ | ----------------------------------- |
| Classic SolverFactory | `pyomo.environ as pyo`                       | `opt.options[...]` / `solve(options={...})`      | `tee=True`, `logfile=...`       | rebuild/NL solve each call           | default Pyomo scripts               |
| Explicit executable   | `pyo.SolverFactory("ipopt", executable=...)` | same classic options                             | same classic output             | same classic behavior                | deterministic binary selection      |
| Contrib Ipopt         | `pyomo.contrib.solver.solvers.ipopt.Ipopt`   | `solver_options={...}` / `config.solver_options` | `tee`, `working_dir`            | NL-file interface with config object | future-facing/config-rich workflows |
| APPSI Ipopt           | `from pyomo.contrib import appsi`            | `solver.ipopt_options[...]`                      | APPSI result + load/get methods | efficient same-model resolves        | parametric/decomposition loops      |

---

## 6.11 Result object differences

### Classic result policy

```python id="ln8fs5"
results = opt.solve(model, load_solutions=False)

print(results.solver.status)
print(results.solver.termination_condition)

if results.solver.termination_condition == pyo.TerminationCondition.optimal:
    model.solutions.load_from(results)
```

### APPSI result policy

```python id="9h5mv3"
from pyomo.contrib import appsi

res = opt.solve(model)

if res.termination_condition == appsi.base.TerminationCondition.optimal:
    opt.load_vars()
else:
    raise RuntimeError(res.termination_condition)
```

APPSI base docs expose `Results.termination_condition`, `best_feasible_objective`, and `best_objective_bound`; APPSI Ipopt docs expose `load_vars`, `get_primals`, `get_duals`, `get_reduced_costs`, and `get_slacks`. ([Pyomo Documentation][5])

### Agent rule

```text id="duo0l1"
Do not write interface-agnostic result handling without adapter functions.
Classic Pyomo results and APPSI results are different objects.
```

---

## 6.12 Interface adapters for agent-generated code

### Classic adapter

```python id="hesla1"
from dataclasses import dataclass
import pyomo.environ as pyo
from pyomo.opt import SolverStatus, TerminationCondition


@dataclass
class SolveSummary:
    ok: bool
    status: str
    termination_condition: str
    objective: float | None


def solve_classic_ipopt(model, *, options=None, tee=True, load=True) -> SolveSummary:
    opt = pyo.SolverFactory("ipopt")
    if not opt.available(exception_flag=False):
        raise RuntimeError("Classic Ipopt unavailable.")

    if options:
        opt.options.update(options)

    results = opt.solve(model, tee=tee, load_solutions=load)

    obj = None
    active_objs = list(model.component_data_objects(pyo.Objective, active=True))
    if active_objs:
        obj = pyo.value(active_objs[0], exception=False)

    ok = (
        results.solver.status == SolverStatus.ok
        and results.solver.termination_condition == TerminationCondition.optimal
    )

    return SolveSummary(
        ok=bool(ok),
        status=str(results.solver.status),
        termination_condition=str(results.solver.termination_condition),
        objective=obj,
    )
```

### APPSI adapter

```python id="o4nlgy"
from dataclasses import dataclass
import pyomo.environ as pyo
from pyomo.contrib import appsi


@dataclass
class AppsiSolveSummary:
    ok: bool
    termination_condition: str
    best_feasible_objective: float | None


def solve_appsi_ipopt(model, *, options=None, load=True) -> AppsiSolveSummary:
    opt = appsi.solvers.Ipopt()

    if options:
        opt.ipopt_options.update(options)

    if not bool(opt.available()):
        raise RuntimeError("APPSI Ipopt unavailable.")

    res = opt.solve(model)

    ok = res.termination_condition == appsi.base.TerminationCondition.optimal
    if ok and load:
        opt.load_vars()

    return AppsiSolveSummary(
        ok=bool(ok),
        termination_condition=str(res.termination_condition),
        best_feasible_objective=res.best_feasible_objective,
    )
```

---

## 6.13 Working directory and generated-file control

### Classic: `keepfiles=True`, symbolic labels

```python id="7jcbwk"
results = opt.solve(
    model,
    tee=True,
    keepfiles=True,
    symbolic_solver_labels=True,
)
```

### New contrib interface: `working_dir`

```python id="n1zfz5"
solver = Ipopt()

results = solver.solve(
    model,
    tee=True,
    working_dir="solver-work",
    symbolic_solver_labels=True,
    solver_options={"tol": 1e-8},
)
```

The newer Ipopt interface documents `working_dir` as the directory in which generated files should be saved and says it replaces the old `keepfiles` option. ([Pyomo Documentation][2])

### Agent value case

```text id="qdtv3r"
Use generated-file retention when:
  debugging NL writer behavior
  reproducing Ipopt command-line failure
  archiving .nl/.sol/log for support
  mapping solver rows/columns to Pyomo component names
```

---

## 6.14 Explicit executable and version check across interfaces

### Classic

```python id="7on4gj"
classic = pyo.SolverFactory("ipopt", executable="/opt/ipopt/bin/ipopt")
print(classic.available(exception_flag=False))
print(classic.version())
```

### Contrib

```python id="58497m"
from pyomo.contrib.solver.solvers.ipopt import Ipopt

solver = Ipopt()
print(bool(solver.available()))
print(solver.version())

res = solver.solve(
    model,
    executable="/opt/ipopt/bin/ipopt",
    solver_options={"tol": 1e-8},
)
```

### APPSI

```python id="cbjbm0"
from pyomo.contrib import appsi

opt = appsi.solvers.Ipopt()
print(bool(opt.available()))
print(opt.version())
```

Both the contrib Ipopt and APPSI Ipopt APIs document `available()` and `version()` methods; the contrib Ipopt API documents `executable` as a solve/config keyword defaulting to PATH search. ([Pyomo Documentation][2])

---

## 6.15 Option-name mapping across interfaces

| Ipopt option         | Classic                                     | Contrib Ipopt                                     | APPSI Ipopt                                       |
| -------------------- | ------------------------------------------- | ------------------------------------------------- | ------------------------------------------------- |
| `tol`                | `opt.options["tol"] = 1e-8`                 | `solver_options={"tol": 1e-8}`                    | `opt.ipopt_options["tol"] = 1e-8`                 |
| `max_iter`           | `opt.options["max_iter"] = 1000`            | `solver.config.solver_options["max_iter"] = 1000` | `opt.ipopt_options["max_iter"] = 1000`            |
| `linear_solver`      | `opt.options["linear_solver"] = "mumps"`    | `solver_options={"linear_solver": "mumps"}`       | `opt.ipopt_options["linear_solver"] = "mumps"`    |
| `print_user_options` | `opt.options["print_user_options"] = "yes"` | `solver_options={"print_user_options": "yes"}`    | `opt.ipopt_options["print_user_options"] = "yes"` |

**Agent rule:** Ipopt option names stay the same; Pyomo container names change by interface.

---

## 6.16 Front-door selection policy

```text id="hhui6f"
Default generated code:
  pyo.SolverFactory("ipopt")

Custom executable / robust deployment:
  pyo.SolverFactory("ipopt", executable=...)

Config-heavy modern Pyomo:
  pyomo.contrib.solver.solvers.ipopt.Ipopt

Repeated same-model solves:
  pyomo.contrib.appsi.solvers.Ipopt

Need persistent-style variable/constraint add/remove/update:
  APPSI, with update_config handled carefully

Need maximum tutorial compatibility:
  classic SolverFactory

Need future-interface exploration:
  ipopt_v2 / contrib Ipopt, version-pinned
```

---

## 6.17 Anti-patterns for LLM agents

```text id="yhg7ft"
BAD:
  opt = SolverFactory("ipopt")
  opt.options["tol"] = 1e-8
  # then reuse opt in unrelated solves without realizing options persist

GOOD:
  create a fresh solver per profile or explicitly clear opt.options

BAD:
  opt.solve(model, tee={"tol": 1e-8})

GOOD:
  opt.solve(model, tee=True, options={"tol": 1e-8})

BAD:
  assume executable found in shell is found in notebook

GOOD:
  print(sys.executable), shutil.which("ipopt"), opt.executable()

BAD:
  mix APPSI Results with classic Results handling

GOOD:
  write adapter functions per interface

BAD:
  disable APPSI update checks while adding/removing constraints

GOOD:
  only disable update checks for fixed-structure repeated solves

BAD:
  symbolic_solver_labels=True in all production solves by default

GOOD:
  enable labels for debugging; disable for large production runs unless needed
```

---

## 6.18 Agent-ready deployment checklist

```text id="k6dd4n"
[ ] Decide interface:
      classic / explicit executable / contrib Ipopt / APPSI Ipopt.

[ ] Verify executable:
      SolverFactory("ipopt").available()
      solver.available()
      opt.version()

[ ] Pass options through the correct container:
      classic: opt.options or solve(options={...})
      contrib: solver_options or config.solver_options
      APPSI: ipopt_options

[ ] Use tee=True during bring-up.

[ ] Use load_solutions=False when termination policy must be checked first.

[ ] Use executable= for deterministic binary selection.

[ ] Use working_dir or keepfiles/symbolic labels for reproducible solver artifacts.

[ ] Probe linear solver before setting non-MUMPS choices.

[ ] Use APPSI only when repeated same-model or update-heavy workflow justifies interface complexity.

[ ] Do not write one result parser for all Pyomo solver interfaces without an adapter.
```

[1]: https://pyomo.readthedocs.io/en/latest/howto/solver_recipes.html "Solver Recipes — Pyomo 6.10.1.dev0 documentation"
[2]: https://pyomo.readthedocs.io/en/stable/api/pyomo.contrib.solver.solvers.ipopt.Ipopt.html "Ipopt — Pyomo 6.10.0 documentation"
[3]: https://pyomo.readthedocs.io/en/6.8.2/explanation/experimental/solvers.html "Future Solver Interface Changes — Pyomo 6.8.2 documentation"
[4]: https://pyomo.readthedocs.io/en/6.9.0/api/pyomo.contrib.appsi.solvers.ipopt.Ipopt.html "Ipopt — Pyomo 6.9.0 documentation"
[5]: https://pyomo.readthedocs.io/en/6.7.1/library_reference/appsi/appsi.html "APPSI — Pyomo 6.7.1 documentation"

# Ipopt Advanced — Section 7: Pyomo model construction patterns for Ipopt

Style target: dense advanced technical catalog / agent-ready reference. 

## 7.0 Construction invariant

```text id="k4zblc"
Pyomo model accepted by Ipopt =
  one active scalar Objective
  continuous Var objects only
  algebraic Constraint objects expressible as smooth equality / inequality / ranged rows
  evaluable starting values for nonlinear expressions
  valid variable bounds and domains
  no active discrete decision variables
  no nonsmooth / discontinuous expression nodes unless deliberately reformulated
  no unsupported external Python black-box functions in the NL solve path
```

Ipopt’s mathematical problem class is continuous `x ∈ R^n`, one scalar objective `f(x)`, general constraints `gL ≤ g(x) ≤ gU`, variable bounds `xL ≤ x ≤ xU`, and twice continuously differentiable objective/constraint functions; Pyomo `Var` defaults to real-valued variables with optional domains, bounds, and initialization, and Pyomo constraints can encode equality, inequality, or ranged rows. ([COIN-OR][1])

---

## 7.1 Variables: bounds, initialization, domains

### Scalar continuous variable

```python id="9lpygj"
import pyomo.environ as pyo

m = pyo.ConcreteModel()

m.x = pyo.Var(
    domain=pyo.Reals,
    bounds=(0.0, 10.0),
    initialize=1.0,
)
```

`Var` is Pyomo’s numeric variable component; `domain` defines valid values such as `Reals`, `NonNegativeReals`, or `Binary`, defaults to `Reals`, `bounds=(lower, upper)` defaults to `(None, None)`, and `initialize` supplies the initial value. ([Pyomo Documentation][2])

### Indexed variables with bound and initialization rules

```python id="l45y66"
m.I = pyo.Set(initialize=["A", "B", "C"])

lb = {"A": 0.0, "B": -5.0, "C": None}
ub = {"A": 10.0, "B": 5.0, "C": None}
x0 = {"A": 1.0, "B": 0.0, "C": 2.5}

def x_bounds(m, i):
    return (lb[i], ub[i])

def x_init(m, i):
    return x0[i]

m.x = pyo.Var(
    m.I,
    domain=pyo.Reals,
    bounds=x_bounds,
    initialize=x_init,
)
```

### Continuous nonnegative variables

```python id="kh7kao"
m.flow = pyo.Var(m.I, domain=pyo.NonNegativeReals, initialize=1.0)
```

Equivalent explicit-bound idiom:

```python id="8e0fms"
m.flow = pyo.Var(m.I, bounds=(0.0, None), initialize=1.0)
```

**Agent rule**

```text id="bcz5uk"
For Ipopt:
  Reals              -> valid continuous NLP domain
  NonNegativeReals   -> valid continuous NLP domain with lower bound 0
  PositiveReals      -> valid domain idea, but still initialize strictly positive
  Binary             -> not valid as an active Ipopt decision domain
  Integers           -> not valid as an active Ipopt decision domain
```

Pyomo exposes methods such as `is_continuous()`, `is_binary()`, and `is_integer()` on variable data; `is_continuous()` returns true for continuous real ranges, `is_binary()` returns true for Binary, and `is_integer()` returns true for contiguous integer ranges. Ipopt’s documented NLP variable vector is continuous real-valued, so integer/binary variables must be relaxed, fixed, or routed to a MIP/MINLP solver before using Ipopt. ([Pyomo Documentation][3])

---

## 7.2 Variable updates: value, bounds, fixed variables

### Set or change initial value

```python id="3a4pss"
m.x["A"].set_value(2.0)
m.x["B"].value = 0.5
```

Safer for potentially out-of-domain warm starts:

```python id="nuyji4"
m.x["A"].set_value(2.0, skip_validation=False)
```

Emergency assignment for diagnostic / repair workflows:

```python id="xm4y80"
m.x["A"].set_value(1e20, skip_validation=True)  # use sparingly
```

`set_value()` converts the incoming value to a numeric value, checks units, domain, and bounds, and can bypass domain/bound checking with `skip_validation=True`. ([Pyomo Documentation][3])

### Change bounds after construction

```python id="0q9zqj"
m.x["A"].setlb(0.0)
m.x["A"].setub(100.0)

m.x["B"].bounds = (-5.0, 5.0)
```

`setlb()` and `setub()` set lower and upper variable bounds, and the `bounds` property returns or sets the numeric `(lower, upper)` tuple; when no bound exists, Pyomo returns `None` rather than `±inf`. ([Pyomo Documentation][3])

### Fix / unfix variables

```python id="ma8dp2"
m.x["A"].fix(3.0)     # remove as decision variable / treat as fixed
m.x["A"].unfix()      # restore as decision variable
m.x["A"].free()       # alias for unfix()
```

Bulk fix:

```python id="dh83ys"
for i in m.I:
    m.x[i].fix(x_fixed[i])
```

Bulk unfix:

```python id="83t1jg"
for i in m.I:
    m.x[i].unfix()
```

`fix(value=...)` sets the fixed indicator to true and optionally sets the value first; `unfix()` sets the fixed indicator to false, and `free()` is an alias. ([Pyomo Documentation][3])

### Fixed variable deployment guidance

```text id="jwt9zo"
Use fix() when:
  design variable is fixed for a subproblem
  parameter sweep treats former decision variable as data
  warm-starting a reduced NLP
  implementing decomposition subproblem logic

Avoid:
  replacing a fixed variable with a Param if you later need to unfix
  fixing variables to invalid/out-of-bounds values
  fixing log/sqrt/division arguments at domain-bound singularities
```

---

## 7.3 Variable initialization patterns for nonlinear solves

### Initialize all nonlinear variables

```python id="bnwdvd"
for v in m.component_data_objects(pyo.Var, active=True):
    if v.value is None and not v.fixed:
        v.set_value(1.0, skip_validation=True)
```

### Interior-point-friendly initialization

```python id="pgpgwo"
def interior_start(lb, ub, default=1.0, frac=0.1):
    if lb is not None and ub is not None:
        return lb + frac * (ub - lb)
    if lb is not None:
        return lb + max(1.0, abs(lb)) * frac
    if ub is not None:
        return ub - max(1.0, abs(ub)) * frac
    return default

for v in m.component_data_objects(pyo.Var, active=True):
    if v.value is None and not v.fixed:
        lb = pyo.value(v.lb, exception=False) if v.lb is not None else None
        ub = pyo.value(v.ub, exception=False) if v.ub is not None else None
        v.set_value(interior_start(lb, ub), skip_validation=True)
```

### Domain-protected starts

```python id="a5bfo8"
m.conc = pyo.Var(bounds=(1e-8, None), initialize=1.0)  # log(conc)
m.rad  = pyo.Var(bounds=(1e-8, None), initialize=1.0)  # sqrt(rad)
m.den  = pyo.Var(bounds=(1e-6, None), initialize=1.0)  # numerator / den
```

**Agent rule**

```text id="5gzkaq"
Ipopt can start constraint-infeasible.
Ipopt cannot evaluate undefined objective/constraint functions.
Protect domains before solve.
```

---

## 7.4 Objective construction: one active scalar objective

### Minimize: default sense

```python id="q8g2kn"
m.obj = pyo.Objective(expr=(m.x - 3.0)**2)
```

### Maximize

```python id="8pl4mz"
m.profit = pyo.Objective(expr=revenue_expr - cost_expr, sense=pyo.maximize)
```

Pyomo’s `Objective` declares a variable-dependent function for an optimizer to minimize or maximize; `sense=pyo.maximize` specifies maximization, and the default sense is minimize. ([Pyomo Documentation][4])

### Explicit minimization transformation

```python id="p7d1ra"
# maximize profit
m.obj = pyo.Objective(expr=-profit_expr, sense=pyo.minimize)
```

**Agent preference**

```text id="9ox00b"
Use sense=pyo.maximize when semantic clarity matters.
Use -profit_expr minimization only when solver-interface / reporting logic standardizes on minimization.
```

### Multiple objective anti-pattern

```python id="j66833"
m.cost = pyo.Objective(expr=cost_expr)
m.emissions = pyo.Objective(expr=emissions_expr)  # BAD if both active
```

### Multi-objective remediation

```python id="xs7irc"
m.emissions.deactivate()

m.scalarized = pyo.Objective(
    expr=cost_expr + lambda_emissions * emissions_expr,
    sense=pyo.minimize,
)
```

### Active-objective sanity check

```python id="z0mpt0"
active_objs = list(m.component_data_objects(pyo.Objective, active=True))
if len(active_objs) != 1:
    raise RuntimeError(f"Ipopt requires exactly one active scalar objective; found {len(active_objs)}")
```

---

## 7.5 Constraint construction: equality, inequality, ranged rows

### Equality

```python id="7qgglj"
m.mass_balance = pyo.Constraint(expr=m.inlet - m.outlet == 0.0)
```

### Upper inequality

```python id="ysuh8t"
m.capacity = pyo.Constraint(expr=m.flow <= m.capacity_limit)
```

### Lower inequality

```python id="4hnlxq"
m.min_flow = pyo.Constraint(expr=m.flow >= m.min_required_flow)
```

### Ranged constraint: `pyo.inequality`

```python id="2c3tzt"
m.window = pyo.Constraint(
    expr=pyo.inequality(1.0, m.x + m.y, 10.0)
)
```

### Ranged constraint: 3-tuple rule

```python id="tq3nwh"
def window_rule(m):
    return (1.0, m.x + m.y, 10.0)

m.window2 = pyo.Constraint(rule=window_rule)
```

Pyomo constraints are commonly equality or inequality expressions returned by a rule; Pyomo also supports a 3-tuple `(lb, expr, ub)` where `lb` or `ub` can be `None`, interpreted as `lb <= expr <= ub`, and variables may appear only in the middle expression. ([Pyomo Documentation][5])

### Indexed constraints

```python id="hfglf4"
m.T = pyo.RangeSet(1, 24)

def storage_balance_rule(m, t):
    if t == 1:
        return m.soc[t] == m.soc0 + m.charge[t] - m.discharge[t]
    return m.soc[t] == m.soc[t - 1] + m.charge[t] - m.discharge[t]

m.storage_balance = pyo.Constraint(m.T, rule=storage_balance_rule)
```

### Skip constraints conditionally

```python id="lw9liv"
def optional_constraint_rule(m, i):
    if disabled[i]:
        return pyo.Constraint.Skip
    return m.x[i] <= ub[i]

m.optional = pyo.Constraint(m.I, rule=optional_constraint_rule)
```

### Constraint anti-patterns

```python id="4lfylh"
# BAD: variables in lower/upper positions of 3-tuple
m.c = pyo.Constraint(expr=(m.x, m.y, 10.0))

# BAD: chained inequality using Python syntax may be ambiguous / unsupported
m.c = pyo.Constraint(expr=1 <= m.x + m.y <= 10)

# GOOD
m.c = pyo.Constraint(expr=pyo.inequality(1, m.x + m.y, 10))
```

---

## 7.6 Mutable `Param` patterns for repeated solves

### Scalar mutable parameter

```python id="oxf06c"
m.p = pyo.Param(initialize=1.0, mutable=True)

m.x = pyo.Var(initialize=0.0)
m.obj = pyo.Objective(expr=(m.x - m.p)**2)
```

### Update and re-solve

```python id="7it5pu"
opt = pyo.SolverFactory("ipopt")
opt.options["tol"] = 1e-8

for p_val in [0.0, 1.0, 2.0, 3.0]:
    m.p.set_value(p_val)
    res = opt.solve(m, tee=False)
    print(p_val, pyo.value(m.x), pyo.value(m.obj))
```

`Param` has a `mutable` option that controls whether values can change after initialization, plus `default`, `initialize`, `validate`, and `within` options for data and domain validation. ([Pyomo Documentation][6])

### Indexed mutable parameter

```python id="k9puu2"
m.I = pyo.Set(initialize=["A", "B", "C"])
m.demand = pyo.Param(m.I, initialize=0.0, mutable=True)

m.production = pyo.Var(m.I, domain=pyo.NonNegativeReals, initialize=1.0)
m.balance = pyo.Constraint(m.I, rule=lambda m, i: m.production[i] >= m.demand[i])
m.cost = pyo.Objective(expr=sum(m.production[i]**2 for i in m.I))

for scenario in scenarios:
    for i in m.I:
        m.demand[i].set_value(scenario["demand"][i])
    res = opt.solve(m)
```

### APPSI repeated-solve pattern

```python id="v3p6ti"
from pyomo.contrib import appsi

solver = appsi.solvers.Ipopt()
solver.ipopt_options["tol"] = 1e-8

for p_val in grid:
    m.p.set_value(float(p_val))
    res = solver.solve(m)
    if res.termination_condition != appsi.base.TerminationCondition.optimal:
        raise RuntimeError(res.termination_condition)
    solver.load_vars()
```

APPSI Ipopt exposes `ipopt_options`, `solve(model)`, `update_params()`, `update_variables()`, `set_instance()`, and `load_vars()`; APPSI is useful for repeated solves where a model is updated rather than completely reconstructed. ([Pyomo Documentation][7])

### Mutable parameter deployment guidance

```text id="ujfo7x"
Use mutable Param when:
  numeric coefficient / RHS / target changes
  model algebraic structure is fixed
  repeated solves or parametric sweeps dominate
  APPSI / persistent update semantics are desired

Do not use mutable Param for:
  changing index set size
  adding/removing constraints
  changing expression topology
  replacing nonlinear functions
```

---

## 7.7 Expressions and derivative-generation posture

### Named expression

```python id="h1ey8x"
m.revenue = pyo.Expression(expr=sum(price[i] * m.sales[i] for i in m.I))
m.cost = pyo.Expression(expr=sum(cost[i] * m.production[i]**2 for i in m.I))

m.obj = pyo.Objective(expr=m.cost - m.revenue)
```

### Rule-generated expression

```python id="zfdh46"
def power_rule(m, i):
    return m.voltage[i] * m.current[i]

m.power = pyo.Expression(m.I, rule=power_rule)
```

Pyomo objectives and constraints use expression rules that return Pyomo algebraic expressions; operations on model components build Pyomo expressions rather than immediately computing numeric values. ([Pyomo Documentation][8])

### NL writer implications

```python id="52948x"
res = opt.solve(
    m,
    tee=True,
    symbolic_solver_labels=True,
    keepfiles=True,
)
```

The Pyomo NL writer supports deterministic file ordering, symbolic solver labels via `.row` / `.col` files, scaling through a `scaling_factor` suffix, explicit row/column ordering hints, export of named `Expression` objects as defined variables, and linear presolve. ([Pyomo Documentation][9])

### Agent derivative posture

```text id="dv9k1m"
Pyomo algebraic expression:
  preserve symbolic expression tree
  NL writer serializes nonlinear expression representation
  Ipopt / ASL workflow obtains derivative information from the NL expression representation

External black-box Python function:
  not ordinary algebraic expression
  not automatically differentiable through standard NL path
  requires supported ExternalFunction mechanism and derivative availability
```

### Use Pyomo math, not Python `math`

```python id="65s1t8"
# BAD: math.sin expects a Python float, not a symbolic Pyomo expression
import math
m.obj = pyo.Objective(expr=math.sin(m.x))

# GOOD
m.obj = pyo.Objective(expr=pyo.sin(m.x))
```

Additional smooth functions:

```python id="esrvui"
expr = (
    pyo.exp(m.x)
    + pyo.log(m.y)
    + pyo.sqrt(m.z)
    + pyo.cos(m.theta)
)
```

**Domain-protect smooth functions**

```python id="il6dmi"
m.y = pyo.Var(bounds=(1e-8, None), initialize=1.0)  # log(y)
m.z = pyo.Var(bounds=(1e-8, None), initialize=1.0)  # sqrt(z)
```

---

## 7.8 External functions: unsupported black-box risk

### ExternalFunction declaration

```python id="6dsayu"
m.f_ext = pyo.ExternalFunction(library="libmyfuncs.so", function="my_smooth_func")
m.obj = pyo.Objective(expr=m.f_ext(m.x))
```

Pyomo `ExternalFunction` embeds user-provided non-algebraic functions into Pyomo expressions; the docs warn that being able to express a model with external functions does not mean the model is solvable, and specifically note that the ASL interface supports external functions for general nonlinear solvers compiled against it but only allows compiled libraries through the `AMPLExternalFunction` interface. ([Pyomo Documentation][10])

### Agent guidance

```text id="50qn7n"
Prefer:
  native Pyomo algebraic expression using pyo.sin / pyo.exp / pyo.log / polynomial operations

Use ExternalFunction only when:
  function is smooth on all visited domains
  function value and derivatives are available to solver interface
  compiled AMPL external function deployment is controlled
  library path and platform ABI are tested

Avoid:
  arbitrary Python black-box functions
  scipy interpolators directly called on Var objects
  neural-network Python callables without differentiable algebraic embedding
```

---

## 7.9 Domains: continuous relaxation versus discrete variables

### Valid continuous examples for Ipopt

```python id="4md0mi"
m.x = pyo.Var(domain=pyo.Reals, initialize=0.0)
m.y = pyo.Var(domain=pyo.NonNegativeReals, initialize=1.0)
m.z = pyo.Var(bounds=(-10.0, 10.0), initialize=0.0)
```

### Invalid active discrete examples for Ipopt

```python id="tmpf0f"
m.b = pyo.Var(domain=pyo.Binary)
m.n = pyo.Var(domain=pyo.NonNegativeIntegers)
```

### Relaxation pattern

```python id="d5vbqk"
m.b_relaxed = pyo.Var(bounds=(0.0, 1.0), initialize=0.5)
```

### Fixed-discrete-as-data pattern

```python id="icz82q"
m.b = pyo.Var(domain=pyo.Binary, initialize=1)
m.b.fix(1)  # no longer an active decision variable
```

### Solver-routing pattern

```python id="caeity"
def contains_active_discrete_vars(model):
    for v in model.component_data_objects(pyo.Var, active=True):
        if not v.fixed and (v.is_binary() or v.is_integer()):
            return True
    return False

if contains_active_discrete_vars(m):
    raise RuntimeError("Active integer/binary variables present; do not use Ipopt directly.")
```

`VarData.is_binary()` and `VarData.is_integer()` expose whether variable domains are binary or integer-like; Ipopt’s NLP vector is continuous real-valued, so active discrete variables must trigger relaxation, fixing, reformulation, or a different solver route. ([Pyomo Documentation][3])

---

## 7.10 Nonsmooth operator anti-patterns

### Bad: nonsmooth Python / algebraic constructs

```python id="lmnt9l"
m.obj = pyo.Objective(expr=abs(m.x))          # nonsmooth at 0
m.c = pyo.Constraint(expr=max(m.x, m.y) <= 5) # Python max, not symbolic smooth max
m.c2 = pyo.Constraint(expr=pyo.floor(m.x) <= 3)
```

### Smooth approximation: absolute value

```python id="fvoc2z"
eps = 1e-6
m.abs_smooth = pyo.Expression(expr=pyo.sqrt(m.x**2 + eps))
m.obj = pyo.Objective(expr=m.abs_smooth)
```

### Exact epigraph for convex absolute value

```python id="z4onx6"
m.t = pyo.Var(domain=pyo.NonNegativeReals, initialize=1.0)
m.abs_pos = pyo.Constraint(expr=m.t >= m.x)
m.abs_neg = pyo.Constraint(expr=m.t >= -m.x)
m.obj = pyo.Objective(expr=m.t)
```

### Smooth approximation: max

```python id="lknynz"
eps = 1e-6
m.smooth_max_xy = pyo.Expression(
    expr=0.5 * (m.x + m.y + pyo.sqrt((m.x - m.y)**2 + eps))
)
```

**Agent rule**

```text id="7bgswd"
Ipopt smoothness contract beats Pyomo expressibility:
  Pyomo may build an expression
  but Ipopt still needs smooth derivatives
```

Ipopt allows linear/nonlinear and convex/nonconvex functions, but requires objective and constraint functions to be twice continuously differentiable for its intended NLP class. ([COIN-OR][1])

---

## 7.11 Accidental unboundedness controls

### Bad

```python id="wb4xka"
m.x = pyo.Var(initialize=0.0)  # free variable by default
```

### Better

```python id="6vyq2z"
m.x = pyo.Var(bounds=(-100.0, 100.0), initialize=0.0)
```

### Detect free variables

```python id="vq0bkt"
free_vars = []
for v in m.component_data_objects(pyo.Var, active=True):
    if not v.fixed and v.lb is None and v.ub is None:
        free_vars.append(v.name)

if free_vars:
    print("Free active variables:", free_vars)
```

### Detect huge fake-infinity bounds

```python id="9jmbfi"
huge_bound_vars = []
for v in m.component_data_objects(pyo.Var, active=True):
    lb = pyo.value(v.lb, exception=False) if v.lb is not None else None
    ub = pyo.value(v.ub, exception=False) if v.ub is not None else None
    if lb is not None and abs(lb) >= 1e19:
        huge_bound_vars.append((v.name, "lb", lb))
    if ub is not None and abs(ub) >= 1e19:
        huge_bound_vars.append((v.name, "ub", ub))
```

**Agent guidance**

```text id="n3psfz"
Use None for truly unbounded.
Use finite physical bounds when known.
Avoid fake infinities 1e20 / 1e30.
Scale variables before applying huge bounds.
```

---

## 7.12 Model sanity checker for Ipopt

```python id="0t6st1"
from __future__ import annotations

import math
import pyomo.environ as pyo


def ipopt_model_sanity_check(
    model,
    *,
    require_initial_values: bool = True,
    warn_free_vars: bool = True,
    huge_bound_threshold: float = 1e19,
):
    errors: list[str] = []
    warnings: list[str] = []

    # Objective checks
    active_objs = list(model.component_data_objects(pyo.Objective, active=True))
    if len(active_objs) == 0:
        errors.append("No active Objective found.")
    elif len(active_objs) > 1:
        errors.append(f"Multiple active Objective components found: {[o.name for o in active_objs]}")

    # Variable checks
    for v in model.component_data_objects(pyo.Var, active=True):
        if not v.fixed and (v.is_binary() or v.is_integer()):
            errors.append(f"Active discrete variable invalid for Ipopt: {v.name}")

        if require_initial_values and not v.fixed and v.value is None:
            warnings.append(f"Variable lacks initial value: {v.name}")

        val = pyo.value(v, exception=False)
        if val is not None:
            try:
                if not math.isfinite(float(val)):
                    errors.append(f"Nonfinite variable initial value: {v.name}={val}")
            except (TypeError, ValueError):
                errors.append(f"Non-numeric variable value: {v.name}={val!r}")

        lb = pyo.value(v.lb, exception=False) if v.lb is not None else None
        ub = pyo.value(v.ub, exception=False) if v.ub is not None else None

        if lb is not None and ub is not None and lb > ub:
            errors.append(f"Inconsistent bounds: {v.name}: lb={lb}, ub={ub}")

        if warn_free_vars and not v.fixed and lb is None and ub is None:
            warnings.append(f"Free active variable: {v.name}")

        if lb is not None and abs(lb) >= huge_bound_threshold:
            warnings.append(f"Huge lower bound may be treated as infinity by Ipopt: {v.name}: {lb}")

        if ub is not None and abs(ub) >= huge_bound_threshold:
            warnings.append(f"Huge upper bound may be treated as infinity by Ipopt: {v.name}: {ub}")

    # Constraint checks
    for c in model.component_data_objects(pyo.Constraint, active=True):
        lb = pyo.value(c.lower, exception=False) if c.lower is not None else None
        ub = pyo.value(c.upper, exception=False) if c.upper is not None else None

        if lb is not None and ub is not None and lb > ub:
            errors.append(f"Inconsistent constraint bounds: {c.name}: lb={lb}, ub={ub}")

        body = pyo.value(c.body, exception=False)
        if body is None:
            warnings.append(f"Constraint body not evaluable at current start: {c.name}")
        else:
            try:
                if not math.isfinite(float(body)):
                    errors.append(f"Constraint body evaluates nonfinite: {c.name}: {body}")
            except (TypeError, ValueError):
                errors.append(f"Constraint body nonnumeric at current start: {c.name}: {body!r}")

    # Objective evaluability
    for obj in active_objs:
        val = pyo.value(obj.expr, exception=False)
        if val is None:
            warnings.append(f"Objective not evaluable at current start: {obj.name}")
        else:
            try:
                if not math.isfinite(float(val)):
                    errors.append(f"Objective evaluates nonfinite: {obj.name}: {val}")
            except (TypeError, ValueError):
                errors.append(f"Objective nonnumeric at current start: {obj.name}: {val!r}")

    return errors, warnings
```

Usage:

```python id="ey5o8y"
errors, warnings = ipopt_model_sanity_check(m)

for msg in warnings:
    print("WARNING:", msg)

for msg in errors:
    print("ERROR:", msg)

if errors:
    raise RuntimeError("Model violates Ipopt construction contract.")
```

---

## 7.13 Pattern: robust Ipopt-ready model factory

```python id="4yxdiw"
import pyomo.environ as pyo


def build_smooth_nlp(data):
    m = pyo.ConcreteModel()

    m.I = pyo.Set(initialize=data["I"])

    m.target = pyo.Param(
        m.I,
        initialize=data["target"],
        mutable=True,
        within=pyo.Reals,
    )

    m.x = pyo.Var(
        m.I,
        domain=pyo.Reals,
        bounds=lambda m, i: data["bounds"][i],
        initialize=lambda m, i: data["x0"][i],
    )

    def residual_expr(m, i):
        # Smooth expression only
        return m.x[i] - m.target[i]

    m.residual = pyo.Expression(m.I, rule=residual_expr)

    m.obj = pyo.Objective(
        expr=sum(m.residual[i] ** 2 for i in m.I),
        sense=pyo.minimize,
    )

    m.norm_limit = pyo.Constraint(
        expr=sum(m.x[i] ** 2 for i in m.I) <= data["radius"] ** 2
    )

    errors, warnings = ipopt_model_sanity_check(m)
    if errors:
        raise RuntimeError(errors)

    return m
```

---

## 7.14 Repeated-solve pattern: mutable coefficients, fixed structure

```python id="8dm6a4"
m = build_smooth_nlp(base_data)

opt = pyo.SolverFactory("ipopt")
opt.options.update({
    "tol": 1e-8,
    "max_iter": 1000,
    "print_level": 0,
})

for scenario in scenarios:
    for i in m.I:
        m.target[i].set_value(scenario["target"][i])

    # optional warm-ish start from previous solution remains in Var.value
    res = opt.solve(m, tee=False)

    errors, warnings = ipopt_model_sanity_check(m, require_initial_values=False)
    if errors:
        raise RuntimeError(errors)

    print(scenario["name"], pyo.value(m.obj))
```

**Value case**

```text id="fx4imm"
Mutable Param repeated solves:
  no model reconstruction
  stable component identity
  stable NL structure if only coefficients/RHS values change
  previous solution remains available as next initialization
  compatible with APPSI-style efficient update workflows
```

---

## 7.15 Construction anti-pattern catalog

| Anti-pattern                           | Failure mode                                      | Replacement                                                               |
| -------------------------------------- | ------------------------------------------------- | ------------------------------------------------------------------------- |
| active `Binary` / `Integer` variables  | Ipopt solves continuous NLP, not discrete search  | relax/fix/use MIP/MINLP solver                                            |
| no variable initialization             | undefined nonlinear evaluation / poor convergence | initialize all nonlinear vars                                             |
| `math.sin(m.x)`                        | Python float coercion failure                     | `pyo.sin(m.x)`                                                            |
| `abs(m.x)` at active optimum           | nonsmooth derivative                              | epigraph or smooth approximation                                          |
| `max(m.x, m.y)`                        | Python comparison / nonsmooth                     | epigraph or smooth max                                                    |
| `log(m.x)` with `x` allowed 0          | domain error                                      | `bounds=(eps, None)`                                                      |
| `sqrt(m.x)` at 0                       | derivative singularity                            | lower bound away from zero                                                |
| multiple active objectives             | ambiguous solve target                            | deactivate/scalarize                                                      |
| unbounded variables by accident        | unstable/infeasible/unbounded NLP                 | physical bounds or explicit review                                        |
| mutable Param used to change index set | stale model topology                              | rebuild model or use APPSI structural updates carefully                   |
| arbitrary Python external function     | unsupported/non-differentiable                    | algebraic Pyomo expression or compiled external function with derivatives |

---

## 7.16 Agent-ready final checklist

```text id="ha1yey"
[ ] Use ConcreteModel for executable generated examples unless AbstractModel/data separation is required.
[ ] Declare all Ipopt decision variables as continuous domains.
[ ] Use NonNegativeReals or bounds=(0, None) for nonnegative continuous variables.
[ ] Do not leave nonlinear variables uninitialized.
[ ] Use fix()/unfix() for temporary subproblem fixing.
[ ] Use setlb()/setub()/bounds for dynamic bounds; validate lb <= ub.
[ ] Ensure exactly one active Objective.
[ ] Use sense=pyo.maximize or explicit negation consistently.
[ ] Use Constraint(expr=...), rule=..., or tuple/ranged constraints correctly.
[ ] Use pyo.inequality(lb, expr, ub) for ranged constraints.
[ ] Use mutable Param for coefficients/RHS values that change across repeated solves.
[ ] Do not use mutable Param to change algebraic structure.
[ ] Use pyo.sin/pyo.exp/pyo.log/pyo.sqrt, not Python math functions.
[ ] Guard log/sqrt/division domains with finite bounds and interior starts.
[ ] Avoid nonsmooth abs/max/min/floor/ceil/round in active NLP expressions.
[ ] Treat ExternalFunction as advanced compiled-function deployment, not ordinary Python callback modeling.
[ ] Run a model sanity check before Ipopt solve.
[ ] Use symbolic_solver_labels / keepfiles only for debugging or reproducibility artifacts.
```

[1]: https://coin-or.github.io/Ipopt/ "Ipopt: Documentation"
[2]: https://pyomo.readthedocs.io/en/latest/api/pyomo.core.base.var.Var.html "Var — Pyomo 6.10.1.dev0 documentation"
[3]: https://pyomo.readthedocs.io/en/stable/api/pyomo.core.base.var.VarData.html "VarData — Pyomo 6.10.0 documentation"
[4]: https://pyomo.readthedocs.io/en/6.8.0/pyomo_modeling_components/Objectives.html "Objectives — Pyomo 6.8.0 documentation"
[5]: https://pyomo.readthedocs.io/en/stable/explanation/modeling/math_programming/constraints.html "Constraints — Pyomo 6.10.0 documentation"
[6]: https://pyomo.readthedocs.io/en/6.8.0/pyomo_modeling_components/Parameters.html "Parameters — Pyomo 6.8.0 documentation"
[7]: https://pyomo.readthedocs.io/en/6.9.0/api/pyomo.contrib.appsi.solvers.ipopt.Ipopt.html "Ipopt — Pyomo 6.9.0 documentation"
[8]: https://pyomo.readthedocs.io/en/6.4.4/pyomo_modeling_components/Expressions.html "Expressions — Pyomo 6.4.4 documentation"
[9]: https://pyomo.readthedocs.io/en/6.8.2/api/pyomo.repn.plugins.nl_writer.NLWriter.html "NLWriter — Pyomo 6.8.2 documentation"
[10]: https://pyomo.readthedocs.io/en/latest/api/pyomo.core.base.external.ExternalFunction.html?utm_source=chatgpt.com "ExternalFunction — Pyomo 6.10.1.dev0 documentation"

# Ipopt Advanced — Section 8: derivatives and Hessian strategy

Style target: dense advanced technical catalog / agent-ready reference. 

## 8.0 Derivative-contract invariant

```text id="zx89oj"
Ipopt solve quality =
  correct function values
  correct first derivatives
  useful sparse Jacobian structure
  useful Hessian-of-Lagrangian information or a deliberate Hessian approximation policy
  evaluable derivatives at all iterates
  numerically scaled derivative magnitudes
```

For direct interfaces, Ipopt’s TNLP API requires the NLP dimensions and sparse derivative sizes, objective values, objective gradient, constraint values, constraint Jacobian structure/values, and Hessian-of-Lagrangian structure/values. In the standard Pyomo workflow, Pyomo writes an NL representation and the `ipopt` executable solves it through the AMPL/NL-style interface, so the agent normally controls derivative behavior through model expression quality and Ipopt options rather than implementing derivative callbacks. Ipopt’s command-line interface can solve `.nl` files directly, and Pyomo’s `NLWriter` writes models in NL format. ([COIN-OR][1])

---

## 8.1 Interface split: Pyomo `.nl` path versus direct-code path

### Pyomo + Ipopt executable path

```text id="nylv9n"
Pyomo algebraic expressions
→ NLWriter writes .nl
→ Ipopt executable reads .nl through ASL/AMPL-style interface
→ Ipopt obtains objective/constraint/derivative information from that interface
→ user configures derivative policy with Ipopt options
```

```python id="j2eufa"
import pyomo.environ as pyo

opt = pyo.SolverFactory("ipopt")
opt.options.update({
    "tol": 1e-8,
    "hessian_approximation": "exact",   # default; explicit for documentation
})
res = opt.solve(model, tee=True)
```

### Direct TNLP / C++ / C / callback path

```text id="826fk6"
User implementation must provide:
  get_nlp_info
  get_bounds_info
  get_starting_point
  eval_f
  eval_grad_f
  eval_g
  eval_jac_g
  eval_h
  finalize_solution
```

Ipopt’s TNLP reference shows `get_nlp_info` returning number of variables, number of constraints, nonzeros in the constraint Jacobian, nonzeros in the Hessian, and sparse index style; it also defines `eval_f`, `eval_grad_f`, `eval_g`, `eval_jac_g`, and `eval_h` as the function/derivative callback surface. ([COIN-OR][1])

**Agent rule**

```text id="5d8b55"
Pyomo agent:
  write smooth symbolic Pyomo expressions
  avoid external black-box calls unless supported
  tune Ipopt derivative/Hessian options

Direct-code agent:
  implement exact callbacks
  maintain fixed sparse structures
  verify derivatives with derivative checker
  provide lower-triangular Hessian-of-Lagrangian structure/values
```

---

## 8.2 Ipopt derivative information: direct-interface contract

### Dimensions and sparse structures

```text id="0r1skd"
get_nlp_info(...)
  n            number of variables
  m            number of constraints
  nnz_jac_g    number of nonzeros in ∂g/∂x
  nnz_h_lag    number of nonzeros in Hessian of Lagrangian
  index_style  C_STYLE 0-based or FORTRAN_STYLE 1-based
```

Ipopt uses `get_nlp_info` values to allocate arrays that later derivative callbacks must fill; incorrect nonzero counts can cause difficult memory bugs in direct interfaces. ([COIN-OR][1])

### Objective value and gradient

```text id="fvf3ej"
eval_f(x)        → f(x)
eval_grad_f(x)   → ∇f(x)
```

`eval_f` returns the scalar objective value, and `eval_grad_f` fills an array containing gradient values in the same order as the variable vector. ([COIN-OR][1])

### Constraint values

```text id="rcv9qk"
eval_g(x) → g(x)
```

`eval_g` returns the constraint body vector `g(x)` and should not add or subtract constraint lower/upper bound values. ([COIN-OR][1])

### Jacobian structure and values

```text id="k6itwp"
first eval_jac_g call:
  x      = NULL
  values = NULL
  iRow, jCol filled with sparse structure

later eval_jac_g calls:
  iRow, jCol = NULL
  values filled in same order as structure
```

Ipopt’s `eval_jac_g` asks first for the row/column sparsity pattern and later for numeric values in the same order; the Jacobian entry is derivative of constraint `g_i` with respect to variable `x_j`. ([COIN-OR][1])

### Hessian-of-Lagrangian structure and values

```text id="og0gpi"
H(x, λ, σ_f) =
  σ_f ∇²f(x) + Σ_i λ_i ∇²g_i(x)
```

```text id="alfs73"
first eval_h call:
  x, lambda, values = NULL
  iRow, jCol filled with sparse lower-triangular structure

later eval_h calls:
  iRow, jCol = NULL
  values filled in same order as structure
```

Ipopt’s `eval_h` uses the Hessian of the Lagrangian, i.e. objective Hessian scaled by `obj_factor` plus multiplier-weighted constraint Hessians; because this matrix is symmetric, Ipopt expects only lower-triangular entries. A default `eval_h` implementation exists for users who select quasi-Newton approximations and do not need exact second derivatives. ([COIN-OR][1])

---

## 8.3 Pyomo NL writer: derivative-relevant behavior

### Key NL writer controls

```python id="4fg21p"
from pyomo.contrib.solver.solvers.ipopt import Ipopt

solver = Ipopt()
solver.config.writer_config.symbolic_solver_labels = True
solver.config.writer_config.scale_model = True
solver.config.writer_config.export_defined_variables = True
solver.config.writer_config.linear_presolve = True

res = solver.solve(
    model,
    tee=True,
    solver_options={"tol": 1e-8},
)
```

Pyomo’s `NLWriter` writes a concrete model in NL format; it can write `.row` and `.col` files when `symbolic_solver_labels=True`, use model scaling from the `scaling_factor` suffix when `scale_model=True`, export `Expression` objects as defined variables when `export_defined_variables=True`, and perform basic linear presolve by variable elimination when `linear_presolve=True`. ([Pyomo Documentation][2])

### Deterministic/symbolic export controls

```python id="4tyb7l"
res = opt.solve(
    model,
    tee=True,
    keepfiles=True,
    symbolic_solver_labels=True,
)
```

### New-interface writer config

```python id="7jlp5z"
from pyomo.contrib.solver.solvers.ipopt import Ipopt

opt = Ipopt()
opt.config.writer_config.symbolic_solver_labels = True
opt.config.writer_config.linear_presolve = False
opt.config.writer_config.scale_model = True

res = opt.solve(
    model,
    tee=True,
    solver_options={
        "print_user_options": "yes",
        "tol": 1e-8,
    },
)
```

Pyomo’s redesigned solver-interface docs state that the new Ipopt interface exposes writer capabilities through `writer_config`, including `symbolic_solver_labels`, `scale_model`, `export_defined_variables`, and `linear_presolve`; by default, both `linear_presolve` and `scale_model` are enabled in the displayed configuration. ([Pyomo Documentation][3])

### Agent implications

```text id="zc69mz"
symbolic_solver_labels=True:
  better derivative/debug row/column traceability
  larger files and slower writing on large models

linear_presolve=True:
  may reduce model size
  can change row/column mapping and derivative structure
  disable for exact row/column reproducibility debugging

scale_model=True:
  applies scaling_factor suffix to NL representation
  useful for derivative magnitude conditioning
  can complicate comparison to unscaled hand residuals

export_defined_variables=True:
  exports Expression objects as defined variables
  can improve file structure/readability
  may affect NL structure and symbol mapping
```

---

## 8.4 Exact Hessian strategy

### Syntax: explicit exact Hessian

```python id="8u6yas"
opt = pyo.SolverFactory("ipopt")
opt.options.update({
    "hessian_approximation": "exact",
})
res = opt.solve(model, tee=True)
```

Ipopt’s `hessian_approximation` option controls what Hessian-of-Lagrangian information is used; the default is `exact`, meaning second derivatives provided by the NLP are used. ([COIN-OR][4])

### When exact Hessian is preferred

```text id="rmhfhq"
Use exact Hessian when:
  Pyomo algebraic model has smooth standard expressions
  derivative generation succeeds
  Hessian sparsity is not catastrophically dense
  high-accuracy KKT solution required
  nonlinear equality constraints dominate
  warm-start / local convergence quality matters
  iteration count more important than per-iteration derivative cost
```

### Value case

```text id="8ggz12"
exact Hessian:
  Newton-like local convergence
  fewer major iterations
  stronger curvature information
  better behavior for highly constrained nonlinear systems
  preferred baseline for well-posed Pyomo NLPs
```

### Failure signals

```text id="q1sh34"
exact Hessian problematic when:
  Hessian evaluation is very expensive
  Hessian is extremely dense
  external function Hessians unavailable/incorrect
  memory pressure from KKT factorization dominates
  derivative checker flags second-order errors
  invalid derivative numbers appear
```

### Derivative NaN/Inf guard

```python id="7zwynm"
opt.options.update({
    "check_derivatives_for_naninf": "yes",
    "print_level": 7,
})
```

`check_derivatives_for_naninf=yes` causes Ipopt to error if invalid numbers are detected in constraint Jacobians or the Lagrangian Hessian; if triggered, matrices are written at detailed print level, which can generate large output. ([COIN-OR][4])

---

## 8.5 Limited-memory Hessian strategy

### Syntax: basic limited-memory

```python id="c99z4e"
opt = pyo.SolverFactory("ipopt")
opt.options.update({
    "hessian_approximation": "limited-memory",
})
res = opt.solve(model, tee=True)
```

`hessian_approximation=limited-memory` tells Ipopt to use a limited-memory quasi-Newton approximation rather than exact second derivatives; the default alternative is `exact`. ([COIN-OR][4])

### Syntax: tuned limited-memory profile

```python id="oz4kei"
opt.options.update({
    "hessian_approximation": "limited-memory",
    "limited_memory_update_type": "bfgs",
    "limited_memory_max_history": 20,
    "limited_memory_initialization": "scalar1",
})
```

`limited_memory_max_history` controls how many recent iterations contribute to the approximation, defaulting to 6; `limited_memory_update_type` defaults to `bfgs`, while `sr1` is also listed but explicitly noted as not working well; `limited_memory_initialization` controls the initial diagonal approximation strategy. ([COIN-OR][4])

### When to use limited-memory

```text id="w7b5hn"
Use hessian_approximation=limited-memory when:
  second derivatives unavailable
  external functions lack reliable Hessians
  exact Hessian generation/evaluation too costly
  Hessian is dense but Jacobian remains sparse
  memory pressure severe
  very large model with many variables and moderate accuracy target
  early-stage feasibility/model-development solve
```

### Tradeoffs

| Dimension                     |                       Exact Hessian |                             Limited-memory |
| ----------------------------- | ----------------------------------: | -----------------------------------------: |
| Second derivative requirement |                                 yes |                    no exact Hessian values |
| Per-iteration derivative cost |                              higher |                                      lower |
| Major iterations              |                       usually fewer |                                 often more |
| Local convergence             |                            stronger |                      weaker / quasi-Newton |
| Memory footprint              |                         can be high |                              usually lower |
| Robustness on constrained NLP | often better if derivatives correct |  can degrade on difficult equality systems |
| Best use                      |          final solve, high accuracy | huge models, missing Hessians, prototyping |

### Agent rule

```text id="3653i3"
Default Pyomo NLP:
  exact Hessian

If exact Hessian fails or is too expensive:
  limited-memory + derivative checker first-order + benchmark

Do not use limited-memory to hide nonsmooth/incorrect model algebra.
```

---

## 8.6 Limited-memory subspace controls

### Nonlinear-variable subspace

```python id="fjbhks"
opt.options.update({
    "hessian_approximation": "limited-memory",
    "hessian_approximation_space": "nonlinear-variables",
})
```

### All-variable subspace

```python id="izwbws"
opt.options.update({
    "hessian_approximation": "limited-memory",
    "hessian_approximation_space": "all-variables",
})
```

`hessian_approximation_space` defaults to `nonlinear-variables`, meaning the approximation is only in the space of nonlinear variables; `all-variables` approximates in all variable space excluding slacks. ([COIN-OR][4])

### `num_linear_variables`

```python id="ukxxmw"
opt.options.update({
    "hessian_approximation": "limited-memory",
    "num_linear_variables": 100,
})
```

When Hessian approximation is used, `num_linear_variables` tells Ipopt that the first variables are linear and should not be included in the Hessian approximation; the option is ignored if the TNLP implements nonlinear-variable metadata. ([COIN-OR][4])

**Agent caution**

```text id="0d00u8"
num_linear_variables is ordering-sensitive.
In Pyomo/NL writer workflows, variable ordering is writer-controlled.
Do not set num_linear_variables unless you own and verify ordering.
Prefer default nonlinear-variable detection / NL metadata behavior.
```

---

## 8.7 First-derivative approximation options

### Jacobian finite-difference values

```python id="cjdyye"
opt.options.update({
    "jacobian_approximation": "finite-difference-values",
    "findiff_perturbation": 1e-7,
})
```

### Gradient finite-difference values

```python id="vczxj6"
opt.options.update({
    "gradient_approximation": "finite-difference-values",
    "findiff_perturbation": 1e-7,
})
```

Ipopt’s `jacobian_approximation` default is `exact`; `finite-difference-values` uses user-provided Jacobian structure but computes values by finite differences. `gradient_approximation` similarly defaults to exact and can compute objective gradient values by finite differences. `findiff_perturbation` controls the relative perturbation size and defaults to `1e-7`. ([COIN-OR][4])

### Use cases

```text id="s70346"
Use finite-difference derivative values only when:
  direct-code callback derivative values suspected wrong
  external functions provide structure but unreliable derivatives
  temporary diagnostic comparison needed
  exact first derivatives unavailable but sparsity structure known
```

### Tradeoffs

```text id="jwut8q"
finite-difference values:
  slower
  noise-sensitive
  perturbation-sensitive
  inaccurate near bounds / nonsmooth points
  still requires useful sparsity structure for Jacobian
  not a substitute for smooth model formulation
```

### Agent anti-default

```python id="er9lff"
# BAD as a generic Pyomo+Ipopt setting:
opt.options["jacobian_approximation"] = "finite-difference-values"
opt.options["gradient_approximation"] = "finite-difference-values"
```

**Agent rule**

```text id="drc24a"
For normal Pyomo algebraic models:
  keep jacobian_approximation=exact
  keep gradient_approximation=exact

For debugging:
  compare exact derivatives against derivative checker before switching to finite differences.
```

---

## 8.8 Derivative checker: correctness validation layer

### First-order derivative checker

```python id="wbgliy"
opt.options.update({
    "derivative_test": "first-order",
    "derivative_test_print_all": "yes",
    "derivative_test_tol": 1e-4,
    "derivative_test_perturbation": 1e-8,
    "max_iter": 0,
    "print_level": 7,
})
```

### Second-order derivative checker

```python id="7dicdh"
opt.options.update({
    "derivative_test": "second-order",
    "derivative_test_print_all": "yes",
    "derivative_test_tol": 1e-4,
    "derivative_test_perturbation": 1e-8,
    "max_iter": 0,
    "print_level": 7,
})
```

Ipopt’s derivative checker runs a finite-difference test before optimization; `first-order` checks objective and constraint first derivatives, `second-order` checks first and second derivatives, perturbation defaults to about `1e-8`, and `derivative_test_print_all=yes` prints all estimated derivative information rather than only suspicious entries. ([COIN-OR][5])

### Agent use policy

```text id="n6xe53"
Run derivative checker when:
  using ExternalFunction
  direct TNLP/cyipopt callbacks implemented manually
  derivative-related termination failure
  INVALID_NUMBER_DETECTED
  Restoration_Failed with no obvious infeasibility
  new nonlinear model template generated by an LLM
```

### Cost policy

```text id="dg8rd2"
derivative_test=second-order:
  expensive
  run on small instances
  run with max_iter=0 for structural validation
  avoid on full production-scale instances
```

---

## 8.9 Constant derivative options for linear/QP structure

### Syntax

```python id="rqm42j"
opt.options.update({
    "grad_f_constant": "yes",
    "jac_c_constant": "yes",
    "jac_d_constant": "yes",
    "hessian_constant": "yes",
})
```

`grad_f_constant=yes` causes Ipopt to request the objective gradient only once when the objective is linear; `jac_c_constant=yes` and `jac_d_constant=yes` do the same for equality and inequality constraint Jacobians when constraints are linear; `hessian_constant=yes` tells Ipopt to request the Hessian only once for a QP with quadratic objective and linear constraints. ([COIN-OR][4])

### Agent use

```text id="cprz75"
Use only when algebraic structure is truly constant:
  linear objective      -> grad_f_constant=yes
  linear equalities     -> jac_c_constant=yes
  linear inequalities   -> jac_d_constant=yes
  QP                   -> hessian_constant=yes

Do not set:
  if coefficients depend on variables
  if mutable Param changes solve-to-solve but derivative wrt variables remains same? safe only per solve if structure/coefs loaded before solve
  if uncertain; wrong constant-derivative flags can corrupt solve
```

---

## 8.10 Sparse structure: why it dominates performance

### Core sparse contract

```text id="a5s72c"
Jacobian structure:
  row/column nonzero pattern of ∂g/∂x
  requested once in direct interfaces
  numeric values filled repeatedly

Hessian structure:
  lower-triangular nonzero pattern of ∇²_xx L(x, λ)
  requested once in direct interfaces
  numeric values filled repeatedly
```

Ipopt’s TNLP API requests Jacobian row/column structure once and later values in the same order; it does the same for the Hessian and expects only lower-triangular entries because the Hessian is symmetric. ([COIN-OR][1])

### Sparsity quality effects

```text id="taz74i"
good sparsity:
  smaller KKT matrix
  less fill-in during factorization
  lower memory pressure
  faster linear solves
  more robust numerical pivots
  easier derivative debugging

bad sparsity:
  dense Jacobian/Hessian blocks
  large KKT factorization memory
  slow iterations despite few variables
  linear solver failures
  unnecessary nonlinear coupling
```

### Pyomo expression anti-pattern: dense accidental coupling

```python id="jdmk7s"
# BAD: every constraint depends on every variable
m.c = pyo.Constraint(
    m.I,
    rule=lambda m, i: sum(m.x[j] for j in m.J) >= demand[i],
)
```

### Sparse alternative

```python id="tensn2"
# GOOD: only neighborhood variables appear in each constraint
m.c = pyo.Constraint(
    m.I,
    rule=lambda m, i: sum(m.x[j] for j in neighbors[i]) >= demand[i],
)
```

### Hessian sparsity anti-pattern

```python id="ma815a"
# BAD: dense quadratic objective
m.obj = pyo.Objective(
    expr=sum(Q[i, j] * m.x[i] * m.x[j] for i in m.I for j in m.I)
)
```

### Sparse quadratic objective

```python id="ifxld6"
# GOOD: only nonzero Q entries
m.QNZ = pyo.Set(dimen=2, initialize=[(i, j) for (i, j), val in Q.items() if val != 0])
m.obj = pyo.Objective(
    expr=sum(Q[i, j] * m.x[i] * m.x[j] for i, j in m.QNZ)
)
```

---

## 8.11 External functions and derivative risk

### ExternalFunction risk

```python id="grsrbl"
m.f_ext = pyo.ExternalFunction(library="libmyfuncs.so", function="smooth_f")
m.obj = pyo.Objective(expr=m.f_ext(m.x))
```

Pyomo’s `ExternalFunction` lets users embed non-algebraic functions in expressions, but the docs warn that expressibility does not imply solvability; the ASL interface supports external functions for general nonlinear solvers compiled against it, but only compiled libraries through `AMPLExternalFunction`. ([Pyomo Documentation][6])

### Agent policy

```text id="8go579"
Preferred:
  native Pyomo algebraic expression

ExternalFunction allowed only with:
  compiled library
  smooth function over all iterates
  derivative support compatible with solver interface
  derivative checker on small instance
  controlled deployment path / ABI

Never:
  arbitrary Python callback hidden inside objective
  scipy/numpy function called with Var objects
  ML model Python predict() inside Objective
```

---

## 8.12 Hessian strategy decision table

| Model / situation                           | Recommended Hessian policy                        | Rationale                                                    |
| ------------------------------------------- | ------------------------------------------------- | ------------------------------------------------------------ |
| Standard smooth Pyomo NLP                   | `hessian_approximation=exact`                     | best local convergence                                       |
| Highly constrained nonlinear equality model | `exact`                                           | curvature critical                                           |
| Very large model, Hessian memory issue      | `limited-memory`                                  | reduce second-derivative burden                              |
| ExternalFunction with unreliable Hessian    | `limited-memory` + derivative checker first-order | avoid bad second derivatives                                 |
| Direct TNLP Hessian not implemented         | `limited-memory`                                  | Ipopt default `eval_h` can be omitted when quasi-Newton used |
| Early feasibility debugging                 | `limited-memory` acceptable                       | quicker iteration                                            |
| Final high-accuracy solve                   | `exact` if possible                               | stronger KKT convergence                                     |
| Noisy/nonsmooth model                       | neither solves root issue                         | reformulate; Ipopt requires smoothness                       |

---

## 8.13 Option bundles

### Exact-Hessian audit bundle

```python id="5c6o8q"
opt.options.update({
    "hessian_approximation": "exact",
    "check_derivatives_for_naninf": "yes",
    "print_user_options": "yes",
    "print_level": 5,
})
```

### Limited-memory large-model bundle

```python id="z5tnql"
opt.options.update({
    "hessian_approximation": "limited-memory",
    "limited_memory_update_type": "bfgs",
    "limited_memory_max_history": 10,
    "hessian_approximation_space": "nonlinear-variables",
})
```

### First-derivative finite-difference diagnostic bundle

```python id="txm4ov"
opt.options.update({
    "jacobian_approximation": "finite-difference-values",
    "gradient_approximation": "finite-difference-values",
    "findiff_perturbation": 1e-7,
    "print_user_options": "yes",
})
```

### Derivative-check-only bundle

```python id="z89ch7"
opt.options.update({
    "derivative_test": "second-order",
    "derivative_test_print_all": "yes",
    "derivative_test_tol": 1e-4,
    "derivative_test_perturbation": 1e-8,
    "max_iter": 0,
    "print_level": 7,
})
```

---

## 8.14 Pyomo syntax: compare exact versus limited-memory

```python id="yd2s7w"
import pyomo.environ as pyo
from pyomo.opt import TerminationCondition


def solve_ipopt_with_hessian_policy(model, policy: str):
    m = model.clone()

    opt = pyo.SolverFactory("ipopt")
    opt.options.update({
        "tol": 1e-8,
        "max_iter": 1000,
        "print_level": 5,
        "print_user_options": "yes",
    })

    if policy == "exact":
        opt.options["hessian_approximation"] = "exact"
    elif policy == "limited-memory":
        opt.options.update({
            "hessian_approximation": "limited-memory",
            "limited_memory_update_type": "bfgs",
            "limited_memory_max_history": 10,
        })
    else:
        raise ValueError(policy)

    res = opt.solve(m, tee=True, load_solutions=False)

    return {
        "policy": policy,
        "status": str(res.solver.status),
        "termination_condition": str(res.solver.termination_condition),
        "ok": res.solver.termination_condition == TerminationCondition.optimal,
        "results": res,
        "model": m,
    }


runs = [
    solve_ipopt_with_hessian_policy(model, "exact"),
    solve_ipopt_with_hessian_policy(model, "limited-memory"),
]
```

**Agent evaluation metrics**

```text id="jh6d74"
compare:
  termination condition
  objective value
  constraint residuals
  iteration count
  wall time
  memory if measured externally
  restoration/regularization frequency in log
```

---

## 8.15 Direct-interface pseudo-code contract

```cpp id="tjrsz4"
// Direct Ipopt TNLP conceptual skeleton.
// Not Pyomo code.

bool get_nlp_info(
    Index& n,
    Index& m,
    Index& nnz_jac_g,
    Index& nnz_h_lag,
    IndexStyleEnum& index_style
);

bool get_bounds_info(
    Index n,
    Number* x_l,
    Number* x_u,
    Index m,
    Number* g_l,
    Number* g_u
);

bool get_starting_point(
    Index n,
    bool init_x,
    Number* x,
    bool init_z,
    Number* z_L,
    Number* z_U,
    Index m,
    bool init_lambda,
    Number* lambda
);

bool eval_f(Index n, const Number* x, bool new_x, Number& obj_value);

bool eval_grad_f(Index n, const Number* x, bool new_x, Number* grad_f);

bool eval_g(Index n, const Number* x, bool new_x, Index m, Number* g);

bool eval_jac_g(
    Index n,
    const Number* x,
    bool new_x,
    Index m,
    Index nele_jac,
    Index* iRow,
    Index* jCol,
    Number* values
);

bool eval_h(
    Index n,
    const Number* x,
    bool new_x,
    Number obj_factor,
    Index m,
    const Number* lambda,
    bool new_lambda,
    Index nele_hess,
    Index* iRow,
    Index* jCol,
    Number* values
);
```

**Direct-agent correctness constraints**

```text id="afy98x"
[ ] n, m, nnz_jac_g, nnz_h_lag exactly correct.
[ ] Jacobian structure immutable across solve.
[ ] Hessian lower-triangular structure immutable across solve.
[ ] Jacobian values match declared structure order.
[ ] Hessian values match declared structure order.
[ ] eval_g returns raw g(x), not residuals against bounds.
[ ] eval_h returns obj_factor * ∇²f + Σ lambda_i * ∇²g_i.
[ ] all callbacks return false on evaluation failure rather than writing NaN/Inf.
[ ] derivative checker run before trusting solve.
```

---

## 8.16 Sanity checker for Pyomo derivative-risk patterns

```python id="av59d8"
import pyomo.environ as pyo
from pyomo.core.expr.visitor import identify_variables


def ipopt_derivative_risk_report(model):
    report = {
        "active_objectives": [],
        "active_constraints": 0,
        "external_functions_present": [],
        "uninitialized_variables_in_active_exprs": [],
        "free_variables_in_active_exprs": [],
    }

    active_exprs = []

    for obj in model.component_data_objects(pyo.Objective, active=True):
        report["active_objectives"].append(obj.name)
        active_exprs.append((obj.name, obj.expr))

    for con in model.component_data_objects(pyo.Constraint, active=True):
        report["active_constraints"] += 1
        active_exprs.append((con.name, con.body))

    seen_uninit = set()
    seen_free = set()

    for expr_name, expr in active_exprs:
        for var in identify_variables(expr, include_fixed=False):
            if var.value is None and var.name not in seen_uninit:
                report["uninitialized_variables_in_active_exprs"].append((expr_name, var.name))
                seen_uninit.add(var.name)

            if var.lb is None and var.ub is None and var.name not in seen_free:
                report["free_variables_in_active_exprs"].append((expr_name, var.name))
                seen_free.add(var.name)

    # ExternalFunction detection is Pyomo-version-sensitive; this placeholder keeps
    # generated agents from making false guarantees.
    # Use expression tree visitors specific to your Pyomo version for full detection.

    return report
```

---

## 8.17 Anti-pattern catalog

```text id="4pmg0u"
BAD:
  hessian_approximation=limited-memory as universal default.

GOOD:
  exact first; limited-memory for explicit cost/memory/missing-Hessian reason.

BAD:
  jacobian_approximation=finite-difference-values for normal Pyomo algebraic model.

GOOD:
  exact Jacobian; derivative checker for diagnostics.

BAD:
  ExternalFunction wrapping a Python callback and assuming Ipopt can differentiate it.

GOOD:
  compiled AMPL external function with derivative support, or algebraic expression.

BAD:
  Dense objective sum over all i,j when Q is sparse.

GOOD:
  sum only over nonzero pairs.

BAD:
  manually set num_linear_variables with Pyomo NL writer ordering unverified.

GOOD:
  leave default or inspect `.col`/NL writer ordering before advanced tuning.

BAD:
  ignore derivative checker warnings due to “solver still returned solution.”

GOOD:
  treat derivative warnings as model/callback defects until disproven.
```

---

## 8.18 Final checklist

```text id="4gbyox"
[ ] Standard Pyomo model uses symbolic Pyomo expressions, not Python black-box math.
[ ] NL writer path selected intentionally: classic SolverFactory or contrib Ipopt.
[ ] symbolic_solver_labels enabled for derivative/debug artifact generation.
[ ] linear_presolve disabled only when row/column reproducibility matters.
[ ] scaling_factor suffix / scale_model considered for badly scaled derivatives.
[ ] Exact Hessian used as default for smooth algebraic Pyomo NLP.
[ ] limited-memory used only with explicit cost/memory/Hessian-availability reason.
[ ] finite-difference Jacobian/gradient values used only as diagnostic fallback.
[ ] findiff_perturbation tuned only after understanding scale and bounds.
[ ] derivative_test run for direct callbacks, external functions, or suspicious solves.
[ ] check_derivatives_for_naninf enabled during derivative debugging.
[ ] Sparse Jacobian/Hessian structure preserved by modeling pattern.
[ ] Dense accidental coupling removed from constraints/objective.
[ ] Direct-interface callbacks provide correct dimensions, structures, values, and lower-triangle Hessian.
[ ] Solver logs compared for exact versus limited-memory policies before deployment.
```

[1]: https://coin-or.github.io/Ipopt/classIpopt_1_1TNLP.html "Ipopt: Ipopt::TNLP Class Reference"
[2]: https://pyomo.readthedocs.io/en/stable/api/pyomo.repn.plugins.nl_writer.NLWriter.html "NLWriter — Pyomo 6.10.0 documentation"
[3]: https://pyomo.readthedocs.io/en/stable/explanation/experimental/solvers.html "Future Solver Interface Changes — Pyomo 6.10.0 documentation"
[4]: https://coin-or.github.io/Ipopt/OPTIONS.html "Ipopt: Ipopt Options"
[5]: https://coin-or.github.io/Ipopt/SPECIALS.html "Ipopt: Special Features"
[6]: https://pyomo.readthedocs.io/en/latest/api/pyomo.core.base.external.ExternalFunction.html "ExternalFunction — Pyomo 6.10.1.dev0 documentation"

# Ipopt Advanced — Section 9: derivative checker and model debugging

Style target: dense advanced technical catalog / agent-ready reference. 

## 9.0 Derivative-checker invariant

```text id="69qe4e"
Ipopt derivative checker =
  finite-difference audit
  executed before optimization starts
  evaluated at user-provided starting point
  compares solver-supplied derivatives against finite-difference estimates
  can test first derivatives or first + second derivatives
  intended for debugging, not production solving
```

Ipopt’s derivative checker is a finite-difference test run before the optimization starts. `derivative_test=first-order` checks objective-gradient and constraint-Jacobian derivatives; `derivative_test=second-order` checks first and second derivatives; `derivative_test=none` is the default. The finite-difference perturbation is controlled by `derivative_test_perturbation`, and suspicious entries are reported when relative deviation exceeds `derivative_test_tol`. ([coin-or.github.io][1])

---

## 9.1 When derivative checking matters in Pyomo

### Normal Pyomo algebraic model

```text id="kesp04"
Pyomo algebraic expressions
→ NL writer
→ Ipopt / ASL derivative evaluation
```

For ordinary Pyomo expressions built from supported algebraic operators, derivative defects usually indicate one of:

```text id="ihoqkm"
nonsmooth expression at starting point
undefined expression near finite-difference perturbation
bad external function
bad scaling causing finite-difference noise
bad variable initialization
incorrect compiled external-function derivative implementation
unsupported expression route
```

### Direct-code / callback model

```text id="3hlk1q"
C++ TNLP / C / cyipopt / custom interface:
  derivative checker is mandatory before trusting solve result
```

Direct interfaces must provide objective values, objective gradients, constraint values, Jacobian structure/values, and Hessian structure/values; derivative checker detects many implementation defects but does not prove global correctness over all points. Ipopt’s derivative checker docs explicitly warn that derivative implementation mistakes are easy and position the checker as a convenient pre-solve finite-difference audit. ([coin-or.github.io][1])

---

## 9.2 Pyomo option syntax: derivative checker

### First-order derivative check

```python id="7hwmr4"
import pyomo.environ as pyo

opt = pyo.SolverFactory("ipopt")
opt.options.update({
    "derivative_test": "first-order",
    "derivative_test_tol": 1e-4,
    "derivative_test_perturbation": 1e-8,
    "derivative_test_print_all": "yes",
    "max_iter": 0,
    "print_level": 7,
})

results = opt.solve(model, tee=True)
```

### Second-order derivative check

```python id="y1dz97"
opt = pyo.SolverFactory("ipopt")
opt.options.update({
    "derivative_test": "second-order",
    "derivative_test_tol": 1e-4,
    "derivative_test_perturbation": 1e-8,
    "derivative_test_print_all": "yes",
    "max_iter": 0,
    "print_level": 7,
})

results = opt.solve(model, tee=True)
```

### Only second-order derivative check

```python id="d4jodm"
opt.options.update({
    "derivative_test": "only-second-order",
    "derivative_test_print_all": "yes",
    "max_iter": 0,
})
```

Ipopt’s option reference lists `derivative_test` values `none`, `first-order`, `second-order`, and `only-second-order`; `derivative_test_perturbation` defaults to `1e-8`; `derivative_test_tol` defaults to `1e-4`; `derivative_test_print_all` defaults to `no` and accepts `yes` / `no`. ([coin-or.github.io][2])

---

## 9.3 `ipopt.opt` syntax

```text id="sceodj"
# ipopt.opt

# First-derivative finite-difference audit
derivative_test first-order

# Relative deviation threshold for warnings
derivative_test_tol 1e-4

# Relative finite-difference perturbation
derivative_test_perturbation 1e-8

# Print every checked derivative, not only suspicious entries
derivative_test_print_all yes

# Run checker only; do not optimize
max_iter 0

# Enough log detail for debugging
print_level 7
```

Ipopt option files use `option_name value` per line with `#` comments; option values are typed as Number, Integer, or String, so derivative-test toggles such as `derivative_test_print_all` should be written as `yes` / `no`, not Python booleans. ([coin-or.github.io][3])

---

## 9.4 Direct `.nl` command-line syntax

```bash id="da4t26"
ipopt model.nl -AMPL \
  derivative_test=first-order \
  derivative_test_tol=1e-4 \
  derivative_test_perturbation=1e-8 \
  derivative_test_print_all=yes \
  max_iter=0 \
  print_level=7
```

Equivalent file-based run:

```bash id="jczy00"
cat > ipopt.opt <<'EOF'
derivative_test second-order
derivative_test_tol 1e-4
derivative_test_perturbation 1e-8
derivative_test_print_all yes
max_iter 0
print_level 7
EOF

ipopt model.nl -AMPL
```

---

## 9.5 Option semantics: exact agent contract

| Option                         |    Type | Default | Meaning                                                                   | Agent guidance                                              |
| ------------------------------ | ------: | ------: | ------------------------------------------------------------------------- | ----------------------------------------------------------- |
| `derivative_test`              |  String |  `none` | enable finite-difference derivative checker                               | `first-order` first; `second-order` after first-order clean |
| `derivative_test_tol`          |  Number |  `1e-4` | relative deviation threshold for marking derivative wrong                 | loosen/tighten only after scale/perturbation review         |
| `derivative_test_perturbation` |  Number |  `1e-8` | relative finite-difference perturbation of variable entries               | adjust for scale/noise; default usually good                |
| `derivative_test_print_all`    |  String |    `no` | print all derivative comparisons instead of only suspicious ones          | use `yes` in debugging, `no` for shorter logs               |
| `derivative_test_first_index`  | Integer |    `-2` | start derivative test from later variable/constraint index                | use to isolate large models                                 |
| `point_perturbation_radius`    |  Number |    `10` | maximum perturbation for evaluation point when random perturbation needed | rarely tune                                                 |

`derivative_test_first_index=-2` means all derivatives are checked; otherwise, for first-order tests it indicates the first variable index, and for second-order tests the first constraint index, with `-1` referring to the objective Hessian. ([coin-or.github.io][2])

---

## 9.6 Recommended debug workflow

### Stage 1: make a small instance

```text id="2r25f4"
full production model:
  100k variables, 200k constraints

derivative-check instance:
  10–100 variables
  10–100 constraints
  same algebraic patterns
  representative variable bounds/domains
  representative external functions
```

Ipopt’s documentation states second derivatives are finite-difference approximations of first derivatives, so first derivative errors should be corrected before debugging second derivatives; it also explicitly recommends debugging a small problem instance because finite-difference checks are expensive. ([coin-or.github.io][1])

### Stage 2: first-order check

```python id="6vs6l3"
DERIVATIVE_CHECK_FIRST = {
    "derivative_test": "first-order",
    "derivative_test_tol": 1e-4,
    "derivative_test_perturbation": 1e-8,
    "derivative_test_print_all": "yes",
    "max_iter": 0,
    "print_level": 7,
}
```

### Stage 3: fix first-order defects

```text id="ww3hlc"
fix order:
  missing Jacobian sparsity entries
  wrong Jacobian values
  wrong objective gradient values
  invalid finite-difference domains
  external-function derivative bugs
```

### Stage 4: second-order check

```python id="x4m8pq"
DERIVATIVE_CHECK_SECOND = {
    "derivative_test": "second-order",
    "derivative_test_tol": 1e-4,
    "derivative_test_perturbation": 1e-8,
    "derivative_test_print_all": "yes",
    "max_iter": 0,
    "print_level": 7,
}
```

### Stage 5: solve normally

```python id="nizwzt"
SOLVE_NORMAL = {
    "derivative_test": "none",
    "tol": 1e-8,
    "max_iter": 1000,
}
```

---

## 9.7 Output anatomy: first-order checker

Typical first-order output shape:

```text id="k1qdm9"
Starting derivative checker.

* grad_f[          2] = -6.5159999999999991e+02    ~ -6.5559997134793468e+02  [ 6.101e-03]
* jac_g [    4,    4] =  0.0000000000000000e+00    ~  2.2160643690464592e-02  [ 2.216e-02]
* jac_g [    4,    5] =  1.3798494268463347e+01 v  ~  1.3776333629422766e+01  [ 1.609e-03]
* jac_g [    6,    7] =  1.4776333636790881e+01 v  ~  1.3776333629422766e+01  [ 7.259e-02]

Derivative checker detected 4 error(s).
```

Ipopt’s documentation defines `*` as an entry whose deviation exceeds the tolerance; the first number is the supplied derivative value, the second number after `~` is the finite-difference estimate, and the bracketed value is the relative difference. For `jac_g`, the first index is the constraint index and the second is the variable index, with numbering style dependent on the interface. ([coin-or.github.io][1])

### Output fields

```text id="tu7zy6"
*:
  suspicious derivative; relative error > derivative_test_tol

grad_f[j]:
  j-th objective-gradient entry

jac_g[i,j]:
  derivative of i-th constraint body g_i wrt j-th variable x_j

left numeric value:
  derivative supplied by interface / user code / NL evaluator

v:
  entry exists in user-provided Jacobian sparsity structure

~ right numeric value:
  finite-difference estimate

[ ... ]:
  relative deviation
```

Ipopt’s derivative checker uses the relative deviation formula `|approx - exact| / max(|approx|, derivative_test_tol)`, and the `v` marker after a Jacobian value means that the entry is present in the supplied nonzero structure; absence of `v` indicates that the derivative was not declared as part of the sparsity structure. ([coin-or.github.io][1])

---

## 9.8 Interpreting missing sparsity entries

### Symptom

```text id="2tzyo0"
* jac_g [    4,    4] =  0.0000000000000000e+00    ~  2.2160643690464592e-02  [ 2.216e-02]
```

### Meaning

```text id="i47ku7"
no "v" marker:
  derivative checker finite difference says jac_g[4,4] nonzero
  supplied Jacobian sparsity does not include this position
  direct-interface sparsity pattern likely incomplete
```

Ipopt’s docs explicitly identify a missing `v` on a finite-difference-nonzero Jacobian entry as a likely sparsity-structure mistake. ([coin-or.github.io][1])

### Direct-interface fix

```text id="nkvn7a"
eval_jac_g structure call:
  add row index 4
  add col index 4
  increment nnz_jac_g
  ensure value array order matches structure order
```

### Pyomo/NL fix candidates

```text id="wk7m61"
ordinary Pyomo algebraic model:
  true missing sparsity pattern is rare
  investigate:
    ExternalFunction derivative metadata
    piecewise/nonsmooth expression
    expression generated conditionally
    variable used through value() during construction
    unsupported black-box function route
```

### Pyomo anti-pattern causing missing symbolic dependence

```python id="gr7hwj"
# BAD: freezes value at model-construction time, removes symbolic dependence.
coef = pyo.value(m.x)
m.c = pyo.Constraint(expr=coef * m.y >= 1.0)
```

Correct:

```python id="civk73"
m.c = pyo.Constraint(expr=m.x * m.y >= 1.0)
```

---

## 9.9 Interpreting wrong Jacobian values

### Symptom

```text id="sgjow4"
* jac_g [    4,    5] =  1.3798494268463347e+01 v  ~  1.3776333629422766e+01  [ 1.609e-03]
```

### Meaning

```text id="7xxibo"
"v" marker present:
  derivative position exists in declared sparsity structure

left value differs from finite difference:
  supplied derivative value likely wrong
  or finite-difference estimate unreliable due to scale/domain/noise
```

Ipopt’s docs use exactly this pattern to distinguish Jacobian entries present in the nonzero structure but whose values appear wrong. ([coin-or.github.io][1])

### Direct-interface fixes

```text id="7kl2b6"
[ ] verify constraint function formula g_i(x)
[ ] verify derivative formula ∂g_i/∂x_j
[ ] verify row/column indexing convention
[ ] verify value-array order matches structure-array order
[ ] verify no stale cached x / new_x mishandling
[ ] verify scaling or unit conversions not applied inconsistently
[ ] verify constraint body derivative, not residual derivative against bounds
```

### Pyomo fixes

```text id="1hizk3"
[ ] replace Python math.* with pyomo functions
[ ] remove value(var) from active expressions
[ ] protect finite-difference domains with bounds/interior starts
[ ] replace abs/max/min/floor/ceil with smooth/reformulated equivalents
[ ] check ExternalFunction derivative implementation
[ ] reduce scaling pathologies
```

---

## 9.10 Interpreting objective-gradient defects

### Symptom

```text id="462hkd"
* grad_f[          2] = -6.5159999999999991e+02    ~ -6.5559997134793468e+02  [ 6.101e-03]
```

### Meaning

```text id="v22xrl"
objective gradient component j suspicious:
  supplied ∂f/∂x_j differs from finite-difference estimate
```

### Common causes

```text id="kk2j7d"
direct interface:
  wrong gradient formula
  wrong objective scaling
  wrong variable ordering
  stale cached x
  finite difference crosses domain/discontinuity

Pyomo:
  ExternalFunction objective derivative wrong
  nonsmooth objective at starting point
  objective expression contains value(var)
  Python function accidentally evaluated outside symbolic graph
  poor scaling causing finite-difference sensitivity
```

### Debug pattern: isolate objective

```python id="9lnd7e"
# Temporarily deactivate constraints to isolate objective derivative defects.
for c in model.component_data_objects(pyo.Constraint, active=True):
    c.deactivate()

opt.options.update({
    "derivative_test": "first-order",
    "derivative_test_print_all": "yes",
    "max_iter": 0,
})
opt.solve(model, tee=True)
```

---

## 9.11 Output anatomy: second-order checker

Typical second-order output shape:

```text id="rb1lgn"
*             obj_hess[    1,    1] =  1.8810000000000000e+03 v  ~  1.8820000036612328e+03  [ 5.314e-04]
*     3-th constr_hess[    2,    4] =  1.0000000000000000e+00 v  ~  0.0000000000000000e+00  [ 1.000e+00]
```

Ipopt’s docs state that `obj_hess` reports objective Hessian derivative defects and `constr_hess` reports Hessian defects for a constraint; second derivatives are approximated by finite differences of first derivatives, so first-order errors should be fixed before second-order debugging. ([coin-or.github.io][1])

### Output fields

```text id="dsf279"
obj_hess[i,j]:
  ∂²f / ∂x_i∂x_j

k-th constr_hess[i,j]:
  ∂²g_k / ∂x_i∂x_j

v:
  entry present in Hessian sparsity structure

missing v:
  finite-difference-detected second derivative absent from structure

large bracketed relative difference:
  value mismatch or unreliable finite-difference estimate
```

### Hessian-of-Lagrangian caution

```text id="4fuju2"
Direct interface eval_h must return:
  obj_factor * ∇²f(x) + Σ_i lambda_i * ∇²g_i(x)

Derivative checker lines separate objective Hessian and constraint Hessian defects for diagnosis.
```

---

## 9.12 Sparse-structure debugging: direct interfaces

### Jacobian structure call pattern

```text id="3l1i3r"
if values == NULL:
  fill iRow[k], jCol[k] for every nonzero derivative position

else:
  fill values[k] in the exact same order
```

### Hessian structure call pattern

```text id="o1hiye"
if values == NULL:
  fill lower-triangular iRow[k], jCol[k] for every nonzero Hessian position

else:
  fill values[k] in the exact same order
```

### Direct-interface error checklist

```text id="tst67j"
[ ] nnz_jac_g equals number of declared Jacobian structure entries.
[ ] nnz_h_lag equals number of declared lower-triangular Hessian entries.
[ ] row/column indices match C_STYLE or FORTRAN_STYLE consistently.
[ ] Jacobian values are in same order as Jacobian structure.
[ ] Hessian values are in same order as Hessian structure.
[ ] Hessian uses lower triangle only.
[ ] Hessian combines objective and constraints with obj_factor/lambda.
[ ] constraint derivatives are derivatives of g(x), not lb - g(x) or g(x) - ub.
```

---

## 9.13 Pyomo-specific debugging workflow

### Keep files and symbolic labels

```python id="w41n5k"
res = opt.solve(
    model,
    tee=True,
    keepfiles=True,
    symbolic_solver_labels=True,
)
```

### New Pyomo contrib interface

```python id="f1bm0a"
from pyomo.contrib.solver.solvers.ipopt import Ipopt

solver = Ipopt()
res = solver.solve(
    model,
    tee=True,
    working_dir="ipopt-debug",
    symbolic_solver_labels=True,
    solver_options={
        "derivative_test": "first-order",
        "derivative_test_print_all": "yes",
        "max_iter": 0,
        "print_level": 7,
    },
)
```

Pyomo solver recipes document `tee=True` for streaming solver output and option dictionaries for solver options; the newer Pyomo Ipopt interface documents `working_dir`, `load_solutions`, `symbolic_solver_labels`, `solver_options`, and `executable` as solve/config controls for the NL-file-based interface. ([pyomo.readthedocs.io][4])

### Map solver indices back to Pyomo names

```text id="e5mjew"
classic:
  keepfiles=True + symbolic_solver_labels=True
  inspect generated .row and .col files

contrib:
  working_dir="..."
  symbolic_solver_labels=True
  inspect files in working_dir
```

### Agent rule

```text id="7jp6r9"
When derivative checker reports jac_g[i,j]:
  map i through .row file
  map j through .col file
  inspect corresponding Pyomo Constraint / Var
```

---

## 9.14 Starting-point sensitivity

### Why starting point matters

```text id="fib4k8"
Derivative checker samples finite differences around the user-provided starting point.
If the start is at a kink, singularity, bound, log/sqrt/domain boundary, or huge-scale region,
warnings can reflect model-domain/scale problems rather than algebraic derivative bugs.
```

Ipopt’s derivative checker perturbs each component of the user-provided starting point; the perturbation is relative and defaults to `1e-8`, which is approximately square root of machine precision. ([coin-or.github.io][1])

### Bad starts

```python id="23u1ey"
m.x = pyo.Var(bounds=(0, None), initialize=0.0)
m.obj = pyo.Objective(expr=pyo.sqrt(m.x))  # derivative singular at 0
```

```python id="79fu8k"
m.y = pyo.Var(bounds=(0, None), initialize=0.0)
m.c = pyo.Constraint(expr=pyo.log(m.y) >= -10)  # undefined at 0
```

### Better starts

```python id="p7lye5"
eps = 1e-6

m.x = pyo.Var(bounds=(eps, None), initialize=1.0)
m.obj = pyo.Objective(expr=pyo.sqrt(m.x))

m.y = pyo.Var(bounds=(eps, None), initialize=1.0)
m.c = pyo.Constraint(expr=pyo.log(m.y) >= -10)
```

### Debug-start normalization

```python id="3mw1eu"
def set_interior_starts(model, default=1.0, frac=0.1):
    for v in model.component_data_objects(pyo.Var, active=True):
        if v.fixed:
            continue
        lb = pyo.value(v.lb, exception=False) if v.lb is not None else None
        ub = pyo.value(v.ub, exception=False) if v.ub is not None else None

        if lb is not None and ub is not None:
            val = lb + frac * (ub - lb)
        elif lb is not None:
            val = lb + max(1.0, abs(lb)) * frac
        elif ub is not None:
            val = ub - max(1.0, abs(ub)) * frac
        else:
            val = default

        v.set_value(val, skip_validation=True)
```

---

## 9.15 Perturbation-size tuning

### Default

```python id="rxpkgq"
opt.options["derivative_test_perturbation"] = 1e-8
```

### Larger perturbation for noisy/scaled values

```python id="qkt22l"
opt.options["derivative_test_perturbation"] = 1e-6
```

### Smaller perturbation for smooth well-scaled values

```python id="6b9vvg"
opt.options["derivative_test_perturbation"] = 1e-9
```

### Interpretation policy

```text id="bl14s0"
If warning disappears when perturbation changes:
  suspect scale/domain/finite-difference sensitivity
  do not immediately assume exact derivative is correct

If warning persists across perturbation sizes:
  stronger evidence of derivative or sparsity bug

If perturbation crosses nonsmooth point/domain boundary:
  fix start/bounds/model formulation first
```

Ipopt’s docs state that the default perturbation is usually fine but may be changed if warnings look wrong; the perturbation is relative to variable entries. ([coin-or.github.io][1])

---

## 9.16 Tolerance tuning

### Default tolerance

```python id="5r4mmz"
opt.options["derivative_test_tol"] = 1e-4
```

### Stricter

```python id="dw3u6l"
opt.options["derivative_test_tol"] = 1e-6
```

### Looser for scale/noise investigation

```python id="zsjebc"
opt.options["derivative_test_tol"] = 1e-3
```

### Agent policy

```text id="mixyj5"
Use default 1e-4 first.

Tighten when:
  model is well-scaled
  exact analytic derivatives expected
  direct callback code under test

Loosen when:
  finite-difference noise likely
  variables badly scaled
  external functions have limited precision

Never:
  loosen tolerance to hide persistent structural errors.
```

Ipopt marks derivative entries as wrong when the relative deviation exceeds `derivative_test_tol`; the default is `0.0001`. ([coin-or.github.io][2])

---

## 9.17 `derivative_test_print_all`

### Suspicious only

```python id="dr5h9z"
opt.options["derivative_test_print_all"] = "no"
```

### Full dump

```python id="ai6ppr"
opt.options["derivative_test_print_all"] = "yes"
```

### Agent policy

```text id="zlzuzt"
small model:
  derivative_test_print_all=yes

large model:
  first run no
  rerun yes after using derivative_test_first_index / submodel isolation

CI regression:
  no, unless golden output intentionally stored
```

Ipopt’s docs state that `derivative_test_print_all=yes` prints user-provided values, finite-difference estimates, and relative deviations for every partial derivative; otherwise, only derivatives whose deviations exceed tolerance are printed. ([coin-or.github.io][1])

---

## 9.18 `derivative_test_first_index`: isolate large problems

### First-order isolation

```python id="u7cbdt"
opt.options.update({
    "derivative_test": "first-order",
    "derivative_test_first_index": 1000,
})
```

Meaning:

```text id="7jsczm"
start first-order derivative check at variable index 1000
```

### Second-order isolation

```python id="26z3sk"
opt.options.update({
    "derivative_test": "second-order",
    "derivative_test_first_index": -1,  # objective Hessian
})
```

Meaning:

```text id="xyv99m"
for second-order:
  -1 refers to objective Hessian
  nonnegative value starts at corresponding constraint index
```

Ipopt’s option reference specifies `derivative_test_first_index` behavior separately for first- and second-order tests, including `-1` for objective Hessian in second-order checks. ([coin-or.github.io][2])

---

## 9.19 Full Pyomo derivative-debug helper

```python id="o8h7z2"
from __future__ import annotations

from pathlib import Path
import pyomo.environ as pyo


def run_ipopt_derivative_check(
    model,
    *,
    order: str = "first-order",
    tol: float = 1e-4,
    perturbation: float = 1e-8,
    print_all: bool = True,
    first_index: int | None = None,
    executable: str | None = None,
    working_dir: str | Path | None = None,
    symbolic_solver_labels: bool = True,
):
    if order not in {"first-order", "second-order", "only-second-order"}:
        raise ValueError(order)

    kwargs = {}
    if executable is not None:
        kwargs["executable"] = executable

    opt = pyo.SolverFactory("ipopt", **kwargs)
    if not opt.available(exception_flag=False):
        raise RuntimeError("Ipopt executable unavailable.")

    opt.options.update({
        "derivative_test": order,
        "derivative_test_tol": tol,
        "derivative_test_perturbation": perturbation,
        "derivative_test_print_all": "yes" if print_all else "no",
        "max_iter": 0,
        "print_level": 7,
        "print_user_options": "yes",
    })

    if first_index is not None:
        opt.options["derivative_test_first_index"] = int(first_index)

    solve_kwargs = {
        "tee": True,
        "keepfiles": True,
        "symbolic_solver_labels": symbolic_solver_labels,
    }

    if working_dir is not None:
        # Classic interface may not expose working_dir uniformly across versions.
        # Prefer contrib Ipopt for controlled working_dir.
        Path(working_dir).mkdir(parents=True, exist_ok=True)

    return opt.solve(model, **solve_kwargs)
```

---

## 9.20 Log parsing: detect derivative-check failures

```python id="h0kgna"
import re
import subprocess
from pathlib import Path


DERIVATIVE_ERROR_RE = re.compile(r"Derivative checker detected\s+(\d+)\s+error", re.I)


def parse_derivative_checker_error_count(log_text: str) -> int | None:
    match = DERIVATIVE_ERROR_RE.search(log_text)
    if match:
        return int(match.group(1))
    if "No errors detected by derivative checker" in log_text:
        return 0
    return None


def run_command_capture(cmd: list[str], log_path: str | Path) -> int:
    p = subprocess.run(
        cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    Path(log_path).write_text(p.stdout)
    return p.returncode
```

### CI use

```python id="w09boh"
log = Path("ipopt_derivative_check.log").read_text()
n_errors = parse_derivative_checker_error_count(log)

if n_errors is None:
    raise AssertionError("Derivative checker summary not found.")
if n_errors != 0:
    raise AssertionError(f"Derivative checker reported {n_errors} errors.")
```

---

## 9.21 Model-debug triage matrix

| Checker output                      | Most likely cause                   | First fix                                                   |
| ----------------------------------- | ----------------------------------- | ----------------------------------------------------------- |
| `grad_f[j]` wrong                   | objective derivative issue          | inspect objective expression / external function / scale    |
| `jac_g[i,j]` wrong with `v`         | Jacobian value wrong                | inspect constraint `i`, variable `j`, direct callback order |
| `jac_g[i,j]` wrong without `v`      | missing Jacobian sparsity entry     | add sparsity entry or fix symbolic dependence               |
| `obj_hess[i,j]` wrong               | objective Hessian issue             | fix first-order first, then Hessian formula                 |
| `constr_hess[i,j]` wrong            | constraint Hessian issue            | fix constraint first derivatives first                      |
| many small deviations               | scaling/perturbation issue          | rescale, change perturbation, inspect starts                |
| errors near log/sqrt/division vars  | domain-boundary finite difference   | interior starts and bounds                                  |
| errors only with external functions | external derivative implementation  | derivative-check external function separately               |
| checker crashes with invalid number | undefined function value/derivative | protect domains; enable `check_derivatives_for_naninf`      |

---

## 9.22 `check_derivatives_for_naninf`: companion diagnostic

```python id="0qof34"
opt.options.update({
    "check_derivatives_for_naninf": "yes",
    "print_level": 7,
})
```

`check_derivatives_for_naninf=yes` makes Ipopt error when invalid numbers are found in the constraint Jacobian or Lagrangian Hessian; if invalid values are detected, the matrix is printed at detailed output level, which can be large. ([coin-or.github.io][2])

### Agent use

```text id="wjx6bq"
Use with derivative checker when:
  INVALID_NUMBER_DETECTED
  NaN/Inf in external derivatives
  log/sqrt/division domains uncertain
  finite-difference checker stops unexpectedly
```

---

## 9.23 Pyomo expression anti-patterns found by derivative checking

### `value()` freezes symbolic dependency

```python id="hzs9rq"
# BAD
a = pyo.value(m.x)
m.c = pyo.Constraint(expr=a * m.y >= 1)
```

```python id="ng9ej9"
# GOOD
m.c = pyo.Constraint(expr=m.x * m.y >= 1)
```

### Python `math` instead of Pyomo math

```python id="0tio54"
# BAD
import math
m.obj = pyo.Objective(expr=math.sin(m.x))
```

```python id="l3g3fu"
# GOOD
m.obj = pyo.Objective(expr=pyo.sin(m.x))
```

### nonsmooth expression

```python id="zpqsdv"
# BAD for smooth NLP
m.obj = pyo.Objective(expr=abs(m.x))
```

```python id="yyh5ig"
# smooth approximation
eps = 1e-6
m.obj = pyo.Objective(expr=pyo.sqrt(m.x**2 + eps))
```

### domain boundary

```python id="xrc1li"
# BAD
m.x = pyo.Var(bounds=(0, None), initialize=0)
m.c = pyo.Constraint(expr=pyo.log(m.x) >= -10)
```

```python id="dlx8a4"
# GOOD
m.x = pyo.Var(bounds=(1e-8, None), initialize=1.0)
m.c = pyo.Constraint(expr=pyo.log(m.x) >= -10)
```

---

## 9.24 Direct-interface bug patterns found by derivative checking

```text id="l76g0g"
Wrong row index:
  jac_g[i,j] value appears under wrong i

Wrong column index:
  derivative with respect to x_j appears under x_k

Wrong indexing base:
  C_STYLE 0-based vs FORTRAN_STYLE 1-based mismatch

Wrong value order:
  structure order and value order inconsistent

Wrong Hessian triangle:
  upper triangle supplied when lower triangle expected

Wrong Lagrangian Hessian:
  eval_h returns ∇²f only, omits Σ λ_i∇²g_i

Wrong objective scaling:
  eval_h ignores obj_factor

Wrong constraint residual convention:
  derivatives of g(x)-ub or lb-g(x) instead of g(x)

Stale cache:
  new_x ignored incorrectly
```

---

## 9.25 Small-instance generation pattern

```python id="eeo81g"
def build_debug_instance(full_data, *, max_items=10):
    debug_data = dict(full_data)
    debug_data["I"] = list(full_data["I"])[:max_items]

    # Slice every indexed data mapping consistently.
    for key in ["demand", "cost", "bounds", "x0"]:
        if key in debug_data:
            debug_data[key] = {i: full_data[key][i] for i in debug_data["I"]}

    return build_model(debug_data)


debug_model = build_debug_instance(data, max_items=10)
run_ipopt_derivative_check(debug_model, order="first-order")
```

**Agent rule:** derivative-check the smallest model instance that still contains the nonlinear expression families, external functions, and indexing patterns of the production model.

---

## 9.26 Performance and deployment policy

```text id="8i5a47"
Development:
  derivative_test first-order on new model templates
  derivative_test second-order if exact Hessian is used and first-order is clean
  print_all yes for tiny models

CI:
  derivative check on one small representative instance
  fail if derivative checker reports errors
  archive derivative-check log

Production:
  derivative_test none
  check_derivatives_for_naninf no unless diagnosing
  run ordinary solve profile
```

### Why not production?

```text id="i5kg0z"
finite-difference derivative checking:
  O(n) or worse objective/constraint evaluations for first-order
  second-order finite differences of first derivatives are more expensive
  prints large logs
  can perturb near fragile domains
  detects local derivative consistency only at checked starting point
```

Ipopt’s docs characterize the derivative test as slow and executed before optimization, and recommend using small instances when possible. ([coin-or.github.io][1])

---

## 9.27 Agent-ready derivative-debug profile catalog

### `DERIV_FIRST_SMALL`

```python id="f7i4gm"
DERIV_FIRST_SMALL = {
    "derivative_test": "first-order",
    "derivative_test_tol": 1e-4,
    "derivative_test_perturbation": 1e-8,
    "derivative_test_print_all": "yes",
    "max_iter": 0,
    "print_level": 7,
}
```

### `DERIV_SECOND_SMALL`

```python id="kqkmxz"
DERIV_SECOND_SMALL = {
    "derivative_test": "second-order",
    "derivative_test_tol": 1e-4,
    "derivative_test_perturbation": 1e-8,
    "derivative_test_print_all": "yes",
    "max_iter": 0,
    "print_level": 7,
}
```

### `DERIV_FIRST_LARGE_ISOLATED`

```python id="ucg8fg"
DERIV_FIRST_LARGE_ISOLATED = {
    "derivative_test": "first-order",
    "derivative_test_first_index": 1000,
    "derivative_test_tol": 1e-4,
    "derivative_test_print_all": "no",
    "max_iter": 0,
    "print_level": 5,
}
```

### `NANINF_DERIV_DIAG`

```python id="t2lth0"
NANINF_DERIV_DIAG = {
    "check_derivatives_for_naninf": "yes",
    "print_level": 7,
    "max_iter": 0,
}
```

---

## 9.28 Anti-patterns for LLM agents

```text id="klwzhh"
BAD:
  derivative_test=second-order before first-order is clean.

GOOD:
  first-order first; second-order after first-order passes.

BAD:
  derivative_test_print_all=yes on full-scale model by default.

GOOD:
  small instance or derivative_test_first_index isolation.

BAD:
  loosen derivative_test_tol until errors disappear.

GOOD:
  investigate scaling, perturbation, sparsity, formulas, and domains.

BAD:
  treat missing "v" as a value error.

GOOD:
  missing "v" means sparsity-structure omission.

BAD:
  run derivative checker at x=0 for log(x), sqrt(x), division by x.

GOOD:
  set interior starting values and protective bounds.

BAD:
  leave derivative_test enabled in production.

GOOD:
  derivative_test none for production solve profiles.

BAD:
  assume Pyomo algebraic expressions cannot produce derivative-check issues.

GOOD:
  audit external functions, nonsmooth functions, value() usage, and bad starts.
```

---

## 9.29 Final checklist

```text id="mkx02b"
[ ] Build smallest representative debug instance.
[ ] Set all nonlinear variables to finite interior starts.
[ ] Protect log/sqrt/division domains with bounds.
[ ] Enable derivative_test=first-order first.
[ ] Use derivative_test_print_all=yes only on small instances.
[ ] Interpret "*" as tolerance-exceeding derivative entry.
[ ] Interpret "v" on jac_g/Hessian entries as present in declared sparsity.
[ ] Treat missing "v" with nonzero finite difference as missing sparsity.
[ ] Fix all first-order defects before second-order defects.
[ ] Use derivative_test_perturbation tuning only after checking scale/domain.
[ ] Use derivative_test_tol tuning carefully; do not hide structural defects.
[ ] Use symbolic_solver_labels / row-col files to map indices to Pyomo components.
[ ] Use derivative_test_first_index to isolate large models.
[ ] Use check_derivatives_for_naninf for NaN/Inf derivative failures.
[ ] Archive derivative-check logs for CI/regression.
[ ] Disable derivative_test for production solves.
```

[1]: https://coin-or.github.io/Ipopt/SPECIALS.html "Ipopt: Special Features"
[2]: https://coin-or.github.io/Ipopt/OPTIONS.html "Ipopt: Ipopt Options"
[3]: https://coin-or.github.io/Ipopt/OPTIONS.html?utm_source=chatgpt.com "Ipopt Options"
[4]: https://pyomo.readthedocs.io/en/latest/howto/solver_recipes.html "Solver Recipes — Pyomo 6.10.1.dev0 documentation"

# Ipopt Advanced — Section 10: linear solvers and numerical linear algebra

Style target: dense advanced technical catalog / agent-ready reference. 

## 10.0 Linear-solver invariant

```text id="6bz3ba"
Ipopt major iteration
→ build sparse KKT / augmented linear system
→ factor/solve sparse symmetric indefinite system
→ compute primal-dual search direction
→ line-search / filter accept or reject step
```

**Practical consequence:** the sparse linear solver is often the dominant runtime and robustness component in Ipopt. Ipopt’s install documentation states that Ipopt requires at least one linear solver for sparse symmetric indefinite matrices, that the largest fraction of optimizer computation time is usually spent solving the linear system, and that linear-solver choice affects both speed and robustness. ([coin-or.github.io][1])

---

## 10.1 Pyomo option syntax: selecting a linear solver

### Baseline portable conda-forge profile

```python id="3cwrw3"
import pyomo.environ as pyo

opt = pyo.SolverFactory("ipopt")

opt.options.update({
    "linear_solver": "mumps",
    "tol": 1e-8,
    "print_user_options": "yes",
})

results = opt.solve(model, tee=True)
```

### Probe before selecting non-baseline solvers

```python id="rwul0u"
import pyomo.environ as pyo

opt = pyo.SolverFactory("ipopt")

for name in ["mumps", "spral", "ma27", "ma57", "ma77", "ma86", "ma97", "pardiso", "pardisomkl", "wsmp"]:
    try:
        print(f"{name:12s}", opt.has_linear_solver(name))
    except Exception as exc:
        print(f"{name:12s}", f"{type(exc).__name__}: {exc}")
```

Pyomo’s newer Ipopt interface documents `has_linear_solver(linear_solver)` as a method that solves a small problem to determine whether the Ipopt executable has access to the requested linear solver; this is the correct programmatic check before deploying non-default linear-solver options. ([pyomo.readthedocs.io][2])

### Installed option dump

```bash id="wiqdhc"
ipopt --print-options > ipopt.print-options.txt
ipopt -= > ipopt.ampl-options.txt
```

Ipopt’s option docs expose the generic `linear_solver` option list, but build-dependent support must be inspected on the installed executable; options such as HSL/Pardiso/SPRAL/MUMPS controls only matter when that solver is available in the build or runtime-load path. ([coin-or.github.io][3])

---

## 10.2 Conda-forge practical baseline

```text id="pf3tof"
portable baseline:
  linear_solver=mumps

current conda-forge metadata:
  ipopt 3.14.19
  common dependencies include:
    ampl-asl
    libblas
    liblapack
    mumps-seq

current Linux metadata also shows:
    libspral
```

Current conda-forge metadata for `ipopt` 3.14.19 shows dependencies such as `ampl-asl`, `libblas`, `liblapack`, and `mumps-seq` across major platform variants; current Linux variants additionally list `libspral`, while the displayed macOS variants list `mumps-seq` but not `libspral` in the same dependency block. ([prefix.dev][4])

### Agent policy

```text id="7qtkwm"
Default generated Pyomo code:
  omit linear_solver OR set linear_solver=mumps

Linux performance experiment:
  if opt.has_linear_solver("spral"):
      test linear_solver=spral against mumps

Custom performance deployment:
  benchmark mumps, spral, HSL, Pardiso, MKL Pardiso where licensed/available

Never:
  assume ma57 / pardiso / pardisomkl / wsmp exists in conda-forge ipopt
```

---

## 10.3 Ipopt `linear_solver` option values

```text id="578l45"
linear_solver ∈ {
  ma27,
  ma57,
  ma77,
  ma86,
  ma97,
  pardiso,
  pardisomkl,
  spral,
  wsmp,
  mumps,
  custom
}
```

Ipopt’s `linear_solver` option determines the package used to solve the augmented linear system for search directions; the documented values include the HSL family (`ma27`, `ma57`, `ma77`, `ma86`, `ma97`), Pardiso Project (`pardiso`), Intel MKL Pardiso (`pardisomkl`), SPRAL (`spral`), WSMP (`wsmp`), MUMPS (`mumps`), and an expert `custom` interface. ([coin-or.github.io][3])

### Syntax examples

```python id="cfdptl"
opt.options["linear_solver"] = "mumps"
```

```python id="m21j2e"
opt.options["linear_solver"] = "spral"
```

```python id="npv8qi"
opt.options.update({
    "linear_solver": "ma57",
    "hsllib": "/absolute/path/to/libhsl.so",
})
```

```python id="86m77y"
opt.options.update({
    "linear_solver": "pardiso",
    "pardisolib": "/absolute/path/to/libpardiso.so",
})
```

```python id="ddexgr"
opt.options["linear_solver"] = "pardisomkl"
```

---

## 10.4 Numerical linear algebra: what the solver is solving

```text id="6qgnd9"
Ipopt Newton/KKT system:
  sparse
  symmetric
  indefinite
  ill-conditioning possible
  inertia/signature matters
  pivoting/scaling/orderings dominate memory and robustness
```

### Agent interpretation

```text id="jw93ej"
modeling affects linear solver through:
  Jacobian sparsity
  Hessian sparsity
  constraint scaling
  variable scaling
  equality dependency
  bound degeneracy
  nonlinear expression coupling
```

### Sparse-structure value case

```text id="jeccnv"
good sparsity:
  lower fill-in
  lower memory
  faster factorization
  better pivoting behavior
  fewer numerical failures

bad sparsity:
  dense KKT blocks
  excessive fill-in
  memory explosion
  high regularization
  more restoration/linear-solver failures
```

---

## 10.5 Installed capability audit

### Capability report

```python id="8doyn7"
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from typing import Any

import pyomo.environ as pyo


LINEAR_SOLVERS = [
    "mumps",
    "spral",
    "ma27",
    "ma57",
    "ma77",
    "ma86",
    "ma97",
    "pardiso",
    "pardisomkl",
    "wsmp",
]


@dataclass
class LinearSolverStatus:
    name: str
    available: bool | None
    error: str | None = None


@dataclass
class IpoptLinearAlgebraReport:
    python: str
    ipopt_path: str | None
    ipopt_version_stdout: str
    pyomo_available: bool
    pyomo_version: Any
    linear_solvers: list[LinearSolverStatus]


def run_text(cmd: list[str]) -> str:
    try:
        return subprocess.run(
            cmd,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=30,
        ).stdout.strip()
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"


def build_report() -> IpoptLinearAlgebraReport:
    opt = pyo.SolverFactory("ipopt")
    ipopt_path = shutil.which("ipopt")

    pyomo_available = bool(opt.available(exception_flag=False))

    try:
        pyomo_version = opt.version()
    except Exception as exc:
        pyomo_version = f"{type(exc).__name__}: {exc}"

    statuses: list[LinearSolverStatus] = []
    if pyomo_available:
        for ls in LINEAR_SOLVERS:
            try:
                statuses.append(LinearSolverStatus(ls, bool(opt.has_linear_solver(ls))))
            except Exception as exc:
                statuses.append(LinearSolverStatus(ls, None, f"{type(exc).__name__}: {exc}"))

    return IpoptLinearAlgebraReport(
        python=sys.executable,
        ipopt_path=ipopt_path,
        ipopt_version_stdout=run_text([ipopt_path, "-v"]) if ipopt_path else "",
        pyomo_available=pyomo_available,
        pyomo_version=pyomo_version,
        linear_solvers=statuses,
    )


if __name__ == "__main__":
    print(json.dumps(asdict(build_report()), indent=2, default=str))
```

### Agent rule

```text id="tiszgr"
Every serious Ipopt deployment should archive:
  ipopt --print-options
  linear-solver probe results
  solver log from a small NLP with print_user_options=yes
  conda list / environment.yml
```

---

## 10.6 MUMPS: portable baseline

### Minimal MUMPS profile

```python id="rh0la1"
opt.options.update({
    "linear_solver": "mumps",
})
```

### Diagnostic MUMPS profile

```python id="v59rld"
opt.options.update({
    "linear_solver": "mumps",
    "mumps_print_level": 2,
    "print_level": 5,
    "print_user_options": "yes",
})
```

### Pivot-stability profile

```python id="leyydi"
opt.options.update({
    "linear_solver": "mumps",
    "mumps_pivtol": 1e-5,
    "mumps_pivtolmax": 0.1,
})
```

### Memory-stress profile

```python id="k2qgqy"
opt.options.update({
    "linear_solver": "mumps",
    "mumps_mem_percent": 2000,
})
```

Ipopt’s MUMPS options include `mumps_print_level`, `mumps_pivtol`, `mumps_pivtolmax`, `mumps_mem_percent`, `mumps_permuting_scaling`, `mumps_pivot_order`, and `mumps_scaling`; `mumps_pivtol` trades sparsity against stability, while Ipopt may increase pivot tolerance up to `mumps_pivtolmax` for more accurate linear solves. ([coin-or.github.io][3])

### MUMPS option semantics

| Option                    | Default | Meaning                                           | Agent tuning use                              |
| ------------------------- | ------: | ------------------------------------------------- | --------------------------------------------- |
| `mumps_print_level`       |     `0` | MUMPS diagnostic verbosity                        | use `2` or `3` for debugging                  |
| `mumps_pivtol`            |  `1e-6` | pivot tolerance                                   | increase for stability, decrease for sparsity |
| `mumps_pivtolmax`         |   `0.1` | maximum pivot tolerance Ipopt may use             | keep high enough for recovery                 |
| `mumps_mem_percent`       |  `1000` | extra estimated workspace percentage              | increase for memory allocation/fill-in issues |
| `mumps_permuting_scaling` |     `7` | MUMPS ICNTL(6)                                    | advanced                                      |
| `mumps_pivot_order`       |     `7` | MUMPS ICNTL(7)                                    | advanced                                      |
| `mumps_scaling`           |    `77` | MUMPS ICNTL(8)                                    | advanced                                      |
| `mumps_dep_tol`           |     `0` | linearly dependent constraint detection threshold | degeneracy debugging                          |

### MUMPS deployment cautions

```text id="g73lnl"
MUMPS is a strong default because:
  open/package-friendly
  conda-forge packaged
  available across major platforms
  no separate commercial license path

MUMPS can be weak when:
  KKT system is badly scaled
  equality constraints are nearly dependent
  pivoting causes large fill-in
  memory pressure dominates
  MPI/fake-MPI interactions matter in HPC applications
```

Ipopt’s install docs note that MUMPS performance can improve when METIS ordering algorithms are available and warn that the non-MPI version of MUMPS uses a fake MPI implementation that can interact poorly with MPI programs. ([coin-or.github.io][1])

---

## 10.7 HSL family: MA27, MA57, MA77, MA86, MA97

### Solver names

```text id="n7nn0e"
linear_solver ma27
linear_solver ma57
linear_solver ma77
linear_solver ma86
linear_solver ma97
```

### Runtime-loaded HSL syntax

```python id="1qyhf7"
opt.options.update({
    "linear_solver": "ma57",
    "hsllib": "/absolute/path/to/libhsl.so",
})
```

`hsllib` is the Ipopt option naming the shared library from which HSL routines should be loaded at runtime if an HSL solver is selected; the default names are platform-specific (`libhsl.so`, `libhsl.dylib`, `libhsl.dll`), and the value may include a path. ([coin-or.github.io][3])

### HSL licensing/deployment facts

```text id="1l58za"
Coin-HSL Archive:
  includes older codes such as MA27, MA28, MC19
  not redistributable without license from authors

Coin-HSL Full:
  includes MA57, HSL_MA77, HSL_MA86, HSL_MA97 in addition to Archive contents
  academic-use availability noted by Ipopt docs
```

Ipopt’s install docs describe Coin-HSL Archive and Coin-HSL Full, note restrictions on redistribution, and state that HSL can be compiled through ThirdParty-HSL or loaded as a shared library at runtime; the same docs note that MA57 can be considerably faster than MA27 on some problems. ([coin-or.github.io][1])

### Runtime HSL deployment checklist

```text id="3h765v"
[ ] obtain HSL under valid license
[ ] build or receive shared library for target OS/architecture
[ ] confirm Ipopt build supports linear-solver loader
[ ] set hsllib to absolute path
[ ] set linear_solver to selected HSL solver
[ ] run opt.has_linear_solver("ma57")
[ ] run representative benchmark against mumps
[ ] do not redistribute libhsl without explicit rights
```

### Example: HSL profile

```python id="cdadxl"
opt.options.update({
    "linear_solver": "ma57",
    "hsllib": "/opt/hsl/lib/libhsl.so",
    "linear_system_scaling": "mc19",
    "print_user_options": "yes",
})
```

`linear_system_scaling` defaults to MC19 only for selected HSL solvers such as MA27/MA57/MA77/MA86, and otherwise defaults differently; MC19 is HSL-related linear-system scaling independent of NLP scaling. ([coin-or.github.io][3])

---

## 10.8 Pardiso Project versus Intel MKL Pardiso

### Pardiso Project

```python id="iq0awk"
opt.options.update({
    "linear_solver": "pardiso",
    "pardisolib": "/absolute/path/to/libpardiso.so",
})
```

### Intel MKL Pardiso

```python id="1j9tyu"
opt.options.update({
    "linear_solver": "pardisomkl",
})
```

Ipopt 3.14 distinguishes Pardiso Project from Intel MKL Pardiso: `linear_solver=pardiso` refers to Pardiso Project and is loaded at runtime through `pardisolib`, while `linear_solver=pardisomkl` selects the Pardiso implementation in Intel MKL when Ipopt is built with MKL support. ([coin-or.github.io][1])

### Pardiso Project options

```python id="x0xp0f"
opt.options.update({
    "linear_solver": "pardiso",
    "pardisolib": "/opt/pardiso/libpardiso.so",
    "pardiso_msglvl": 0,
    "pardiso_matching_strategy": "complete+2x2",
})
```

### MKL Pardiso options

```python id="bu2src"
opt.options.update({
    "linear_solver": "pardisomkl",
    "pardisomkl_msglvl": 0,
    "pardisomkl_matching_strategy": "complete+2x2",
    "pardisomkl_order": "metis",
})
```

Ipopt documents separate option namespaces for Pardiso Project (`pardiso_*`) and MKL Pardiso (`pardisomkl_*`), including matching strategy and message-level controls; MKL Pardiso also exposes ordering controls such as `pardisomkl_order`. ([coin-or.github.io][3])

### Pardiso deployment policy

```text id="q0dy5t"
Use pardiso when:
  user provides Pardiso Project shared library
  license confirmed
  pardisolib absolute path known
  opt.has_linear_solver("pardiso") succeeds

Use pardisomkl when:
  Ipopt binary was built with MKL Pardiso support
  opt.has_linear_solver("pardisomkl") succeeds

Do not:
  treat pardiso and pardisomkl as synonyms
  use pardisolib for MKL Pardiso
  assume conda-forge ipopt supports either
```

Ipopt’s install docs state that Pardiso Project requires obtaining the Pardiso library and license separately, and that the number of processors for parallel Pardiso should be controlled with `OMP_NUM_THREADS` as described in the Pardiso manual. ([coin-or.github.io][1])

---

## 10.9 SPRAL: CPU/GPU-capable sparse linear solver

### Basic SPRAL profile

```python id="v4nrrj"
opt.options.update({
    "linear_solver": "spral",
    "spral_print_level": 0,
})
```

### SPRAL scaling/order/pivot profile

```python id="x4duop"
opt.options.update({
    "linear_solver": "spral",
    "spral_order": "matching",
    "spral_scaling": "matching",
    "spral_pivot_method": "block",
    "spral_u": 1e-8,
    "spral_umax": 1e-4,
})
```

### SPRAL GPU-related profile

```python id="tpokdb"
opt.options.update({
    "linear_solver": "spral",
    "spral_use_gpu": "yes",
    "spral_min_gpu_work": 5e9,
    "spral_gpu_perf_coeff": 1.0,
})
```

Ipopt’s SPRAL options include CPU block size, GPU performance coefficient, NUMA behavior, minimum GPU work, ordering, pivot method, print level, scaling choices, pivot thresholds, and `spral_use_gpu`; `spral_use_gpu` defaults to `yes` if SPRAL with GPU support is present, but effective GPU use depends on how SPRAL/Ipopt were built and deployed. ([coin-or.github.io][3])

### SPRAL build/deployment facts

```text id="kjqhmm"
SPRAL CPU build:
  requires SPRAL library, headers, OpenMP/runtime libs, BLAS/LAPACK stack

SPRAL GPU build:
  additionally requires CUDA-related libraries and GPU-capable SPRAL build

runtime env:
  OMP_CANCELLATION=TRUE
  OMP_PROC_BIND=TRUE
  OMP_NESTED=TRUE for older SPRAL variants
```

Ipopt’s install guide gives separate SPRAL CPU and CPU+GPU link-flag examples, notes that best performance can require matching SPRAL with high-performance linear algebra routines, and lists OpenMP environment variables recommended when using SPRAL. ([coin-or.github.io][1])

### SPRAL agent policy

```text id="4zqba4"
Conda-forge Linux:
  metadata may show libspral
  still probe opt.has_linear_solver("spral")

macOS/Windows:
  do not assume spral; probe

GPU:
  do not enable GPU path unless:
    spral exists
    spral_use_gpu option present
    GPU-capable SPRAL build deployed
    CUDA/runtime environment validated
    representative benchmark beats CPU path
```

---

## 10.10 BLAS/LAPACK and conda BLAS variants

### Inspect current BLAS/LAPACK packages

```bash id="480iov"
conda list "libblas|liblapack|openblas|mkl|blis|accelerate"
```

### Pin OpenBLAS-like conda variant

```yaml id="myw69b"
channels:
  - conda-forge
channel_priority: strict
dependencies:
  - python=3.11
  - pyomo
  - ipopt
  - libblas=*=*openblas
  - liblapack=*=*openblas
```

### Pin MKL-like conda variant where compatible

```yaml id="7iadlc"
channels:
  - conda-forge
channel_priority: strict
dependencies:
  - python=3.11
  - pyomo
  - ipopt
  - libblas=*=*mkl
  - liblapack=*=*mkl
```

Conda-forge `ipopt` depends on abstract `libblas` and `liblapack` packages, while Ipopt’s installation docs strongly recommend using an efficient BLAS/LAPACK implementation tailored to the hardware. ([prefix.dev][4])

### Thread-control profile

```bash id="lyjzhp"
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
```

### Agent policy

```text id="0mgg5l"
Single Ipopt solve on dedicated node:
  benchmark BLAS threads and linear-solver threads

Many scenario solves in parallel:
  usually set BLAS/OpenMP threads to 1 per process

Pardiso/SPRAL threaded solve:
  coordinate OMP_NUM_THREADS with solver-specific parallelism

Conda reproducibility:
  pin BLAS implementation in environment.yml for benchmark comparability
```

---

## 10.11 Linear-system scaling controls

### Global linear-system scaling

```python id="3o0gr8"
opt.options.update({
    "linear_system_scaling": "none",
})
```

```python id="uhgqp5"
opt.options.update({
    "linear_system_scaling": "mc19",
    "linear_scaling_on_demand": "yes",
})
```

Ipopt’s `linear_system_scaling` controls symmetric scaling of the augmented linear system, independent of NLP scaling; choices include `none`, `mc19`, and `slack-based`, and `linear_scaling_on_demand=yes` delays scaling until linear-system solutions appear poor. ([coin-or.github.io][3])

### Agent distinction

```text id="e7d4la"
nlp_scaling_method:
  scales NLP objective/constraints/variables

linear_system_scaling:
  scales augmented KKT linear system

Do not confuse these controls.
```

---

## 10.12 Benchmark harness: compare available solvers

```python id="gqs6m3"
from __future__ import annotations

import time
import pyomo.environ as pyo


def solve_with_linear_solver(model, linear_solver: str, *, tee=False):
    m = model.clone()
    opt = pyo.SolverFactory("ipopt")

    if not opt.available(exception_flag=False):
        raise RuntimeError("Ipopt unavailable.")

    try:
        if not opt.has_linear_solver(linear_solver):
            return {
                "linear_solver": linear_solver,
                "available": False,
                "ok": False,
                "error": "has_linear_solver returned False",
            }
    except Exception as exc:
        return {
            "linear_solver": linear_solver,
            "available": None,
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
        }

    opt.options.update({
        "linear_solver": linear_solver,
        "tol": 1e-8,
        "max_iter": 1000,
        "print_level": 5 if tee else 0,
        "print_user_options": "yes",
    })

    t0 = time.perf_counter()
    try:
        res = opt.solve(m, tee=tee, load_solutions=True)
        elapsed = time.perf_counter() - t0
        active_objs = list(m.component_data_objects(pyo.Objective, active=True))
        obj = pyo.value(active_objs[0], exception=False) if active_objs else None
        return {
            "linear_solver": linear_solver,
            "available": True,
            "ok": True,
            "status": str(res.solver.status),
            "termination_condition": str(res.solver.termination_condition),
            "objective": obj,
            "elapsed_seconds": elapsed,
        }
    except Exception as exc:
        return {
            "linear_solver": linear_solver,
            "available": True,
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
        }


def benchmark_linear_solvers(model, candidates=("mumps", "spral", "ma57", "pardiso", "pardisomkl")):
    return [solve_with_linear_solver(model, ls) for ls in candidates]
```

### Benchmark metric contract

```text id="dhxuye"
record:
  solver availability
  termination condition
  objective
  max constraint violation
  elapsed time
  iteration count from log
  linear-solver warnings
  memory / RSS if available externally
```

---

## 10.13 Log and timing controls

### Ipopt timing statistics

```python id="ehtnkr"
opt.options.update({
    "print_timing_statistics": "yes",
    "print_level": 5,
})
```

`print_timing_statistics=yes` tells Ipopt to print timing statistics and implies `timing_statistics=yes`, which helps separate NLP evaluation time from linear-algebra/solver work in logs. ([coin-or.github.io][3])

### Solver log capture

```python id="0dcby7"
results = opt.solve(
    model,
    tee=True,
    logfile="ipopt-linear-solver-benchmark.log",
)
```

### Agent interpretation

```text id="mromht"
If time dominated by:
  NLP function/derivative evaluation:
    optimize Pyomo expressions, external functions, model construction, NL writing

  linear solver / system solve:
    benchmark linear_solver, scaling, pivot settings, sparsity quality, BLAS threads

  many line-search backtracks:
    check scaling, derivatives, nonsmoothness, initialization

  restoration:
    check feasibility and constraint qualification before linear-solver tuning
```

---

## 10.14 Modeling choices that damage linear-solver performance

### Dense all-to-all coupling

```python id="8wcnci"
# BAD: dense constraint Jacobian
m.c = pyo.Constraint(
    m.I,
    rule=lambda m, i: sum(m.x[j] for j in m.J) >= demand[i],
)
```

### Sparse adjacency

```python id="q3oeop"
# GOOD: sparse local coupling
m.c = pyo.Constraint(
    m.I,
    rule=lambda m, i: sum(m.x[j] for j in neighbors[i]) >= demand[i],
)
```

### Dense quadratic Hessian

```python id="ye2567"
# BAD if Q is sparse but modeled dense
m.obj = pyo.Objective(
    expr=sum(Q[i, j] * m.x[i] * m.x[j] for i in m.I for j in m.I)
)
```

### Sparse Hessian

```python id="c3gvm9"
m.QNZ = pyo.Set(dimen=2, initialize=[(i, j) for (i, j), v in Q.items() if v != 0.0])
m.obj = pyo.Objective(
    expr=sum(Q[i, j] * m.x[i] * m.x[j] for i, j in m.QNZ)
)
```

### Agent rule

```text id="ud5vwd"
Linear-solver tuning cannot fully compensate for dense or badly scaled modeling.
First fix:
  sparsity
  scaling
  variable bounds
  derivative correctness
then benchmark linear_solver.
```

---

## 10.15 Failure-mode diagnostics

| Symptom                          | Likely linear-algebra cause      | First action                                          |
| -------------------------------- | -------------------------------- | ----------------------------------------------------- |
| `Error_In_Step_Computation`      | KKT solve/regularization failure | check derivatives, scaling, try MUMPS pivot settings  |
| repeated `lg(rg)` large          | Hessian/KKT regularization       | check scaling, degeneracy, Hessian strategy           |
| MUMPS memory error               | fill-in / workspace              | increase `mumps_mem_percent`, reduce dense coupling   |
| solver slow with few iterations  | factorization dominates          | benchmark solvers, BLAS, sparsity                     |
| solver slow with many iterations | not only linear solver           | check algorithm/scaling/initialization                |
| `Restoration_Failed`             | not necessarily linear solver    | check feasibility/derivatives before switching solver |
| `linear_solver` option rejected  | build lacks solver               | run `has_linear_solver`, inspect option dump          |
| `pardisolib` load failure        | path/license/ABI                 | verify library path, OS, license, architecture        |
| GPU SPRAL no speedup             | build/data/GPU scheduling        | verify GPU build, problem size, `spral_min_gpu_work`  |

---

## 10.16 Safe selection function

```python id="0vyzcu"
import pyomo.environ as pyo


def configure_linear_solver(
    opt,
    *,
    preferred=("spral", "mumps"),
    require=False,
):
    availability = {}

    for ls in preferred:
        try:
            availability[ls] = bool(opt.has_linear_solver(ls))
        except Exception:
            availability[ls] = False

    for ls in preferred:
        if availability[ls]:
            opt.options["linear_solver"] = ls
            return ls, availability

    if require:
        raise RuntimeError(f"No preferred linear solver available: {availability}")

    # Leave Ipopt default if nothing in preferred list is confirmed.
    return None, availability


opt = pyo.SolverFactory("ipopt")
chosen, availability = configure_linear_solver(opt, preferred=("spral", "mumps"))
print("chosen:", chosen)
print("availability:", availability)
```

---

## 10.17 Deployment profiles

### Portable conda-forge profile

```python id="tq0esw"
IPOPT_LINEAR_PORTABLE = {
    "linear_solver": "mumps",
    "mumps_pivtol": 1e-6,
    "mumps_pivtolmax": 0.1,
}
```

### MUMPS stability profile

```python id="d9j6d0"
IPOPT_LINEAR_MUMPS_STABLE = {
    "linear_solver": "mumps",
    "mumps_pivtol": 1e-5,
    "mumps_pivtolmax": 0.1,
    "mumps_mem_percent": 2000,
}
```

### SPRAL profile

```python id="p2p5rs"
IPOPT_LINEAR_SPRAL = {
    "linear_solver": "spral",
    "spral_order": "matching",
    "spral_scaling": "matching",
    "spral_pivot_method": "block",
    "spral_use_gpu": "no",  # switch only after GPU-capable deployment proof
}
```

### HSL profile

```python id="xvrc9v"
IPOPT_LINEAR_HSL_MA57 = {
    "linear_solver": "ma57",
    "hsllib": "/opt/hsl/lib/libhsl.so",
    "linear_system_scaling": "mc19",
}
```

### Pardiso Project profile

```python id="jt4t52"
IPOPT_LINEAR_PARDISO_PROJECT = {
    "linear_solver": "pardiso",
    "pardisolib": "/opt/pardiso/libpardiso.so",
    "pardiso_matching_strategy": "complete+2x2",
    "pardiso_msglvl": 0,
}
```

### MKL Pardiso profile

```python id="uk153a"
IPOPT_LINEAR_PARDISO_MKL = {
    "linear_solver": "pardisomkl",
    "pardisomkl_matching_strategy": "complete+2x2",
    "pardisomkl_order": "metis",
    "pardisomkl_msglvl": 0,
}
```

---

## 10.18 Licensing and redistribution policy

```text id="dt13kn"
Ipopt:
  EPL-licensed solver package

MUMPS:
  conda-packaged baseline; open/public-domain noted by Ipopt docs

HSL:
  separate HSL license path
  redistribution restrictions
  do not ship library unless user confirms rights

Pardiso Project:
  separate academic/evaluation/commercial license
  runtime-loaded through pardisolib

Intel MKL Pardiso:
  bundled with MKL
  requires Ipopt built with MKL/Pardiso support
  use linear_solver=pardisomkl, not pardiso

WSMP:
  separate vendor library path
```

Ipopt’s docs state that HSL Archive may not be redistributed in source or binary form without a purchased license, describe HSL Full as freely available for academic use, and state that Pardiso Project requires obtaining the library and reading its license agreement before use. ([coin-or.github.io][1])

---

## 10.19 Anti-patterns for LLM agents

```text id="02mg2h"
BAD:
  opt.options["linear_solver"] = "ma57"
  # without HSL license/library/probe

GOOD:
  if opt.has_linear_solver("ma57"):
      opt.options["linear_solver"] = "ma57"

BAD:
  treat pardiso as MKL Pardiso in Ipopt 3.14+

GOOD:
  pardiso      = Pardiso Project via pardisolib
  pardisomkl   = Intel MKL Pardiso

BAD:
  enable spral_use_gpu=yes and assume GPU is used

GOOD:
  verify SPRAL GPU build, CUDA runtime, option dump, and benchmark log

BAD:
  increase mumps_pivtol blindly after every failure

GOOD:
  check derivatives, scaling, infeasibility, and linear-solver log first

BAD:
  use dense all-pairs summations for sparse physical networks

GOOD:
  build sparse neighbor/index sets

BAD:
  assume conda-forge `ipopt` exposes all documented linear_solver values

GOOD:
  capture ipopt --print-options and has_linear_solver matrix
```

---

## 10.20 Final checklist

```text id="s6qce2"
[ ] Understand linear solve as central Ipopt cost/robustness component.
[ ] Use MUMPS as portable conda-forge baseline.
[ ] Probe SPRAL before using it, especially across OS/platforms.
[ ] Treat HSL/Pardiso/WSMP as custom licensed deployments.
[ ] Distinguish Pardiso Project from MKL Pardiso.
[ ] Use hsllib only for runtime-loaded HSL libraries.
[ ] Use pardisolib only for Pardiso Project libraries.
[ ] Do not assume conda-forge build exposes HSL/Pardiso/MKL/WSMP.
[ ] Capture ipopt --print-options for installed executable.
[ ] Use has_linear_solver(...) before setting nonbaseline solver.
[ ] Tune MUMPS pivots/memory only after checking model scaling and derivatives.
[ ] Use SPRAL GPU controls only after confirming GPU-capable build.
[ ] Pin BLAS/LAPACK variant for reproducible benchmarks.
[ ] Control thread counts in parallel scenario solves.
[ ] Benchmark representative model families, not toy models only.
[ ] Improve sparsity/model scaling before blaming the linear solver.
```

[1]: https://coin-or.github.io/Ipopt/INSTALL.html "Ipopt: Installing Ipopt"
[2]: https://pyomo.readthedocs.io/en/stable/api/pyomo.contrib.solver.solvers.ipopt.Ipopt.html?utm_source=chatgpt.com "Ipopt — Pyomo 6.10.0 documentation"
[3]: https://coin-or.github.io/Ipopt/OPTIONS.html "Ipopt: Ipopt Options"
[4]: https://prefix.dev/channels/conda-forge/packages/ipopt "ipopt - conda-forge"

# Ipopt Advanced — Section 11: scaling, initialization, and bound treatment

Style target: dense advanced technical catalog / agent-ready reference. 

## 11.0 Control-surface invariant

```text id="qx6j9m"
Ipopt robustness depends heavily on:
  scaled objective / constraint / derivative magnitudes
  finite, meaningful variable bounds
  evaluable interior starting point
  controlled handling of fixed variables
  explicit policy for bound relaxation
  explicit policy for poor/no starting values
```

Ipopt’s scaling, initialization, bound relaxation, and fixed-variable controls are first-class options. The high-impact options in this section are `nlp_scaling_method`, `nlp_scaling_max_gradient`, `bound_relax_factor`, `honor_original_bounds`, `fixed_variable_treatment`, `bound_push`, `bound_frac`, `least_square_init_primal`, and `least_square_init_duals`. ([coin-or.github.io][1])

---

## 11.1 Pyomo option deployment syntax

### Persistent solver-object options

```python id="g92bqk"
import pyomo.environ as pyo

opt = pyo.SolverFactory("ipopt")
opt.options.update({
    "nlp_scaling_method": "gradient-based",
    "nlp_scaling_max_gradient": 100.0,
    "bound_relax_factor": 1e-8,
    "fixed_variable_treatment": "make_parameter",
    "bound_push": 1e-2,
    "bound_frac": 1e-2,
})
results = opt.solve(model, tee=True)
```

### Solve-local options

```python id="67s8c5"
results = opt.solve(
    model,
    tee=True,
    options={
        "nlp_scaling_method": "none",
        "bound_relax_factor": 0.0,
        "fixed_variable_treatment": "make_constraint",
    },
)
```

### `ipopt.opt`

```text id="4v87hg"
# ipopt.opt
nlp_scaling_method gradient-based
nlp_scaling_max_gradient 100
bound_relax_factor 1e-8
honor_original_bounds no
fixed_variable_treatment make_parameter
bound_push 1e-2
bound_frac 1e-2
```

Ipopt option files use `option_name value` lines with `#` comments; the docs show this exact syntax pattern for `nlp_scaling_method`, `mu_init`, and `max_iter`. ([coin-or.github.io][2])

---

## 11.2 NLP scaling: `nlp_scaling_method`

### Option surface

```python id="v3n2wx"
opt.options["nlp_scaling_method"] = "gradient-based"
```

Valid values:

```text id="178e8g"
none
user-scaling
gradient-based
equilibration-based
```

Ipopt’s `nlp_scaling_method` selects the internal problem-scaling technique; default is `gradient-based`. `none` disables problem scaling; `user-scaling` uses scaling supplied by the NLP; `gradient-based` scales so the maximum gradient at the starting point is `nlp_scaling_max_gradient`; `equilibration-based` tries to scale first derivatives to order 1 at random points using MC19. ([coin-or.github.io][2])

### Default / baseline

```python id="83qf7x"
opt.options.update({
    "nlp_scaling_method": "gradient-based",
    "nlp_scaling_max_gradient": 100.0,
})
```

### Disable scaling

```python id="ydy9ix"
opt.options["nlp_scaling_method"] = "none"
```

### User scaling

```python id="5cv0eq"
m.scaling_factor = pyo.Suffix(direction=pyo.Suffix.EXPORT)

m.scaling_factor[m.obj] = 1e-3
m.scaling_factor[m.mass_balance] = 1e2
m.scaling_factor[m.x] = 1e-1

opt.options["nlp_scaling_method"] = "user-scaling"
```

### Equilibration-based scaling

```python id="h3t23l"
opt.options["nlp_scaling_method"] = "equilibration-based"
```

**Agent rule**

```text id="0npj1s"
Default:
  gradient-based

Use user-scaling:
  when domain modeler supplies physically meaningful scale factors

Use none:
  when model is already nondimensionalized
  when automatic scaling hides physical residual interpretation
  when debugging raw residuals / derivative magnitudes
  when gradient-based scaling produces misleading unscaled feasibility

Use equilibration-based:
  advanced experiment only; requires Harwell MC19 availability/path in build
```

---

## 11.3 Gradient-based scaling: `nlp_scaling_max_gradient`, target-gradient controls

### Main cutoff

```python id="z0dw3g"
opt.options.update({
    "nlp_scaling_method": "gradient-based",
    "nlp_scaling_max_gradient": 100.0,
})
```

`nlp_scaling_max_gradient` is only used when `nlp_scaling_method=gradient-based`; if the maximum gradient exceeds this value, Ipopt computes scaling factors to bring that maximum gradient back to the cutoff. Its default is `100`. ([coin-or.github.io][2])

### Objective/constraint target-gradient overrides

```python id="9pwdu8"
opt.options.update({
    "nlp_scaling_method": "gradient-based",
    "nlp_scaling_obj_target_gradient": 10.0,
    "nlp_scaling_constr_target_gradient": 10.0,
})
```

Ipopt exposes advanced objective and constraint target-gradient options; positive values override `nlp_scaling_max_gradient` for the objective or constraint functions respectively. ([coin-or.github.io][2])

### Minimum scaling factor

```python id="kcxu6s"
opt.options.update({
    "nlp_scaling_method": "gradient-based",
    "nlp_scaling_min_value": 1e-8,
})
```

`nlp_scaling_min_value` limits how small gradient-based scaling factors can become; Ipopt’s docs explicitly warn that very small scaling factors caused by huge derivatives can make the final unscaled constraint violation significant. ([coin-or.github.io][2])

### Scaling-value case

```text id="1mc6a2"
gradient-based scaling helps when:
  objective gradient norm ≫ constraint gradient norm
  units mix pressure/temperature/flow/cost
  raw derivatives span many orders of magnitude
  line search struggles due to derivative scale
  dual infeasibility is dominated by large-gradient rows

gradient-based scaling can hurt interpretation when:
  reported scaled optimality looks good but unscaled residuals matter physically
  large derivative is caused by bad units or singular start
  modeler expects unscaled feasibility thresholds as primary contract
```

---

## 11.4 Manual nondimensionalization: preferred modeling-layer scaling

### Bad raw-units model

```python id="9r8z1n"
m.P = pyo.Var(bounds=(1e5, 1e7), initialize=1e6)       # Pa
m.F = pyo.Var(bounds=(1e-6, 1e-2), initialize=1e-4)    # mol/s
m.C = pyo.Var(bounds=(0, 1e9), initialize=1e6)         # cost units

m.obj = pyo.Objective(expr=m.C + 1e9 * (m.F - 1e-4)**2)
```

### Scaled variables

```python id="bsk0ei"
P_ref = 1e6
F_ref = 1e-4
C_ref = 1e6

m.P_hat = pyo.Var(bounds=(0.1, 10.0), initialize=1.0)
m.F_hat = pyo.Var(bounds=(0.01, 100.0), initialize=1.0)
m.C_hat = pyo.Var(bounds=(0.0, 1000.0), initialize=1.0)

P = P_ref * m.P_hat
F = F_ref * m.F_hat
C = C_ref * m.C_hat

m.obj = pyo.Objective(expr=m.C_hat + (m.F_hat - 1.0)**2)
```

### Agent policy

```text id="62ion8"
Preferred hierarchy:
  1. nondimensionalize model variables/constraints in Pyomo
  2. add user scaling suffixes when explicit physical scaling is known
  3. rely on gradient-based scaling as safety net
  4. disable scaling only for already-scaled models or diagnostics
```

---

## 11.5 Bound relaxation: `bound_relax_factor`

### Default behavior

```python id="loce9a"
opt.options["bound_relax_factor"] = 1e-8
```

`bound_relax_factor` controls initial relaxation of variable bounds before optimization. If it is set to zero, bound relaxation is disabled. Ipopt also caps the absolute relaxation using `constr_viol_tol`; importantly, the final constraint violation reported by Ipopt does **not** include violations of original non-relaxed variable bounds. ([coin-or.github.io][1])

### Disable bound relaxation

```python id="8jk48k"
opt.options["bound_relax_factor"] = 0.0
```

### Project final point into original bounds

```python id="cnlpvw"
opt.options["honor_original_bounds"] = "yes"
```

`honor_original_bounds` determines whether Ipopt projects the final point back into the original user-provided bounds after optimization; the docs note that reported constraint/complementarity violations are for the non-projected point. Default is `no`. ([coin-or.github.io][1])

### Bound-relaxation diagnostic profile

```python id="xk7hwg"
opt.options.update({
    "bound_relax_factor": 0.0,
    "honor_original_bounds": "yes",
    "constr_viol_tol": 1e-8,
    "print_user_options": "yes",
})
```

### Agent decision table

| Situation                                     |                                      Suggested setting | Reason                                                                |
| --------------------------------------------- | -----------------------------------------------------: | --------------------------------------------------------------------- |
| ordinary smooth NLP                           |                                         default `1e-8` | mild numerical buffer                                                 |
| strict physical bound contract                |                               `bound_relax_factor=0.0` | no hidden original-bound relaxation                                   |
| regulatory/safety bounds                      |                    `0.0` + manual bound residual audit | reported Ipopt violation may exclude original relaxed-bound violation |
| warm-start near active bounds                 |            small positive default or warm-start pushes | interior-point needs nonzero interior margin                          |
| final loaded values must obey original bounds | `honor_original_bounds=yes` plus manual residual audit | projection changes final point semantics                              |

### Original-bound audit helper

```python id="hoj0tq"
import pyomo.environ as pyo

def original_bound_violations(model, tol=1e-9):
    rows = []
    for v in model.component_data_objects(pyo.Var, active=True):
        val = pyo.value(v, exception=False)
        if val is None:
            continue

        lb = pyo.value(v.lb, exception=False) if v.lb is not None else None
        ub = pyo.value(v.ub, exception=False) if v.ub is not None else None

        lviol = 0.0 if lb is None else max(0.0, lb - val)
        uviol = 0.0 if ub is None else max(0.0, val - ub)
        viol = max(lviol, uviol)

        if viol > tol:
            rows.append((v.name, val, lb, ub, viol))
    return sorted(rows, key=lambda r: r[-1], reverse=True)
```

---

## 11.6 `constr_viol_tol` interaction

```python id="4l4qgu"
opt.options.update({
    "constr_viol_tol": 1e-6,
    "bound_relax_factor": 1e-8,
})
```

`constr_viol_tol` is the absolute tolerance for constraint and variable-bound violation required for successful termination, and if `bound_relax_factor` is nonzero, `constr_viol_tol` restricts the absolute amount by which Ipopt relaxes variable bounds. ([coin-or.github.io][1])

### Agent rule

```text id="or2z77"
If strict bound feasibility matters:
  set bound_relax_factor=0
  set constr_viol_tol to physical feasibility tolerance
  audit original bounds manually after solve

If numerical robustness matters more:
  keep small bound_relax_factor
  understand reported final constraint violation excludes original relaxed-bound violations
```

---

## 11.7 Fixed variable treatment: `fixed_variable_treatment`

### Option surface

```python id="jv0nei"
opt.options["fixed_variable_treatment"] = "make_parameter"
```

Valid values:

```text id="6o1ccz"
make_parameter
make_parameter_nodual
make_constraint
relax_bounds
```

Ipopt’s `fixed_variable_treatment` determines how fixed variables are handled. Default is `make_parameter`. The docs distinguish `make_constraint`—where the starting point still has fixed variables at their given values—from `make_parameter`/`make_parameter_nodual`, where functions are evaluated with fixed values; `relax_bounds` relaxes fixing bounds according to `bound_relax_factor`. Bound multipliers are computed for fixed variables for all choices except `make_parameter_nodual`. ([coin-or.github.io][1])

### Pyomo fixed-variable syntax

```python id="beazx3"
m.x.fix(3.0)
m.x.unfix()
m.x.free()  # alias for unfix()
```

For scalar variable data, Pyomo’s `fix(value=...)` treats the variable as nonvariable and optionally sets the value first; `unfix()` treats it as a variable again; `free()` is an alias for `unfix()`. Pyomo’s `set_value()` checks units, domain, and bounds unless `skip_validation=True` is supplied. ([Pyomo Documentation][3])

### Treatment semantics

| Ipopt setting           | What happens                                                                           | Multiplier implication                    | Agent use                                                                    |
| ----------------------- | -------------------------------------------------------------------------------------- | ----------------------------------------- | ---------------------------------------------------------------------------- |
| `make_parameter`        | remove fixed variable from optimization variables; evaluate functions with fixed value | fixed-variable bound multipliers computed | default; good for most fixed design variables                                |
| `make_parameter_nodual` | remove fixed variable and do not compute bound multipliers                             | no fixed-variable bound multipliers       | use when multipliers for fixed vars irrelevant or problematic                |
| `make_constraint`       | add equality constraints fixing variables                                              | multipliers available through constraints | use when fixed-variable multiplier interpretation as equality row is desired |
| `relax_bounds`          | relax fixing bound constraints according to `bound_relax_factor`                       | bound treatment affected by relaxation    | use rarely; diagnostic/numerical escape hatch                                |

### Pyomo pattern: fixed design subproblem

```python id="iamh27"
for i in m.design_index:
    m.design[i].fix(design_value[i])

opt.options["fixed_variable_treatment"] = "make_parameter"
res = opt.solve(m, tee=True)

for i in m.design_index:
    m.design[i].unfix()
```

### Pyomo pattern: want fixed-variable multipliers as constraints

```python id="6g8rec"
m.x.fix(3.0)

opt.options.update({
    "fixed_variable_treatment": "make_constraint",
})

# optionally import duals
m.dual = pyo.Suffix(direction=pyo.Suffix.IMPORT)
res = opt.solve(m, tee=True)
```

### Agent rule

```text id="i1hl3y"
Default:
  make_parameter

Use make_constraint:
  sensitivity/multiplier interpretation for fixed variables needed

Use make_parameter_nodual:
  no bound multipliers needed for fixed variables

Avoid relax_bounds:
  unless knowingly allowing fixed-value relaxation for numerical reasons
```

---

## 11.8 Starting values: Pyomo construction-time initialization

### Scalar variable

```python id="8dstsa"
m.x = pyo.Var(bounds=(0.0, 10.0), initialize=1.0)
```

### Indexed variable

```python id="7qwzip"
m.I = pyo.Set(initialize=["A", "B", "C"])

def x_init(m, i):
    return {"A": 1.0, "B": 2.0, "C": 3.0}[i]

m.x = pyo.Var(m.I, bounds=(0.0, None), initialize=x_init)
```

Pyomo `Var` supports `domain`, `bounds`, and `initialize`; `initialize` may be a float or a rule returning initial values, while `rule` is an alias for `initialize`. Bounds default to `(None, None)`, and domain defaults to `Reals`. ([Pyomo Documentation][4])

### After construction: `.value` assignment

```python id="algl9t"
m.x.value = 2.0

for i in m.I:
    m.x[i].value = x0[i]
```

### After construction: `set_value`

```python id="vrzoyq"
m.x.set_value(2.0)
m.x.set_value(2.0, skip_validation=True)
```

Pyomo `VarData.set_value(val, skip_validation=False)` sets the current variable value, evaluates expressions, converts units if needed, and validates domain/bounds unless `skip_validation=True` is used. ([Pyomo Documentation][3])

### Bulk initialization helper

```python id="9x3qgg"
def initialize_from_dict(var, values, *, skip_validation=False):
    for idx, val in values.items():
        var[idx].set_value(val, skip_validation=skip_validation)
```

---

## 11.9 Starting-point boundary pushes: `bound_push`, `bound_frac`, slack analogues

```python id="khhcjw"
opt.options.update({
    "bound_push": 1e-2,
    "bound_frac": 1e-2,
    "slack_bound_push": 1e-2,
    "slack_bound_frac": 1e-2,
})
```

`bound_push` and `bound_frac` determine how much Ipopt may modify the initial point to be sufficiently inside variable bounds. `slack_bound_push` and `slack_bound_frac` do the same for initial slack variables. Defaults are `0.01` for all four controls, with `bound_frac` and `slack_bound_frac` constrained to at most `0.5`. ([coin-or.github.io][1])

### Use cases

```text id="poefyo"
Increase pushes:
  starts exactly on bounds cause line-search/barrier issues
  log/sqrt/division domains need strict interior
  complementarity-like active bounds create numerical fragility

Decrease pushes:
  user start is high-quality and close to active-bound solution
  warm-start profile with explicit warm_start_* push controls
  small feasible interval would be overly disturbed
```

### Agent-safe start-inside-bounds function

```python id="1rlhw8"
def interior_start(lb, ub, default=1.0, frac=0.1, eps=1e-8):
    if lb is not None and ub is not None:
        if ub <= lb:
            return lb
        return lb + frac * (ub - lb)
    if lb is not None:
        return lb + max(eps, frac * max(1.0, abs(lb)))
    if ub is not None:
        return ub - max(eps, frac * max(1.0, abs(ub)))
    return default
```

### Apply starts to model

```python id="2lhiaj"
def initialize_unset_variables(model, default=1.0, frac=0.1):
    for v in model.component_data_objects(pyo.Var, active=True):
        if v.fixed or v.value is not None:
            continue

        lb = pyo.value(v.lb, exception=False) if v.lb is not None else None
        ub = pyo.value(v.ub, exception=False) if v.ub is not None else None

        v.set_value(interior_start(lb, ub, default=default, frac=frac), skip_validation=True)
```

---

## 11.10 Heuristics for badly initialized nonlinear models

### Failure symptoms

```text id="ck57ga"
undefined objective/constraint at start
log/sqrt/division domain error
NaN/Inf derivative
Restoration_Failed immediately
tiny-step termination
large primal infeasibility from first iteration
line search stalls
dual infeasibility enormous due to scale
```

### Heuristic ladder

```text id="rxwngv"
1. Initialize every variable used in nonlinear expressions.
2. Move starts strictly inside finite bounds.
3. Protect log/sqrt/division domains with lower bounds and positive starts.
4. Use physically plausible starts for nonlinear equality systems.
5. Fix a subset of difficult variables; solve easier subproblem; unfix gradually.
6. Use continuation/homotopy on hard parameters.
7. Use least_square_init_primal only when user starts are unknown or low-value.
8. Use derivative checker after starts are evaluable.
```

### Domain-protected variables

```python id="oc83ch"
eps = 1e-8

m.conc = pyo.Var(bounds=(eps, None), initialize=1.0)  # log(conc)
m.rad  = pyo.Var(bounds=(eps, None), initialize=1.0)  # sqrt(rad)
m.den  = pyo.Var(bounds=(eps, None), initialize=1.0)  # numerator / den
```

### Continuation pattern

```python id="3pzr91"
m.alpha = pyo.Param(initialize=0.0, mutable=True)

# hard constraint relaxed by alpha
m.c = pyo.Constraint(expr=(1 - m.alpha) * easy_expr + m.alpha * hard_expr == rhs)

opt = pyo.SolverFactory("ipopt")
opt.options["tol"] = 1e-8

for a in [0.0, 0.25, 0.5, 0.75, 1.0]:
    m.alpha.set_value(a)
    res = opt.solve(m, tee=True)
```

### Progressive unfixing pattern

```python id="qunvix"
# Stage 1: fix hard variables at plausible values
for v in hard_vars:
    v.fix(plausible[v])

opt.solve(m, tee=True)

# Stage 2: unfix and use stage-1 solution as start
for v in hard_vars:
    v.unfix()

opt.solve(m, tee=True)
```

---

## 11.11 Least-square initialization: `least_square_init_primal`

```python id="ohofjr"
opt.options["least_square_init_primal"] = "yes"
```

If `least_square_init_primal=yes`, Ipopt ignores the user-provided point and solves a least-square problem for primal variables and slacks to fit the linearized equality and inequality constraints. Ipopt documents this as useful when the user does not know anything about the starting point, or for LP/QP-like problems; the default is `no`. ([coin-or.github.io][1])

### Use case

```text id="df0vz1"
Use least_square_init_primal=yes when:
  all starts are arbitrary placeholders
  constraints are mostly linear or mildly nonlinear near start
  LP/QP-like model routed through Ipopt
  feasibility is more important than preserving user start
```

### Avoid

```text id="rbetde"
Avoid least_square_init_primal=yes when:
  user start is a good warm start
  variables have semantic start values
  nonlinear constraints are highly nonconvex
  least-square linearization around poor point is misleading
  log/sqrt/domain constraints require handcrafted safe starts
```

### Diagnostic profile

```python id="nfgbol"
opt.options.update({
    "least_square_init_primal": "yes",
    "print_user_options": "yes",
    "print_level": 5,
})
```

---

## 11.12 Least-square initialization: `least_square_init_duals`

```python id="kvwbjf"
opt.options["least_square_init_duals"] = "yes"
```

If `least_square_init_duals=yes`, Ipopt tries to compute least-square multipliers considering all dual variables; if successful, bound multipliers may be corrected to be at least `bound_mult_init_val`. The option overwrites `bound_mult_init_method`; default is `no`. ([coin-or.github.io][1])

### Related dual-init options

```python id="9mmvhk"
opt.options.update({
    "constr_mult_init_max": 1000.0,
    "bound_mult_init_val": 1.0,
    "bound_mult_init_method": "constant",
})
```

Ipopt’s initialization options include `constr_mult_init_max`, `bound_mult_init_val`, and `bound_mult_init_method`; `bound_mult_init_method=constant` initializes all bound multipliers to `bound_mult_init_val`, while `mu-based` initializes bound multipliers from `mu_init` divided by the corresponding slack and may be useful when the start is close to optimal. ([coin-or.github.io][1])

### Use case

```text id="jdm8lu"
least_square_init_duals=yes:
  poor/no multiplier estimates
  LP/QP-like model
  direct interface with no useful dual starts
  diagnostic comparison against default dual initialization

not a substitute for:
  Pyomo warm-start suffixes
  valid primal starts
  feasible model formulation
```

---

## 11.13 Initialization profile catalog

### Default robust profile

```python id="6bcsk9"
IPOPT_INIT_DEFAULT = {
    "bound_push": 1e-2,
    "bound_frac": 1e-2,
    "slack_bound_push": 1e-2,
    "slack_bound_frac": 1e-2,
    "least_square_init_primal": "no",
    "least_square_init_duals": "no",
}
```

### Unknown-start profile

```python id="cbi669"
IPOPT_INIT_UNKNOWN_START = {
    "least_square_init_primal": "yes",
    "least_square_init_duals": "yes",
    "bound_push": 1e-2,
    "bound_frac": 1e-2,
}
```

### High-quality warm-ish start profile

```python id="aisvmo"
IPOPT_INIT_RESPECT_START = {
    "least_square_init_primal": "no",
    "least_square_init_duals": "no",
    "bound_push": 1e-4,
    "bound_frac": 1e-4,
}
```

### Strict-bound profile

```python id="7pnm5v"
IPOPT_STRICT_BOUNDS = {
    "bound_relax_factor": 0.0,
    "honor_original_bounds": "yes",
    "constr_viol_tol": 1e-8,
}
```

### Pre-scaled model profile

```python id="qozqwj"
IPOPT_PRESCALED = {
    "nlp_scaling_method": "none",
}
```

### Auto-scaled model profile

```python id="5yux8u"
IPOPT_AUTOSCALED = {
    "nlp_scaling_method": "gradient-based",
    "nlp_scaling_max_gradient": 100.0,
    "nlp_scaling_min_value": 1e-8,
}
```

---

## 11.14 Scaling suffix pattern in Pyomo

```python id="gzlcbb"
m.scaling_factor = pyo.Suffix(direction=pyo.Suffix.EXPORT)

# Variable scaling
m.scaling_factor[m.x] = 0.1

# Constraint row scaling
m.scaling_factor[m.mass_balance] = 100.0

# Objective scaling
m.scaling_factor[m.obj] = 1e-3

opt.options["nlp_scaling_method"] = "user-scaling"
```

Ipopt’s docs state that user scaling parameters come from the NLP; for AMPL-style workflows they can be specified through the `scaling_factor` suffix. Pyomo’s NL-writer path can export suffixes to the solver interface, making this the natural Pyomo mechanism for explicit user scaling. ([coin-or.github.io][2])

### Agent policy

```text id="fx2fl9"
Use scaling_factor suffix when:
  physical units imply known row/variable scales
  automatic scaling is unstable across starts
  benchmark reproducibility requires explicit scaling
  final unscaled feasibility must be controlled

Avoid arbitrary suffix scaling:
  if not tied to units/residual magnitudes
  if it hides modeling errors
  if it makes objective/constraint tradeoffs opaque
```

---

## 11.15 Start/scale/bound diagnostic helper

```python id="i53zji"
from __future__ import annotations

import math
import pyomo.environ as pyo


def ipopt_start_scale_bound_report(model):
    rows = []

    for v in model.component_data_objects(pyo.Var, active=True):
        val = pyo.value(v, exception=False)
        lb = pyo.value(v.lb, exception=False) if v.lb is not None else None
        ub = pyo.value(v.ub, exception=False) if v.ub is not None else None

        flags = []

        if not v.fixed and val is None:
            flags.append("NO_START")

        if val is not None:
            try:
                if not math.isfinite(float(val)):
                    flags.append("NONFINITE_START")
            except Exception:
                flags.append("NONNUMERIC_START")

        if lb is not None and ub is not None and lb > ub:
            flags.append("BAD_BOUNDS")

        if lb is None and ub is None and not v.fixed:
            flags.append("FREE_VAR")

        if lb is not None and abs(lb) >= 1e19:
            flags.append("HUGE_LB")

        if ub is not None and abs(ub) >= 1e19:
            flags.append("HUGE_UB")

        if val is not None and lb is not None and abs(val - lb) <= 1e-12:
            flags.append("AT_LB")

        if val is not None and ub is not None and abs(val - ub) <= 1e-12:
            flags.append("AT_UB")

        rows.append({
            "name": v.name,
            "value": val,
            "lb": lb,
            "ub": ub,
            "fixed": v.fixed,
            "flags": flags,
        })

    return rows


for row in ipopt_start_scale_bound_report(m):
    if row["flags"]:
        print(row)
```

---

## 11.16 Solve policy wrapper

```python id="ia3ho8"
import pyomo.environ as pyo


def configure_ipopt_scaling_initialization(
    opt,
    *,
    scaling: str = "auto",       # auto | none | user
    strict_bounds: bool = False,
    fixed_treatment: str = "make_parameter",
    unknown_start: bool = False,
):
    if scaling == "auto":
        opt.options.update({
            "nlp_scaling_method": "gradient-based",
            "nlp_scaling_max_gradient": 100.0,
            "nlp_scaling_min_value": 1e-8,
        })
    elif scaling == "none":
        opt.options["nlp_scaling_method"] = "none"
    elif scaling == "user":
        opt.options["nlp_scaling_method"] = "user-scaling"
    else:
        raise ValueError(scaling)

    if strict_bounds:
        opt.options.update({
            "bound_relax_factor": 0.0,
            "honor_original_bounds": "yes",
        })
    else:
        opt.options.update({
            "bound_relax_factor": 1e-8,
            "honor_original_bounds": "no",
        })

    opt.options["fixed_variable_treatment"] = fixed_treatment

    if unknown_start:
        opt.options.update({
            "least_square_init_primal": "yes",
            "least_square_init_duals": "yes",
        })
    else:
        opt.options.update({
            "least_square_init_primal": "no",
            "least_square_init_duals": "no",
        })

    return opt
```

Usage:

```python id="b6i2mr"
opt = pyo.SolverFactory("ipopt")
configure_ipopt_scaling_initialization(
    opt,
    scaling="auto",
    strict_bounds=False,
    fixed_treatment="make_parameter",
    unknown_start=False,
)
res = opt.solve(m, tee=True)
```

---

## 11.17 Decision table

| Problem trait                    | Scaling policy                            | Init policy                               | Bound policy                         | Fixed-var policy                     |
| -------------------------------- | ----------------------------------------- | ----------------------------------------- | ------------------------------------ | ------------------------------------ |
| well-nondimensionalized model    | `nlp_scaling_method=none` or default auto | user starts                               | default relaxation or strict         | `make_parameter`                     |
| raw mixed-unit engineering model | `gradient-based`, then manual scaling     | interior starts                           | default small relaxation             | `make_parameter`                     |
| strict physical bounds           | scaling independent                       | interior starts                           | `bound_relax_factor=0`, audit bounds | `make_parameter`                     |
| fixed design variables           | any                                       | normal                                    | default                              | `make_parameter`                     |
| need fixed-variable multipliers  | any                                       | normal                                    | default                              | `make_constraint`                    |
| no meaningful starts             | gradient-based                            | `least_square_init_primal=yes` experiment | default                              | default                              |
| LP/QP-like NLP                   | any                                       | least-square primal/duals can help        | default                              | default                              |
| warm-started NLP                 | usually same as previous solve            | preserve values/duals                     | warm-start pushes, not least-square  | fixed policy matched to suffix needs |

---

## 11.18 Anti-patterns for LLM agents

```text id="l9hw4r"
BAD:
  set nlp_scaling_method none on raw mixed-unit model by default.

GOOD:
  use gradient-based scaling or explicit user scaling.

BAD:
  rely on bound_relax_factor default when original bounds are regulatory hard constraints.

GOOD:
  set bound_relax_factor=0 and audit final original bound residuals.

BAD:
  use least_square_init_primal=yes while also claiming user-provided warm start is respected.

GOOD:
  least_square_init_primal=yes means Ipopt ignores user primal start.

BAD:
  fix variables and assume multiplier interpretation is unchanged across fixed_variable_treatment modes.

GOOD:
  choose make_parameter / make_constraint / make_parameter_nodual intentionally.

BAD:
  initialize log(x) variable at x=0 because lower bound is 0.

GOOD:
  lower bound x >= eps and initialize x > eps.

BAD:
  use 1e20 fake bounds and then tune scaling.

GOOD:
  use None for infinity, physical finite bounds for real limits, rescale huge quantities.
```

---

## 11.19 Final checklist

```text id="11ehk1"
[ ] Decide scaling policy: gradient-based / user-scaling / none.
[ ] Prefer model-layer nondimensionalization before solver-layer scaling.
[ ] Use scaling_factor suffix for known physical row/variable/objective scales.
[ ] Keep nlp_scaling_method=gradient-based as safe default for raw models.
[ ] Disable scaling only for pre-scaled or diagnostic runs.
[ ] Understand nlp_scaling_max_gradient applies only to gradient-based scaling.
[ ] Set bound_relax_factor=0 for strict original-bound contracts.
[ ] Remember Ipopt-reported final violation can exclude original relaxed-bound violations.
[ ] Use honor_original_bounds=yes only with awareness of projection semantics.
[ ] Choose fixed_variable_treatment deliberately.
[ ] Use make_parameter as default fixed-variable handling.
[ ] Use make_constraint when fixed-variable dual interpretation matters.
[ ] Initialize every nonlinear variable.
[ ] Move starts strictly inside domains for log/sqrt/division.
[ ] Use .set_value(..., skip_validation=False) unless deliberately bypassing validation.
[ ] Use least_square_init_primal=yes only when user starts are poor/unknown.
[ ] Use least_square_init_duals=yes only for multiplier initialization experiments.
[ ] Run start/bounds diagnostic before blaming Ipopt.
```

[1]: https://coin-or.github.io/Ipopt/OPTIONS.html "Ipopt: Ipopt Options"
[2]: https://coin-or.github.io/Ipopt/OPTIONS.html?utm_source=chatgpt.com "Ipopt: Ipopt Options"
[3]: https://pyomo.readthedocs.io/en/stable/api/pyomo.core.base.var.VarData.html "VarData — Pyomo 6.10.0 documentation"
[4]: https://pyomo.readthedocs.io/en/latest/api/pyomo.core.base.var.Var.html "Var — Pyomo 6.10.1.dev0 documentation"

# Ipopt Advanced — Section 12: warm starts in Pyomo + Ipopt

Style target: dense advanced technical catalog / agent-ready reference. 

## 12.0 Warm-start invariant

```text id="n6q5zw"
Ipopt warm start =
  primal variable starting values
  + constraint multipliers
  + lower-bound multipliers
  + upper-bound multipliers
  + warm-start-specific interior-push / barrier options
```

Ipopt’s warm-start documentation states that using only primal values and active constraint multipliers is incomplete for an interior-point method because bound multiplier information `zL` and `zU` for variable bounds is also needed; Ipopt exposes these as `ipopt_zL_out` and `ipopt_zU_out`, and accepts them back through `ipopt_zL_in` and `ipopt_zU_in`. It also warns that warm starts help mainly when subsequent problems preserve similar active inequalities and bounds; active-set changes can reduce or reverse the benefit. ([COIN-OR Documentation][1])

---

## 12.1 What “warm start” means in this stack

```text id="zrmt9j"
Pyomo warm-start payload:
  Var.value                → primal x start
  model.dual              → constraint multiplier λ start
  model.ipopt_zL_in        → lower-bound multiplier zL start
  model.ipopt_zU_in        → upper-bound multiplier zU start

Ipopt warm-start options:
  warm_start_init_point yes
  warm_start_bound_push small
  warm_start_mult_bound_push small
  mu_init small
```

Pyomo’s NL interface treats an export-style suffix named `dual` specially as constraint-multiplier initialization, and Pyomo’s own Ipopt warm-start example declares `ipopt_zL_out` / `ipopt_zU_out` as import suffixes, `ipopt_zL_in` / `ipopt_zU_in` as export suffixes, and `dual` as an import-export suffix. ([Pyomo Documentation][2])

---

## 12.2 Suffix directions: exact Pyomo semantics

```python id="6jo0pa"
model.local_only = pyo.Suffix(direction=pyo.Suffix.LOCAL)
model.imported   = pyo.Suffix(direction=pyo.Suffix.IMPORT)
model.exported   = pyo.Suffix(direction=pyo.Suffix.EXPORT)
model.round_trip = pyo.Suffix(direction=pyo.Suffix.IMPORT_EXPORT)
```

```text id="cgou2j"
LOCAL:
  suffix data stays inside Pyomo; not passed to/from solver

IMPORT:
  suffix data imported from solver solution into Pyomo

EXPORT:
  suffix data exported from Pyomo to solver

IMPORT_EXPORT:
  suffix data imported from solver and exported to solver
```

Pyomo documents these four suffix directions and states that suffix import/export compatibility depends on the solver and solver interface; it also notes that exporting suffix data through the NL file interface requires active export suffixes to have a strict datatype. ([Pyomo Documentation][2])

---

## 12.3 Required Pyomo suffix declarations for Ipopt warm starts

```python id="komr4f"
import pyomo.environ as pyo

# Constraint multipliers: imported after solve; exported on next solve.
model.dual = pyo.Suffix(direction=pyo.Suffix.IMPORT_EXPORT)

# Bound multipliers imported from Ipopt solution.
model.ipopt_zL_out = pyo.Suffix(direction=pyo.Suffix.IMPORT)
model.ipopt_zU_out = pyo.Suffix(direction=pyo.Suffix.IMPORT)

# Bound multipliers exported back to Ipopt for warm start.
model.ipopt_zL_in = pyo.Suffix(direction=pyo.Suffix.EXPORT)
model.ipopt_zU_in = pyo.Suffix(direction=pyo.Suffix.EXPORT)
```

Pyomo’s warm-start example uses exactly these suffix names and directions, with `ipopt_zL_out` / `ipopt_zU_out` for lower/upper bound multipliers imported from Ipopt, `ipopt_zL_in` / `ipopt_zU_in` for lower/upper bound multipliers exported to Ipopt, and `dual` as `IMPORT_EXPORT` for constraint multipliers. ([Pyomo Documentation][2])

---

## 12.4 Core Ipopt warm-start options

### Minimal warm-start option set

```python id="nxfky7"
opt.options.update({
    "warm_start_init_point": "yes",
    "warm_start_bound_push": 1e-6,
    "warm_start_mult_bound_push": 1e-6,
    "mu_init": 1e-6,
})
```

Ipopt’s warm-start documentation identifies `warm_start_init_point`, `warm_start_bound_push`, and `warm_start_mult_bound_push` as the key controls, and specifically recommends setting those push values and `mu_init` to a small value such as `1e-6` when subsequent problems preserve the active set. ([COIN-OR Documentation][1])

### Option semantics

| Option                       |   Type | Role                                                       | Agent setting                               |
| ---------------------------- | -----: | ---------------------------------------------------------- | ------------------------------------------- |
| `warm_start_init_point`      | String | instructs Ipopt to use warm-start primal/dual information  | `"yes"`                                     |
| `warm_start_bound_push`      | Number | pushes warm-start primal variables inside bounds           | `1e-6` to `1e-4` typical                    |
| `warm_start_mult_bound_push` | Number | pushes warm-start bound multipliers inside feasible region | `1e-6` to `1e-4` typical                    |
| `mu_init`                    | Number | initial barrier parameter                                  | small when warm start is close, e.g. `1e-6` |
| `mu_strategy`                | String | optional adaptive barrier strategy                         | test `"adaptive"` as variant                |

Ipopt notes that adaptive barrier updates may reduce iterations for warm starts in some cases, but the computational cost per iteration can be higher; this should be benchmarked rather than assumed. ([COIN-OR Documentation][1])

---

## 12.5 Canonical Pyomo warm-start recipe

### Step 1: declare suffixes before first solve

```python id="nw9zce"
model.dual = pyo.Suffix(direction=pyo.Suffix.IMPORT_EXPORT)

model.ipopt_zL_out = pyo.Suffix(direction=pyo.Suffix.IMPORT)
model.ipopt_zU_out = pyo.Suffix(direction=pyo.Suffix.IMPORT)

model.ipopt_zL_in = pyo.Suffix(direction=pyo.Suffix.EXPORT)
model.ipopt_zU_in = pyo.Suffix(direction=pyo.Suffix.EXPORT)
```

### Step 2: first solve; import primal and multipliers

```python id="17vm6k"
ipopt = pyo.SolverFactory("ipopt")
ipopt.options.update({
    "tol": 1e-8,
    "print_level": 5,
})

results = ipopt.solve(model, tee=True)
```

### Step 3: modify related problem data, preserving structure if possible

```python id="vbgvfn"
# Example: mutable parameter update
model.p.set_value(new_p_value)

# Optional: previous Var.value values remain as primal warm-start values.
```

### Step 4: copy imported bound multipliers into export suffixes

```python id="2a6iwb"
model.ipopt_zL_in.update(model.ipopt_zL_out)
model.ipopt_zU_in.update(model.ipopt_zU_out)
```

Pyomo’s documented warm-start example copies `model.ipopt_zL_out` into `model.ipopt_zL_in` and `model.ipopt_zU_out` into `model.ipopt_zU_in`, then sets `warm_start_init_point`, `warm_start_bound_push`, `warm_start_mult_bound_push`, and `mu_init` before the next solve. ([Pyomo Documentation][2])

### Step 5: second solve with warm-start options

```python id="73fekm"
ipopt.options.update({
    "warm_start_init_point": "yes",
    "warm_start_bound_push": 1e-6,
    "warm_start_mult_bound_push": 1e-6,
    "mu_init": 1e-6,
})

results = ipopt.solve(model, tee=True)
```

---

## 12.6 Full executable example: HS071-style warm start

```python id="8805hw"
import pyomo.environ as pyo


def build_model():
    m = pyo.ConcreteModel()

    m.x1 = pyo.Var(bounds=(1, 5), initialize=1.0)
    m.x2 = pyo.Var(bounds=(1, 5), initialize=5.0)
    m.x3 = pyo.Var(bounds=(1, 5), initialize=5.0)
    m.x4 = pyo.Var(bounds=(1, 5), initialize=1.0)

    m.obj = pyo.Objective(
        expr=m.x1 * m.x4 * (m.x1 + m.x2 + m.x3) + m.x3
    )

    m.inequality = pyo.Constraint(
        expr=m.x1 * m.x2 * m.x3 * m.x4 >= 25.0
    )

    m.equality = pyo.Constraint(
        expr=m.x1**2 + m.x2**2 + m.x3**2 + m.x4**2 == 40.0
    )

    # Warm-start suffixes
    m.dual = pyo.Suffix(direction=pyo.Suffix.IMPORT_EXPORT)
    m.ipopt_zL_out = pyo.Suffix(direction=pyo.Suffix.IMPORT)
    m.ipopt_zU_out = pyo.Suffix(direction=pyo.Suffix.IMPORT)
    m.ipopt_zL_in = pyo.Suffix(direction=pyo.Suffix.EXPORT)
    m.ipopt_zU_in = pyo.Suffix(direction=pyo.Suffix.EXPORT)

    return m


m = build_model()
ipopt = pyo.SolverFactory("ipopt")

print("INITIAL SOLVE")
res1 = ipopt.solve(m, tee=True)

print("Imported bound multipliers")
for v in [m.x1, m.x2, m.x3, m.x4]:
    print(v.name, pyo.value(v), m.ipopt_zL_out.get(v), m.ipopt_zU_out.get(v))

print("Imported constraint multipliers")
print("inequality.dual =", m.dual.get(m.inequality))
print("equality.dual   =", m.dual.get(m.equality))

# Copy bound multipliers for warm start.
m.ipopt_zL_in.update(m.ipopt_zL_out)
m.ipopt_zU_in.update(m.ipopt_zU_out)

ipopt.options.update({
    "warm_start_init_point": "yes",
    "warm_start_bound_push": 1e-6,
    "warm_start_mult_bound_push": 1e-6,
    "mu_init": 1e-6,
})

print("WARM-STARTED SOLVE")
res2 = ipopt.solve(m, tee=True)
```

Pyomo’s suffix documentation demonstrates this exact model pattern and reports an example reduction from 8 iterations without warm start to 2 iterations with warm start for the illustrated problem. ([Pyomo Documentation][2])

---

## 12.7 Warm start across a parametric sweep

### Model pattern: mutable parameter, fixed structure

```python id="ztsx98"
import pyomo.environ as pyo

m = pyo.ConcreteModel()
m.p = pyo.Param(initialize=1.0, mutable=True)

m.x = pyo.Var(bounds=(0.0, 10.0), initialize=1.0)
m.y = pyo.Var(bounds=(0.0, 10.0), initialize=1.0)

m.obj = pyo.Objective(expr=(m.x - m.p)**2 + (m.y - 2.0)**2)
m.c = pyo.Constraint(expr=m.x * m.y >= 1.0)

m.dual = pyo.Suffix(direction=pyo.Suffix.IMPORT_EXPORT)
m.ipopt_zL_out = pyo.Suffix(direction=pyo.Suffix.IMPORT)
m.ipopt_zU_out = pyo.Suffix(direction=pyo.Suffix.IMPORT)
m.ipopt_zL_in = pyo.Suffix(direction=pyo.Suffix.EXPORT)
m.ipopt_zU_in = pyo.Suffix(direction=pyo.Suffix.EXPORT)

ipopt = pyo.SolverFactory("ipopt")
ipopt.options.update({
    "tol": 1e-8,
    "print_level": 0,
})

# Cold solve
m.p.set_value(1.0)
res = ipopt.solve(m, tee=False)

# Warm-start options for subsequent related solves
ipopt.options.update({
    "warm_start_init_point": "yes",
    "warm_start_bound_push": 1e-6,
    "warm_start_mult_bound_push": 1e-6,
    "mu_init": 1e-6,
})

for p_value in [1.1, 1.2, 1.3, 1.4]:
    m.p.set_value(p_value)

    # Current Var.value values = primal starts.
    # Current model.dual values = constraint multiplier starts.
    # Copy latest bound multipliers into *_in suffixes.
    m.ipopt_zL_in.update(m.ipopt_zL_out)
    m.ipopt_zU_in.update(m.ipopt_zU_out)

    res = ipopt.solve(m, tee=False)
    print(p_value, pyo.value(m.x), pyo.value(m.y), pyo.value(m.obj))
```

**Agent rule:** warm-starting is most valuable in parametric sweeps, MPC/online optimization, continuation, decomposition subproblems, OBBT, and repeated NLPs where active constraints/bounds change slowly. Ipopt’s own warning is explicit: if active sets change between solves, warm starts may fail to reduce iterations and can even increase them. ([COIN-OR Documentation][1])

---

## 12.8 Primal warm start only versus full warm start

### Primal-only reuse

```python id="lbyzlk"
# Previous solution remains in Var.value.
model.p.set_value(new_value)

# Do not set warm_start_init_point.
results = ipopt.solve(model, tee=True)
```

### Full warm start

```python id="ks7xxe"
model.ipopt_zL_in.update(model.ipopt_zL_out)
model.ipopt_zU_in.update(model.ipopt_zU_out)

ipopt.options.update({
    "warm_start_init_point": "yes",
    "warm_start_bound_push": 1e-6,
    "warm_start_mult_bound_push": 1e-6,
    "mu_init": 1e-6,
})

results = ipopt.solve(model, tee=True)
```

Ipopt explains that using only primal values and active constraint multipliers misses bound multipliers `zL` and `zU`, which is why the `ipopt_zL_*` and `ipopt_zU_*` suffixes matter for effective warm starts. ([COIN-OR Documentation][1])

---

## 12.9 Suffix lifecycle management

### Clear stale bound multiplier inputs

```python id="d7pojq"
model.ipopt_zL_in.clearAllValues()
model.ipopt_zU_in.clearAllValues()
```

### Copy only valid output suffix entries

```python id="bq1ngq"
model.ipopt_zL_in.clearAllValues()
model.ipopt_zU_in.clearAllValues()

for var, val in model.ipopt_zL_out.items():
    if val is not None:
        model.ipopt_zL_in[var] = val

for var, val in model.ipopt_zU_out.items():
    if val is not None:
        model.ipopt_zU_in[var] = val
```

Pyomo suffix objects provide methods for clearing, setting, and updating suffix data, including `clearAllValues()`, `setValue(...)`, and `updateValues(...)`; suffix export/import behavior is determined by the suffix direction. ([Pyomo Documentation][2])

### Agent rule

```text id="fz8x5n"
If model structure changes:
  clear *_in suffixes
  do not blindly reuse bound multipliers from removed/deactivated variables
  solve cold or rebuild warm-start payload by component identity

If only mutable Params change:
  safe to reuse Var.value, dual, ipopt_zL_out, ipopt_zU_out after copy
```

---

## 12.10 Warm-start option profiles

### Conservative warm start

```python id="c0q26e"
IPOPT_WARM_CONSERVATIVE = {
    "warm_start_init_point": "yes",
    "warm_start_bound_push": 1e-4,
    "warm_start_mult_bound_push": 1e-4,
    "mu_init": 1e-4,
}
```

### Aggressive close-start profile

```python id="7m19gb"
IPOPT_WARM_AGGRESSIVE = {
    "warm_start_init_point": "yes",
    "warm_start_bound_push": 1e-6,
    "warm_start_mult_bound_push": 1e-6,
    "mu_init": 1e-6,
}
```

### Adaptive-barrier warm-start experiment

```python id="ey9z2r"
IPOPT_WARM_ADAPTIVE = {
    "warm_start_init_point": "yes",
    "warm_start_bound_push": 1e-6,
    "warm_start_mult_bound_push": 1e-6,
    "mu_strategy": "adaptive",
    "mu_oracle": "quality-function",
}
```

### Warm-start + strict output audit

```python id="b2elgt"
IPOPT_WARM_AUDIT = {
    "warm_start_init_point": "yes",
    "warm_start_bound_push": 1e-6,
    "warm_start_mult_bound_push": 1e-6,
    "mu_init": 1e-6,
    "print_user_options": "yes",
    "print_level": 5,
}
```

Ipopt recommends small `warm_start_bound_push`, `warm_start_mult_bound_push`, and `mu_init` values when the active set is preserved; it also notes that adaptive `mu_strategy` can be tried as an alternative. ([COIN-OR Documentation][1])

---

## 12.11 Warm-start helper functions

### Declare suffixes idempotently

```python id="tmhh3k"
import pyomo.environ as pyo


def attach_ipopt_warm_start_suffixes(model):
    if not hasattr(model, "dual"):
        model.dual = pyo.Suffix(direction=pyo.Suffix.IMPORT_EXPORT)
    else:
        model.dual.setDirection(pyo.Suffix.IMPORT_EXPORT)

    if not hasattr(model, "ipopt_zL_out"):
        model.ipopt_zL_out = pyo.Suffix(direction=pyo.Suffix.IMPORT)
    if not hasattr(model, "ipopt_zU_out"):
        model.ipopt_zU_out = pyo.Suffix(direction=pyo.Suffix.IMPORT)

    if not hasattr(model, "ipopt_zL_in"):
        model.ipopt_zL_in = pyo.Suffix(direction=pyo.Suffix.EXPORT)
    if not hasattr(model, "ipopt_zU_in"):
        model.ipopt_zU_in = pyo.Suffix(direction=pyo.Suffix.EXPORT)
```

### Prepare warm-start inputs

```python id="b5ewm7"
def prepare_ipopt_warm_start(model, *, skip_none=True):
    model.ipopt_zL_in.clearAllValues()
    model.ipopt_zU_in.clearAllValues()

    for var, val in model.ipopt_zL_out.items():
        if (val is not None) or not skip_none:
            model.ipopt_zL_in[var] = val

    for var, val in model.ipopt_zU_out.items():
        if (val is not None) or not skip_none:
            model.ipopt_zU_in[var] = val
```

### Configure solver

```python id="aflq80"
def configure_ipopt_warm_start(
    opt,
    *,
    push=1e-6,
    mult_push=1e-6,
    mu_init=1e-6,
    adaptive=False,
):
    opt.options["warm_start_init_point"] = "yes"
    opt.options["warm_start_bound_push"] = push
    opt.options["warm_start_mult_bound_push"] = mult_push

    if adaptive:
        opt.options["mu_strategy"] = "adaptive"
    else:
        opt.options["mu_init"] = mu_init
```

### Full workflow function

```python id="ql1qhr"
def warm_started_resolve(model, opt, *, tee=False):
    prepare_ipopt_warm_start(model)
    configure_ipopt_warm_start(opt)
    return opt.solve(model, tee=tee)
```

---

## 12.12 Warm-start suitability classifier

```python id="knrfwb"
def warm_start_is_structurally_safe(model_before_fingerprint, model_after_fingerprint):
    return model_before_fingerprint == model_after_fingerprint
```

Practical fingerprint:

```python id="zcq8lx"
def active_nlp_fingerprint(model):
    vars_ = tuple(v.name for v in model.component_data_objects(pyo.Var, active=True))
    cons_ = tuple(c.name for c in model.component_data_objects(pyo.Constraint, active=True))
    objs_ = tuple(o.name for o in model.component_data_objects(pyo.Objective, active=True))
    fixed = tuple((v.name, bool(v.fixed)) for v in model.component_data_objects(pyo.Var, active=True))
    return vars_, cons_, objs_, fixed
```

Policy:

```text id="2ldpqt"
same variables + same constraints + same fixed status + changed mutable Params:
  warm-start suffix reuse likely valid

added/removed variables:
  cold solve or rebuild suffix maps

activated/deactivated constraints:
  cold solve or carefully clear constraint/bound suffix inputs

changed bounds substantially:
  warm-start may help if active set similar; otherwise benchmark

changed fixed-variable treatment:
  cold solve recommended
```

---

## 12.13 Warm-start diagnostics

### Iteration-count comparison

```python id="l29iis"
def extract_ipopt_iteration_count(results):
    # Classic Pyomo Results often stores solver info, but exact fields vary by version/interface.
    # Prefer parsing solver log for robust iteration-count benchmarking.
    return None
```

### Log-level benchmark

```python id="jhg8cp"
cold = pyo.SolverFactory("ipopt")
cold.options.update({"print_level": 5})
cold.solve(model, tee=True, logfile="cold.log")

prepare_ipopt_warm_start(model)

warm = pyo.SolverFactory("ipopt")
warm.options.update({
    "warm_start_init_point": "yes",
    "warm_start_bound_push": 1e-6,
    "warm_start_mult_bound_push": 1e-6,
    "mu_init": 1e-6,
    "print_level": 5,
})
warm.solve(model, tee=True, logfile="warm.log")
```

Success signals:

```text id="7udfv7"
warm-start iteration 0:
  low inf_pr
  low inf_du
  lg(mu) near mu_init if monotone
  fewer total iterations than cold solve
  no immediate restoration
  objective near previous solution when data perturbation small
```

Pyomo’s documented warm-start example shows the cold solve requiring 8 iterations and the warm-started solve requiring 2 iterations, with the warm-started iteration 0 already near the previous optimum. ([Pyomo Documentation][2])

---

## 12.14 Bound multipliers and active-set sensitivity

```text id="9wmg7f"
zL:
  multiplier for lower variable bound x >= xL

zU:
  multiplier for upper variable bound x <= xU

large zL/zU:
  bound likely active or influential

near-zero zL/zU:
  bound likely inactive
```

Ipopt’s warm-start documentation says the feature is useful when subsequent problems preserve the same set of active inequalities and bounds, and it specifically recommends monitoring `zL` and `zU` for subsequent solutions. ([COIN-OR Documentation][1])

### Active-bound monitor

```python id="9994g4"
def bound_multiplier_report(model, tol=1e-7):
    rows = []
    for v in model.component_data_objects(pyo.Var, active=True):
        zL = model.ipopt_zL_out.get(v, None)
        zU = model.ipopt_zU_out.get(v, None)
        val = pyo.value(v, exception=False)
        lb = pyo.value(v.lb, exception=False) if v.lb is not None else None
        ub = pyo.value(v.ub, exception=False) if v.ub is not None else None

        active_lb = lb is not None and val is not None and abs(val - lb) <= tol
        active_ub = ub is not None and val is not None and abs(val - ub) <= tol

        rows.append({
            "var": v.name,
            "value": val,
            "lb": lb,
            "ub": ub,
            "active_lb": active_lb,
            "active_ub": active_ub,
            "zL": zL,
            "zU": zU,
        })
    return rows
```

---

## 12.15 Fixed variables and warm starts

```text id="h95jxz"
fixed variables can produce ambiguous/solver-dependent bound multiplier patterns
because lower and upper bounds coincide or fixed variables may be transformed
according to fixed_variable_treatment.
```

Recommended policy:

```python id="rxye7z"
opt.options.update({
    "fixed_variable_treatment": "make_parameter",
})
```

When fixed-variable multiplier interpretation matters:

```python id="gk32zf"
opt.options.update({
    "fixed_variable_treatment": "make_constraint",
})
```

Agent rule:

```text id="1mqay9"
If fixed status changes between solves:
  clear ipopt_zL_in / ipopt_zU_in
  cold solve or reinitialize multipliers conservatively
```

---

## 12.16 Warm start versus APPSI repeated solves

```text id="ez1e0e"
Classic Ipopt warm start:
  use Var.value + Suffix objects + Ipopt warm-start options

APPSI repeated solve:
  solver interface can update same model instance efficiently
  still requires warm-start semantics/options when interior-point dual/bound multiplier reuse is desired
```

APPSI is designed for efficient repeated solves of the same Pyomo model with small updates, while classic Ipopt warm-start suffixes specifically provide primal/dual/bound multiplier initialization to Ipopt. Use them as complementary concepts, not synonyms. Pyomo’s APPSI docs describe efficient repeated solves with small model changes, while Pyomo’s suffix docs describe Ipopt warm-start suffixes. ([Pyomo Documentation][2])

---

## 12.17 Warm start and `load_solutions=False`

### Safe termination gate

```python id="oofseq"
from pyomo.opt import SolverStatus, TerminationCondition

res = ipopt.solve(model, tee=True, load_solutions=False)

if res.solver.status == SolverStatus.ok and res.solver.termination_condition == TerminationCondition.optimal:
    model.solutions.load_from(res)
else:
    raise RuntimeError(f"Solve failed: {res.solver.status}, {res.solver.termination_condition}")
```

### Warm-start consequence

```text id="lzltfy"
If load_solutions=False and solution is not loaded:
  Var.value does not become new primal warm-start point
  imported suffixes may not update in model as expected
  next warm start can reuse stale values
```

Agent rule:

```text id="xk0k14"
For warm-start loops:
  only prepare next warm start after successful solve and successful solution/suffix loading.
```

---

## 12.18 Cold-start fallback logic

```python id="3yb91o"
def solve_with_warm_start_fallback(model, opt, *, tee=False):
    prepare_ipopt_warm_start(model)
    configure_ipopt_warm_start(opt)

    res = opt.solve(model, tee=tee)

    term = str(res.solver.termination_condition).lower()
    status = str(res.solver.status).lower()

    if "optimal" in term and "ok" in status:
        return res, "warm"

    # Fallback: clear warm-start inputs and solve cold.
    model.ipopt_zL_in.clearAllValues()
    model.ipopt_zU_in.clearAllValues()

    for key in [
        "warm_start_init_point",
        "warm_start_bound_push",
        "warm_start_mult_bound_push",
        "mu_init",
    ]:
        opt.options.pop(key, None)

    res = opt.solve(model, tee=tee)
    return res, "cold_fallback"
```

Use when:

```text id="h5xtsn"
active set may change
warm-start occasionally triggers restoration/failure
online workflow must recover robustly
```

---

## 12.19 Warm-start benchmark policy

```text id="3yaplg"
Benchmark:
  cold solve for each scenario
  primal-only solve for each scenario
  full warm-start solve for each scenario

Record:
  iteration count
  wall time
  objective
  max constraint violation
  termination condition
  restoration entries
  active-bound pattern
  zL/zU pattern drift
```

Expected outcomes:

```text id="837zfx"
full warm start wins:
  small data perturbation
  same active bounds/constraints
  previous solution near new KKT point

primal-only enough:
  active multipliers change but primal solution close

cold solve wins:
  active set changes
  strong nonconvex basin shift
  old multipliers mislead barrier path
```

Ipopt explicitly states that warm starts can significantly reduce iterations when active inequalities and bounds are preserved, and may not decrease iterations when active sets change. ([COIN-OR Documentation][1])

---

## 12.20 `ipopt.opt` warm-start syntax

```text id="884fwv"
# ipopt.opt

warm_start_init_point yes
warm_start_bound_push 1e-6
warm_start_mult_bound_push 1e-6
mu_init 1e-6
```

Ipopt option files use line-by-line `option_name value` syntax with `#` comments; `yes` / `no` toggles are string option values. ([COIN-OR Documentation][3])

---

## 12.21 Direct AMPL-style conceptual mapping

```text id="c267sz"
AMPL:
  x[i].ipopt_zL_out -> x[i].ipopt_zL_in
  x[i].ipopt_zU_out -> x[i].ipopt_zU_in

Pyomo:
  model.ipopt_zL_in.update(model.ipopt_zL_out)
  model.ipopt_zU_in.update(model.ipopt_zU_out)
```

Ipopt’s warm-start docs show the AMPL-side assignment pattern `ipopt_zL_in := ipopt_zL_out` and `ipopt_zU_in := ipopt_zU_out`; Pyomo’s suffix example implements the same transfer with suffix `.update(...)`. ([COIN-OR Documentation][1])

---

## 12.22 Anti-pattern catalog

```text id="4xt8zn"
BAD:
  set warm_start_init_point=yes without dual / zL / zU suffixes.

GOOD:
  declare dual IMPORT_EXPORT and ipopt_z*_out/import + ipopt_z*_in/export suffixes.

BAD:
  copy ipopt_zL_out to ipopt_zU_in or vice versa.

GOOD:
  ipopt_zL_in.update(ipopt_zL_out)
  ipopt_zU_in.update(ipopt_zU_out)

BAD:
  assume warm start always reduces iterations.

GOOD:
  benchmark; active-set changes can make warm starts worse.

BAD:
  use warm-start multipliers after adding/removing variables or constraints.

GOOD:
  clear suffixes and cold solve after structural changes.

BAD:
  use Python booleans for Ipopt string options.

GOOD:
  opt.options["warm_start_init_point"] = "yes"

BAD:
  enable least_square_init_primal=yes in the same profile and expect primal warm start to be preserved.

GOOD:
  leave least_square_init_primal=no for warm-start profiles.

BAD:
  ignore failed warm-start termination and keep reusing stale suffixes.

GOOD:
  load only successful solutions and refresh suffixes after successful solves.
```

---

## 12.23 Agent-ready final checklist

```text id="q7l3f0"
[ ] Declare model.dual = Suffix(IMPORT_EXPORT).
[ ] Declare model.ipopt_zL_out = Suffix(IMPORT).
[ ] Declare model.ipopt_zU_out = Suffix(IMPORT).
[ ] Declare model.ipopt_zL_in = Suffix(EXPORT).
[ ] Declare model.ipopt_zU_in = Suffix(EXPORT).
[ ] Run initial cold solve successfully.
[ ] Ensure primal Var.value values are loaded.
[ ] Ensure dual and bound multiplier suffixes are populated.
[ ] Copy zL_out → zL_in and zU_out → zU_in before warm solve.
[ ] Set warm_start_init_point = "yes".
[ ] Set warm_start_bound_push and warm_start_mult_bound_push small.
[ ] Set mu_init small for monotone warm-start profile.
[ ] Consider mu_strategy=adaptive only as benchmark variant.
[ ] Use warm starts mainly for related problems with stable active sets.
[ ] Clear warm-start suffixes after structural changes.
[ ] Do not claim warm-start benefit without iteration/time benchmark.
[ ] Use cold-start fallback in robust production loops.
```

[1]: https://coin-or.github.io/Ipopt/SPECIALS.html "Ipopt: Special Features"
[2]: https://pyomo.readthedocs.io/en/6.8.0/pyomo_modeling_components/Suffixes.html "Suffixes — Pyomo 6.8.0 documentation"
[3]: https://coin-or.github.io/Ipopt/OPTIONS.html "Ipopt: Ipopt Options"

# Ipopt Advanced — Section 13: solver output, logs, and termination interpretation

Style target: dense advanced technical catalog / agent-ready reference. 

## 13.0 Output-interpretation invariant

```text id="7j2lnt"
Ipopt log interpretation =
  problem statistics
  + iteration table
  + step-acceptance tags
  + restoration markers
  + exit status
  + Pyomo result status/termination_condition
  + optional manual solution-loading policy
```

Ipopt’s standard console output begins with problem statistics, then prints an iteration table with columns such as `iter`, `objective`, `inf_pr`, `inf_du`, `lg(mu)`, `||d||`, `lg(rg)`, `alpha_du`, `alpha_pr`, and `ls`; fixed variables may be removed internally and therefore not appear in reported problem statistics. ([COIN-OR Documentation][1])

---

## 13.1 Pyomo logging front door

### Stream solver output

```python id="ykwcra"
import pyomo.environ as pyo

opt = pyo.SolverFactory("ipopt")
results = opt.solve(model, tee=True)
```

Pyomo documents `tee=True` as the solver-independent option for streaming solver output; this is useful for troubleshooting solver difficulties. ([Pyomo Documentation][2])

### Capture log to file

```python id="ssdf8b"
results = opt.solve(
    model,
    tee=True,
    logfile="ipopt.solve.log",
)
```

### Ipopt output verbosity

```python id="qhhlc1"
opt.options.update({
    "print_level": 5,
    "print_user_options": "yes",
})
```

### Diagnostic tags at end of iteration lines

```python id="2fqdzv"
opt.options["print_info_string"] = "yes"
```

Ipopt supports extra per-iteration diagnostic tags with `print_info_string=yes`; the output docs list tags for degeneracy, restoration, watchdog behavior, singular systems, limited-memory updates, warm-start initialization failure, and other low-level diagnostic events. ([COIN-OR Documentation][1])

---

## 13.2 Iteration table: canonical shape

```text id="wgtmrm"
iter    objective    inf_pr   inf_du lg(mu)  ||d||  lg(rg) alpha_du alpha_pr  ls
   0  1.6109693e+01 1.12e+01 5.28e-01   0.0 0.00e+00    -  0.00e+00 0.00e+00   0
   1  1.8029749e+01 9.90e-01 6.62e+01   0.1 2.05e+00    -  2.14e-01 1.00e+00f  1
   2  1.8719906e+01 1.25e-02 9.04e+00  -2.2 5.94e-02   2.0 8.04e-01 1.00e+00h  1
```

Ipopt explicitly warns that accepted iterates can have worse printed objective and printed constraint violation because step acceptance uses the barrier objective and internal scaled/slack reformulation, not exactly the values printed in the `objective` and `inf_pr` columns. ([COIN-OR Documentation][1])

---

## 13.3 Iteration table columns

| Column      | Meaning                                                                                 | Agent interpretation                               |   |   |                                                                                |                             |
| ----------- | --------------------------------------------------------------------------------------- | -------------------------------------------------- | - | - | ------------------------------------------------------------------------------ | --------------------------- |
| `iter`      | iteration count, including restoration iterations; `r` suffix means restoration phase   | `12r` = restoration-phase iteration                |   |   |                                                                                |                             |
| `objective` | unscaled objective value at current point; during restoration, still original objective | not necessarily monotone                           |   |   |                                                                                |                             |
| `inf_pr`    | unscaled original constraint violation by default, infinity norm                        | primary feasibility signal for original model      |   |   |                                                                                |                             |
| `inf_du`    | scaled internal dual infeasibility                                                      | stationarity / multiplier consistency signal       |   |   |                                                                                |                             |
| `lg(mu)`    | `log10(mu)`, where `mu` is barrier parameter                                            | barrier progress / complementarity pressure        |   |   |                                                                                |                             |
| `           |                                                                                         | d                                                  |   | ` | infinity norm of primal step, including original variables and internal slacks | step-size / progress signal |
| `lg(rg)`    | `log10` Hessian regularization term; `-` means no regularization                        | frequent/large values imply KKT/Hessian difficulty |   |   |                                                                                |                             |
| `alpha_du`  | dual-variable step size                                                                 | multiplier-step acceptance                         |   |   |                                                                                |                             |
| `alpha_pr`  | primal-variable step size plus diagnostic tag                                           | line-search/filter/restoration/tiny-step signal    |   |   |                                                                                |                             |
| `ls`        | number of backtracking line-search steps, excluding second-order correction steps       | high values imply globalization trouble            |   |   |                                                                                |                             |

The output docs define each column; `inf_pr` is the infinity norm of original unscaled constraint violation by default, `inf_du` is scaled internal dual infeasibility, `lg(mu)` is log-base-10 barrier parameter, and `lg(rg)` is the log regularization term for the Hessian of the Lagrangian in the augmented system. ([COIN-OR Documentation][1])

---

## 13.4 `inf_pr` control: original versus internal violation

```python id="59rfv3"
opt.options["inf_pr_output"] = "original"
```

```python id="ts67sw"
opt.options["inf_pr_output"] = "internal"
```

`inf_pr` defaults to original unscaled NLP constraint violation, but the `inf_pr_output` option can switch what is printed; this matters because Ipopt’s internal step acceptance uses an internal formulation with slacks and scaling that can differ from printed original constraint violation. ([COIN-OR Documentation][1])

**Agent policy**

```text id="o79788"
debugging model feasibility:
  inf_pr_output=original

debugging Ipopt internal globalization behavior:
  compare original output to internal output in separate runs
```

---

## 13.5 Step acceptance letters in `alpha_pr`

| Tag | Meaning                                                                               |
| --- | ------------------------------------------------------------------------------------- |
| `f` | f-type filter iteration, no second-order correction                                   |
| `F` | f-type filter iteration, with second-order correction                                 |
| `h` | h-type filter iteration, no second-order correction                                   |
| `H` | h-type filter iteration, with second-order correction                                 |
| `k` | penalty value unchanged in merit-function method, no second-order correction          |
| `K` | penalty value unchanged in merit-function method, with second-order correction        |
| `n` | penalty value updated in merit-function method, no second-order correction            |
| `N` | penalty value updated in merit-function method, with second-order correction          |
| `R` | restoration phase just started                                                        |
| `w` | watchdog procedure                                                                    |
| `s` | step accepted in soft restoration phase                                               |
| `S` | soft restoration step accepted and original backtracking globalization also satisfied |
| `t` | tiny step accepted without line search                                                |
| `T` | two consecutive tiny steps accepted                                                   |
| `r` | previous iterate restored                                                             |

Ipopt’s output docs define these `alpha_pr` suffix characters and explain that they encode step-acceptance diagnostics, including filter iterations, penalty-merit iterations, restoration, watchdog, soft restoration, and tiny-step cases. ([COIN-OR Documentation][1])

---

## 13.6 Restoration phase interpretation

### Log markers

```text id="1xrkev"
iter suffix:
  15r     -> iteration 15 in restoration phase

alpha_pr tag:
  R       -> restoration phase just started
  s / S   -> soft restoration accepted
```

### Meaning

```text id="npxgiv"
restoration phase =
  Ipopt feasibility-recovery mode
  entered when ordinary filter/line-search progress fails
  solves restoration problem targeting constraint violation reduction
  can return locally infeasible point
```

Ipopt marks restoration-phase iterations with an `r` appended to the iteration number; `R` in `alpha_pr` marks restoration start. If restoration converges to a minimizer of constraint violation that is not feasible for the original problem, Ipopt reports local infeasibility and says the returned point may help identify the problematic constraint. ([COIN-OR Documentation][1])

### Agent interpretation table

| Pattern                       | Meaning                                           | First response                                     |
| ----------------------------- | ------------------------------------------------- | -------------------------------------------------- |
| occasional `R`, then recovery | hard globalization step                           | inspect but not failure                            |
| many `r` iterations           | feasibility recovery dominating                   | check infeasibility, scaling, bad starts           |
| `s` / `S` repeatedly          | soft restoration accepted                         | inspect infeasibility and line-search difficulty   |
| `Restoration_Failed`          | restoration cannot find acceptable feasible point | derivative check, feasibility audit, scaling audit |
| `Infeasible_Problem_Detected` | local infeasibility point found                   | constraint residual report, alternate starts       |

---

## 13.7 Additional diagnostic tags: `print_info_string=yes`

```python id="yd9ww4"
opt.options["print_info_string"] = "yes"
```

High-value tags:

| Tag               | Meaning                                                   |
| ----------------- | --------------------------------------------------------- |
| `A`               | current iteration is acceptable                           |
| `C`               | second-order correction taken                             |
| `Dh`, `Dj`, `Dhj` | Hessian/Jacobian degeneracy signals                       |
| `e`               | step cut back because of evaluation error in backtracking |
| `F+`, `F-`        | filter reset or reset failure                             |
| `L`, `l`          | degenerate Jacobian perturbation                          |
| `R`               | solution of restoration phase                             |
| `s`, `S`          | primal-dual system singular / accepted current solution   |
| `Tmax`            | trial constraint violation larger than filter maximum     |
| `W`, `w`          | watchdog success/failure                                  |
| `NW`              | warm-start initialization failed                          |
| `y`               | least-square multiplier update due to dual infeasibility  |
| `z`               | bound-multiplier correction                               |

Ipopt’s output docs list these optional diagnostic tags under `print_info_string=yes`; they are useful for flagging degeneracy, singular systems, evaluation failures, watchdog behavior, restoration, and warm-start issues. ([COIN-OR Documentation][1])

---

## 13.8 Exit statuses: successful and degraded-success cases

| Ipopt return code            | Console message                                  | Meaning                                                                          | Agent policy                                      |
| ---------------------------- | ------------------------------------------------ | -------------------------------------------------------------------------------- | ------------------------------------------------- |
| `Solve_Succeeded`            | `EXIT: Optimal Solution Found.`                  | locally optimal point within desired tolerances                                  | load solution if Pyomo status ok                  |
| `Solved_To_Acceptable_Level` | `EXIT: Solved To Acceptable Level.`              | did not meet desired tolerances, but met acceptable tolerances                   | load only if application permits degraded solve   |
| `Feasible_Point_Found`       | `EXIT: Feasible point for square problem found.` | square problem feasible with respect to `constr_viol_tol`, not necessarily `tol` | treat as feasible diagnostic, not full optimality |

Ipopt says `Solve_Succeeded` indicates a locally optimal point within desired tolerances; `Solved_To_Acceptable_Level` means desired tolerances were not met but acceptable tolerance criteria were satisfied; `Feasible_Point_Found` applies to square problems where a point feasible with respect to `constr_viol_tol` is found. ([COIN-OR Documentation][1])

---

## 13.9 Exit statuses: infeasibility, limits, numerical failure

| Ipopt return code                    | Console message                                                                 | Meaning                                                                                     | Agent response                                           |
| ------------------------------------ | ------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- | -------------------------------------------------------- |
| `Infeasible_Problem_Detected`        | `EXIT: Converged to a point of local infeasibility. Problem may be infeasible.` | restoration minimized constraint violation locally but did not find feasible original point | inspect constraint residuals, try alternate starts       |
| `Search_Direction_Becomes_Too_Small` | `EXIT: Search Direction is becoming Too Small.`                                 | very small steps; little progress; may be best numerical accuracy under current scaling     | check residuals, scaling, degeneracy                     |
| `Diverging_Iterates`                 | `EXIT: Iterates diverging; problem might be unbounded.`                         | iterate norm exceeded `diverging_iterates_tol`                                              | check bounds/unboundedness/scaling                       |
| `Maximum_Iterations_Exceeded`        | `EXIT: Maximum Number of Iterations Exceeded.`                                  | exceeded `max_iter`                                                                         | inspect convergence trend; raise limit only if improving |
| `Maximum_WallTime_Exceeded`          | `EXIT: Maximum wallclock time exceeded.`                                        | exceeded `max_wall_time`                                                                    | operational timeout                                      |
| `Maximum_CpuTime_Exceeded`           | `EXIT: Maximum CPU time exceeded.`                                              | exceeded `max_cpu_time`                                                                     | operational CPU budget                                   |
| `Restoration_Failed`                 | `EXIT: Restoration Failed!`                                                     | restoration failed to find filter-acceptable feasible point                                 | check degeneracy, CQ, derivatives                        |
| `Error_In_Step_Computation`          | `EXIT: Error in step computation!`                                              | unable to compute acceptable step; invalid Hessian values or severe degeneracy possible     | enable derivative NaN/Inf checks, derivative checker     |
| `Invalid_Option`                     | option-specific error text                                                      | invalid option or unavailable linear solver/load failure                                    | inspect option spelling/build                            |
| `Not_Enough_Degrees_Of_Freedom`      | `EXIT: Problem has too few degrees of freedom.`                                 | too many equalities/fixed vars after internal removal                                       | inspect fixed variables/equality count                   |
| `Invalid_Problem_Definition`         | inconsistent bounds/sides                                                       | lower bound exceeds upper bound or invalid model definition                                 | model construction bug                                   |
| `Insufficient_Memory`                | `EXIT: Not enough memory.` or integer type too small                            | allocation failure or linear solver memory issue                                            | reduce model/fill-in or change linear solver/build       |
| `Internal_Error`                     | internal error message                                                          | unexpected Ipopt internal return code                                                       | preserve repro artifacts                                 |

Ipopt’s output docs define these return codes, messages, and descriptions. Notably, local infeasibility is not a formal global infeasibility proof; `Error_In_Step_Computation` can be caused by invalid Hessian entries such as NaN/Inf; and invalid options can include selecting a linear solver that is not linked and cannot be loaded. ([COIN-OR Documentation][1])

---

## 13.10 Desired versus acceptable convergence

```python id="y0o2m8"
opt.options.update({
    "tol": 1e-8,
    "acceptable_tol": 1e-6,
    "acceptable_iter": 15,
})
```

`tol` is the desired convergence tolerance: Ipopt succeeds only if the scaled NLP error is below `tol` and the absolute criteria `dual_inf_tol`, `constr_viol_tol`, and `compl_inf_tol` are satisfied. `acceptable_tol` is a secondary termination criterion used when desired tolerances are too strict or impractical for the current problem. ([COIN-OR Documentation][3])

**Agent policy**

```text id="rpr2gh"
Solve_Succeeded:
  full success under desired tolerance policy

Solved_To_Acceptable_Level:
  degraded success
  require explicit application-level acceptance
  record as acceptable, not optimal-desired

Maximum_Iterations_Exceeded with low residuals:
  maybe useful incumbent
  do not mark as optimal automatically
```

---

## 13.11 Pyomo status handling

### Basic status gate

```python id="akxyms"
from pyomo.opt import SolverStatus, TerminationCondition

results = opt.solve(model, tee=True)

if (
    results.solver.status == SolverStatus.ok
    and results.solver.termination_condition == TerminationCondition.optimal
):
    print("feasible and optimal")
elif results.solver.termination_condition == TerminationCondition.infeasible:
    print("infeasible or locally infeasible")
else:
    print(str(results.solver))
```

Pyomo’s solver recipes show accessing `results.solver.status` and `results.solver.termination_condition`, comparing them to `SolverStatus.ok` and `TerminationCondition.optimal`, and handling infeasible or other termination cases separately. ([Pyomo Documentation][2])

### Manual loading gate with `load_solutions=False`

```python id="sb1f5h"
from pyomo.opt import TerminationCondition

results = opt.solve(model, tee=True, load_solutions=False)

if results.solver.termination_condition == TerminationCondition.optimal:
    model.solutions.load_from(results)
else:
    raise RuntimeError(f"Solution not loaded: {results.solver.termination_condition}")
```

Pyomo documents the `load_solutions=False` pattern for inspecting termination before mutating the model with solver-returned values; if the termination condition is optimal, the solution can be manually loaded with `model.solutions.load_from(results)`. ([Pyomo Documentation][2])

---

## 13.12 Pyomo enum surface relevant to Ipopt

Useful `TerminationCondition` members for Ipopt mapping:

```text id="b6384d"
optimal
locallyOptimal
feasible
infeasible
maxIterations
maxTimeLimit
minStepLength
unbounded
invalidProblem
solverFailure
internalSolverError
error
resourceInterrupt
unknown
other
```

Pyomo’s `TerminationCondition` enum includes members such as `maxTimeLimit`, `maxIterations`, `minStepLength`, `locallyOptimal`, `feasible`, `optimal`, `unbounded`, `infeasible`, `invalidProblem`, `solverFailure`, `internalSolverError`, `error`, and `resourceInterrupt`. Its `SolverStatus` enum includes `ok`, `warning`, `error`, `aborted`, and `unknown`. ([Pyomo Documentation][4])

**Agent rule**

```text id="awdzpx"
Do not rely only on string search.
Prefer:
  results.solver.status == SolverStatus.ok
  results.solver.termination_condition in allowed_conditions
```

---

## 13.13 Strict load policy

```python id="e3psp0"
from pyomo.opt import SolverStatus, TerminationCondition

def solve_ipopt_strict(model, opt=None, *, tee=True):
    opt = opt or pyo.SolverFactory("ipopt")
    results = opt.solve(model, tee=tee, load_solutions=False)

    status = results.solver.status
    tc = results.solver.termination_condition

    if status == SolverStatus.ok and tc == TerminationCondition.optimal:
        model.solutions.load_from(results)
        return results

    raise RuntimeError(
        f"Ipopt did not satisfy strict policy: status={status}, termination={tc}"
    )
```

Use for:

```text id="diw61l"
production dispatch
regulatory constraints
benchmark final solve
post-optimality sensitivity
automated pipelines where degraded solve is unacceptable
```

---

## 13.14 Acceptable-load policy

```python id="uyfhyx"
from pyomo.opt import SolverStatus, TerminationCondition

ACCEPTABLE_TERMINATIONS = {
    TerminationCondition.optimal,
    TerminationCondition.locallyOptimal,
    # Include feasible only if application accepts feasibility without optimality.
    # TerminationCondition.feasible,
}

def solve_ipopt_with_policy(model, opt=None, *, tee=True, allow_acceptable_text=True):
    opt = opt or pyo.SolverFactory("ipopt")
    results = opt.solve(model, tee=tee, load_solutions=False)

    status = results.solver.status
    tc = results.solver.termination_condition
    solver_text = str(results.solver).lower()

    allowed = status == SolverStatus.ok and tc in ACCEPTABLE_TERMINATIONS

    # Some interfaces may map Ipopt acceptable-level termination differently.
    acceptable_level = allow_acceptable_text and "acceptable" in solver_text

    if allowed or acceptable_level:
        model.solutions.load_from(results)
        return results

    raise RuntimeError(
        f"Ipopt result rejected: status={status}, termination={tc}, solver={results.solver}"
    )
```

**Agent caution**

```text id="usl0l4"
Solved_To_Acceptable_Level:
  can be useful
  is not desired-tolerance success
  should be tagged degraded
  should trigger residual audit before downstream use
```

---

## 13.15 Residual audit after solver success/degraded success

```python id="71qqkp"
import pyomo.environ as pyo

def max_constraint_violation(model):
    worst = (None, 0.0, None, None, None)

    for c in model.component_data_objects(pyo.Constraint, active=True):
        body = pyo.value(c.body, exception=False)
        if body is None:
            continue

        lb = pyo.value(c.lower, exception=False) if c.lower is not None else None
        ub = pyo.value(c.upper, exception=False) if c.upper is not None else None

        lower_v = 0.0 if lb is None else max(0.0, lb - body)
        upper_v = 0.0 if ub is None else max(0.0, body - ub)
        viol = max(lower_v, upper_v)

        if viol > worst[1]:
            worst = (c.name, viol, body, lb, ub)

    return worst


def max_bound_violation(model):
    worst = (None, 0.0, None, None, None)

    for v in model.component_data_objects(pyo.Var, active=True):
        val = pyo.value(v, exception=False)
        if val is None:
            continue

        lb = pyo.value(v.lb, exception=False) if v.lb is not None else None
        ub = pyo.value(v.ub, exception=False) if v.ub is not None else None

        lower_v = 0.0 if lb is None else max(0.0, lb - val)
        upper_v = 0.0 if ub is None else max(0.0, val - ub)
        viol = max(lower_v, upper_v)

        if viol > worst[1]:
            worst = (v.name, viol, val, lb, ub)

    return worst
```

Use after:

```text id="s6hcf1"
Solved_To_Acceptable_Level
Feasible_Point_Found
Infeasible_Problem_Detected
Maximum_Iterations_Exceeded with candidate values
any non-strict solve policy
```

---

## 13.16 Log-pattern triage matrix

| Log pattern                | Likely issue                                                  | First action                                    |   |                             |                        |                                                       |
| -------------------------- | ------------------------------------------------------------- | ----------------------------------------------- | - | --------------------------- | ---------------------- | ----------------------------------------------------- |
| `inf_pr` stays large       | infeasibility, bad starts, wrong constraints                  | constraint residual report                      |   |                             |                        |                                                       |
| `inf_du` stays large       | stationarity/dual difficulty, scaling, Hessian/Jacobian issue | derivative check, scaling audit                 |   |                             |                        |                                                       |
| `lg(mu)` not decreasing    | barrier progress stalled                                      | scaling, line search, active-set difficulty     |   |                             |                        |                                                       |
| `                          |                                                               | d                                               |   | ` tiny, residuals not small | tiny-step / degeneracy | inspect `Search_Direction_Becomes_Too_Small`, scaling |
| frequent positive `lg(rg)` | Hessian/KKT regularization                                    | check Hessian, degeneracy, linear solver        |   |                             |                        |                                                       |
| large `ls` repeatedly      | line search struggling                                        | nonsmoothness, bad derivatives, poor scaling    |   |                             |                        |                                                       |
| many `r` iterations        | restoration active                                            | feasibility diagnostic                          |   |                             |                        |                                                       |
| `R` then failure           | restoration failed                                            | derivative checker + infeasibility audit        |   |                             |                        |                                                       |
| `e` diagnostic tag         | evaluation error during backtracking                          | protect log/sqrt/division domains               |   |                             |                        |                                                       |
| `NW` diagnostic tag        | warm-start initialization failed                              | clear/rebuild suffixes, relax warm-start pushes |   |                             |                        |                                                       |
| `Tmax`                     | trial infeasibility too high for filter                       | scaling/feasibility issue                       |   |                             |                        |                                                       |

---

## 13.17 Minimal log parser for iteration lines

```python id="kqv7sp"
from __future__ import annotations

import re
from dataclasses import dataclass


ITER_RE = re.compile(
    r"^\s*(?P<iter>\d+r?)\s+"
    r"(?P<objective>[-+0-9.eE]+)\s+"
    r"(?P<inf_pr>[-+0-9.eE]+)\s+"
    r"(?P<inf_du>[-+0-9.eE]+)\s+"
    r"(?P<lg_mu>[-+0-9.eE]+)\s+"
    r"(?P<d_norm>[-+0-9.eE]+)\s+"
    r"(?P<lg_rg>[-+0-9.eE]+|-)\s+"
    r"(?P<alpha_du>[-+0-9.eE]+)\s+"
    r"(?P<alpha_pr>[-+0-9.eE]+)(?P<tag>[A-Za-z]?)\s+"
    r"(?P<ls>\d+)"
)


@dataclass(frozen=True)
class IpoptIteration:
    iter_raw: str
    iter_num: int
    restoration: bool
    objective: float
    inf_pr: float
    inf_du: float
    lg_mu: float
    d_norm: float
    lg_rg: float | None
    alpha_du: float
    alpha_pr: float
    tag: str
    line_search_steps: int


def parse_ipopt_iterations(log_text: str) -> list[IpoptIteration]:
    rows = []

    for line in log_text.splitlines():
        m = ITER_RE.match(line)
        if not m:
            continue

        iter_raw = m.group("iter")
        rows.append(
            IpoptIteration(
                iter_raw=iter_raw,
                iter_num=int(iter_raw.rstrip("r")),
                restoration=iter_raw.endswith("r"),
                objective=float(m.group("objective")),
                inf_pr=float(m.group("inf_pr")),
                inf_du=float(m.group("inf_du")),
                lg_mu=float(m.group("lg_mu")),
                d_norm=float(m.group("d_norm")),
                lg_rg=None if m.group("lg_rg") == "-" else float(m.group("lg_rg")),
                alpha_du=float(m.group("alpha_du")),
                alpha_pr=float(m.group("alpha_pr")),
                tag=m.group("tag"),
                line_search_steps=int(m.group("ls")),
            )
        )

    return rows
```

---

## 13.18 Exit-message parser

```python id="upp8k6"
import re

EXIT_RE = re.compile(r"EXIT:\s*(?P<message>.+)$", re.MULTILINE)

def parse_ipopt_exit_message(log_text: str) -> str | None:
    m = EXIT_RE.search(log_text)
    return m.group("message").strip() if m else None
```

Example classification:

```python id="5gm1t9"
def classify_ipopt_exit(message: str | None) -> str:
    if message is None:
        return "unknown"

    msg = message.lower()

    if "optimal solution found" in msg:
        return "desired_success"
    if "acceptable level" in msg:
        return "acceptable_success"
    if "local infeasibility" in msg:
        return "local_infeasibility"
    if "maximum number of iterations" in msg:
        return "iteration_limit"
    if "wallclock time" in msg or "cpu time" in msg:
        return "time_limit"
    if "restoration failed" in msg:
        return "restoration_failed"
    if "error in step computation" in msg:
        return "step_computation_error"
    if "not enough memory" in msg:
        return "memory_failure"

    return "other"
```

---

## 13.19 Production solve wrapper with log artifacts

```python id="w0p0ga"
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pyomo.environ as pyo
from pyomo.opt import SolverStatus, TerminationCondition


@dataclass(frozen=True)
class IpoptSolveAudit:
    status: str
    termination_condition: str
    exit_message: str | None
    exit_class: str
    max_constraint_violation: tuple
    max_bound_violation: tuple
    log_path: str


def solve_ipopt_audited(
    model,
    *,
    log_path: str = "ipopt.solve.log",
    strict: bool = True,
    options: dict[str, object] | None = None,
):
    opt = pyo.SolverFactory("ipopt")
    if not opt.available(exception_flag=False):
        raise RuntimeError("Ipopt unavailable.")

    opt.options.update({
        "print_level": 5,
        "print_user_options": "yes",
        "inf_pr_output": "original",
    })
    if options:
        opt.options.update(options)

    results = opt.solve(
        model,
        tee=True,
        logfile=log_path,
        load_solutions=False,
    )

    log_text = Path(log_path).read_text() if Path(log_path).exists() else ""
    exit_message = parse_ipopt_exit_message(log_text)
    exit_class = classify_ipopt_exit(exit_message)

    status = results.solver.status
    tc = results.solver.termination_condition

    should_load = (
        status == SolverStatus.ok
        and tc == TerminationCondition.optimal
    )

    if should_load:
        model.solutions.load_from(results)

    audit = IpoptSolveAudit(
        status=str(status),
        termination_condition=str(tc),
        exit_message=exit_message,
        exit_class=exit_class,
        max_constraint_violation=max_constraint_violation(model) if should_load else (None, None, None, None, None),
        max_bound_violation=max_bound_violation(model) if should_load else (None, None, None, None, None),
        log_path=log_path,
    )

    if strict and not should_load:
        raise RuntimeError(f"Ipopt solve rejected: {audit}")

    return results, audit
```

---

## 13.20 Agent decision table: load or reject

| Ipopt/Pyomo outcome                                      |             Load solution? | Label                        |
| -------------------------------------------------------- | -------------------------: | ---------------------------- |
| `SolverStatus.ok` + `TerminationCondition.optimal`       |                        yes | desired success              |
| `Solved_To_Acceptable_Level` text / acceptable mapping   |                      maybe | degraded success             |
| `Feasible_Point_Found`                                   |    maybe, feasibility-only | square-feasible              |
| `Infeasible_Problem_Detected`                            | maybe for diagnostics only | local infeasibility          |
| `Maximum_Iterations_Exceeded`                            |                normally no | iteration-limited candidate  |
| `Maximum_WallTime_Exceeded` / `Maximum_CpuTime_Exceeded` |                normally no | time-limited candidate       |
| `Restoration_Failed`                                     |      no except diagnostics | restoration failure          |
| `Error_In_Step_Computation`                              |                         no | numerical/derivative failure |
| `Invalid_Problem_Definition`                             |                         no | model bug                    |
| `Invalid_Option`                                         |                         no | deployment/options bug       |
| `Insufficient_Memory`                                    |                         no | resource/model-size failure  |

---

## 13.21 Anti-pattern catalog

```text id="q9bwvo"
BAD:
  results = opt.solve(model)
  use model values without checking termination

GOOD:
  solve(..., load_solutions=False)
  check status + termination_condition
  manually load on accepted outcomes

BAD:
  treat Solved_To_Acceptable_Level as identical to Optimal Solution Found

GOOD:
  tag acceptable-level result as degraded success

BAD:
  declare infeasible after one Infeasible_Problem_Detected from one start

GOOD:
  inspect residuals and try alternate starts if feasibility is expected

BAD:
  interpret objective increase in one iteration as solver failure

GOOD:
  remember filter/barrier acceptance may accept worse printed objective/inf_pr

BAD:
  ignore `r` restoration markers

GOOD:
  treat repeated restoration as feasibility/model/derivative/scaling diagnostic

BAD:
  fix `Error_In_Step_Computation` by only increasing max_iter

GOOD:
  check NaN/Inf derivatives, Hessian validity, degeneracy, scaling, linear solver

BAD:
  parse logs only and ignore Pyomo result object

GOOD:
  use both logs and results.solver.status / termination_condition
```

---

## 13.22 Final checklist

```text id="zz60gf"
[ ] Use tee=True during model bring-up.
[ ] Save logfile for failures and benchmarks.
[ ] Set print_user_options=yes for option-profile debugging.
[ ] Know every iteration column: iter, objective, inf_pr, inf_du, lg(mu), ||d||, lg(rg), alpha_du, alpha_pr, ls.
[ ] Treat `r` iteration suffix as restoration phase.
[ ] Decode alpha_pr tags: f/F, h/H, k/K, n/N, R, w, s/S, t/T, r.
[ ] Enable print_info_string=yes for hard diagnostic runs.
[ ] Interpret objective/inf_pr nonmonotonicity correctly.
[ ] Distinguish desired success from acceptable-level success.
[ ] Treat local infeasibility as diagnostic, not always proof.
[ ] Treat max_iter/time exits as incomplete unless policy says otherwise.
[ ] Use load_solutions=False when solution-loading policy matters.
[ ] Load manually only after accepted status/termination.
[ ] Run residual audits for acceptable, feasible-only, infeasible, or limit exits.
[ ] Preserve logs, option profile, environment, and generated files for reproducibility.
```

[1]: https://coin-or.github.io/Ipopt/OUTPUT.html "Ipopt: Ipopt Output"
[2]: https://pyomo.readthedocs.io/en/latest/howto/solver_recipes.html "Solver Recipes — Pyomo 6.10.1.dev0 documentation"
[3]: https://coin-or.github.io/Ipopt/OPTIONS.html "Ipopt: Ipopt Options"
[4]: https://pyomo.readthedocs.io/en/latest/api/pyomo.opt.results.solver.TerminationCondition.html "TerminationCondition — Pyomo 6.10.1.dev0 documentation"

# Ipopt Advanced — Section 14: result loading, duals, reduced costs, and suffix data

Style target: dense advanced technical catalog / agent-ready reference. 

## 14.0 Result-data invariant

```text id="6fmrzf"
Pyomo + Ipopt result channels:

1. primal solution
   solver result → Var.value

2. constraint multipliers
   solver result → model.dual[ConstraintData]

3. variable-bound multipliers
   Ipopt result → model.ipopt_zL_out[VarData]
   Ipopt result → model.ipopt_zU_out[VarData]

4. warm-start export multipliers
   model.dual[ConstraintData]       → Ipopt constraint-multiplier start
   model.ipopt_zL_in[VarData]       → Ipopt lower-bound multiplier start
   model.ipopt_zU_in[VarData]       → Ipopt upper-bound multiplier start

5. APPSI solution access
   get_primals()
   get_duals()
   get_reduced_costs()
   get_slacks()
   load_vars()
```

Pyomo `Suffix` components are the primary mechanism for moving extra solver/model data into or out of a solve; Pyomo’s suffix docs state that suffix names available for import can be solver- and interface-specific, and that constraint dual multipliers are the most common imported suffix when the solver supplies them. ([Pyomo Documentation][1])

---

## 14.1 Primal variable loading: classic Pyomo `SolverFactory("ipopt")`

### Default load path

```python id="tsxkdy"
import pyomo.environ as pyo

opt = pyo.SolverFactory("ipopt")
results = opt.solve(model, tee=True)

# After a successful solve, primal values are available through Var.value.
print(pyo.value(model.x))
```

### Strict load path: inspect first, load manually

```python id="ptxuhc"
from pyomo.opt import SolverStatus, TerminationCondition

results = opt.solve(
    model,
    tee=True,
    load_solutions=False,
)

if (
    results.solver.status == SolverStatus.ok
    and results.solver.termination_condition == TerminationCondition.optimal
):
    model.solutions.load_from(results)
else:
    raise RuntimeError(
        f"Rejected solve result: "
        f"status={results.solver.status}, "
        f"termination={results.solver.termination_condition}"
    )
```

Pyomo’s solver recipes explicitly document `load_solutions=False`, followed by manual `model.solutions.load_from(results)` when the termination condition is optimal; the same page shows checking `results.solver.status` and `results.solver.termination_condition` before trusting the solution. ([Pyomo Documentation][2])

### Agent policy

```text id="wlrnch"
Use default loading:
  interactive notebooks
  trusted toy examples
  exploratory scripts

Use load_solutions=False:
  production pipelines
  nonconvex NLPs
  acceptable-level termination policies
  infeasibility diagnostics
  time/iteration-limited solves
  any solve where stale or failed values must not overwrite current Var.value
```

---

## 14.2 Manual-load wrapper

```python id="saw7x5"
from __future__ import annotations

import pyomo.environ as pyo
from pyomo.opt import SolverStatus, TerminationCondition


def solve_ipopt_and_load_if_accepted(
    model,
    *,
    opt=None,
    tee: bool = True,
    allow_locally_optimal: bool = True,
    allow_acceptable_text: bool = False,
):
    opt = opt or pyo.SolverFactory("ipopt")
    if not opt.available(exception_flag=False):
        raise RuntimeError("Ipopt executable unavailable.")

    results = opt.solve(model, tee=tee, load_solutions=False)

    status = results.solver.status
    tc = results.solver.termination_condition
    solver_text = str(results.solver).lower()

    accepted = (
        status == SolverStatus.ok
        and tc == TerminationCondition.optimal
    )

    if allow_locally_optimal:
        accepted = accepted or (
            status == SolverStatus.ok
            and tc == TerminationCondition.locallyOptimal
        )

    if allow_acceptable_text:
        accepted = accepted or ("acceptable" in solver_text)

    if not accepted:
        raise RuntimeError(f"Solution not loaded: status={status}, termination={tc}")

    model.solutions.load_from(results)
    return results
```

**Value case**

```text id="qqh5px"
Manual load gate prevents:
  failed-solve values overwriting incumbent values
  locally infeasible values entering downstream code
  time-limited candidate treated as optimal
  stale warm-start suffixes from a rejected solve
```

---

## 14.3 Constraint duals through `model.dual`

### Declare import dual suffix

```python id="d0ohmo"
model.dual = pyo.Suffix(direction=pyo.Suffix.IMPORT)
```

### Solve and access constraint multipliers

```python id="zdi12u"
results = opt.solve(model, tee=True)

for c in model.component_data_objects(pyo.Constraint, active=True):
    if c in model.dual:
        print(c.name, model.dual[c])
```

Pyomo documents that declaring an active suffix named `dual` with an import-style direction causes constraint dual information to be collected into solver results, assuming the solver supplies dual information; after the result is loaded, dual values are accessible through `model.dual[constraint]`. ([Pyomo Documentation][1])

### Declare round-trip dual suffix for warm starts

```python id="lf3d9s"
model.dual = pyo.Suffix(direction=pyo.Suffix.IMPORT_EXPORT)
```

Pyomo’s NL file interface recognizes an export-style suffix named `dual` as initialization for constraint multipliers, and the docs note that a single `IMPORT_EXPORT` suffix can both import and export dual information. ([Pyomo Documentation][1])

### Safe dual access helper

```python id="7h63dx"
def get_constraint_dual(model, con, default=None):
    if not hasattr(model, "dual"):
        return default
    return model.dual.get(con, default)
```

### Bulk dual table

```python id="4chca8"
def dual_table(model):
    rows = []
    if not hasattr(model, "dual"):
        return rows

    for c in model.component_data_objects(pyo.Constraint, active=True):
        rows.append({
            "constraint": c.name,
            "dual": model.dual.get(c, None),
            "body": pyo.value(c.body, exception=False),
            "lower": pyo.value(c.lower, exception=False) if c.lower is not None else None,
            "upper": pyo.value(c.upper, exception=False) if c.upper is not None else None,
        })
    return rows
```

---

## 14.4 Ipopt bound multipliers: `ipopt_zL_*`, `ipopt_zU_*`

### Import bound multipliers from Ipopt

```python id="u0wiu0"
model.ipopt_zL_out = pyo.Suffix(direction=pyo.Suffix.IMPORT)
model.ipopt_zU_out = pyo.Suffix(direction=pyo.Suffix.IMPORT)
```

### Export bound multipliers to Ipopt

```python id="04p47p"
model.ipopt_zL_in = pyo.Suffix(direction=pyo.Suffix.EXPORT)
model.ipopt_zU_in = pyo.Suffix(direction=pyo.Suffix.EXPORT)
```

Ipopt’s warm-start documentation states that ordinary solution information includes primal variables and active constraint multipliers, but not enough bound-multiplier information for an interior-point warm start; Ipopt communicates lower and upper variable-bound multipliers as `ipopt_zL_out` and `ipopt_zU_out`, and accepts warm-start values through `ipopt_zL_in` and `ipopt_zU_in`. ([COIN-OR Documentation][3])

### Pyomo suffix declaration block

```python id="u5xpix"
def attach_ipopt_suffixes(model):
    model.dual = pyo.Suffix(direction=pyo.Suffix.IMPORT_EXPORT)

    model.ipopt_zL_out = pyo.Suffix(direction=pyo.Suffix.IMPORT)
    model.ipopt_zU_out = pyo.Suffix(direction=pyo.Suffix.IMPORT)

    model.ipopt_zL_in = pyo.Suffix(direction=pyo.Suffix.EXPORT)
    model.ipopt_zU_in = pyo.Suffix(direction=pyo.Suffix.EXPORT)
```

Pyomo’s suffix docs show this exact Ipopt warm-start suffix pattern: `ipopt_zL_out` and `ipopt_zU_out` as import suffixes, `ipopt_zL_in` and `ipopt_zU_in` as export suffixes, and `dual` as `IMPORT_EXPORT`. ([Pyomo Documentation][1])

### Access bound multipliers

```python id="sedtko"
for v in model.component_data_objects(pyo.Var, active=True):
    zL = model.ipopt_zL_out.get(v, None)
    zU = model.ipopt_zU_out.get(v, None)
    print(v.name, pyo.value(v, exception=False), zL, zU)
```

### Active-bound report

```python id="v3k7ij"
def bound_multiplier_table(model, tol=1e-7):
    rows = []
    for v in model.component_data_objects(pyo.Var, active=True):
        val = pyo.value(v, exception=False)
        lb = pyo.value(v.lb, exception=False) if v.lb is not None else None
        ub = pyo.value(v.ub, exception=False) if v.ub is not None else None

        rows.append({
            "var": v.name,
            "value": val,
            "lb": lb,
            "ub": ub,
            "active_lb": (val is not None and lb is not None and abs(val - lb) <= tol),
            "active_ub": (val is not None and ub is not None and abs(val - ub) <= tol),
            "zL": getattr(model, "ipopt_zL_out", {}).get(v, None),
            "zU": getattr(model, "ipopt_zU_out", {}).get(v, None),
        })
    return rows
```

---

## 14.5 Bound multipliers versus “reduced costs”

```text id="c4ui6d"
Ipopt classic NL interface:
  ipopt_zL_out = lower-bound multiplier
  ipopt_zU_out = upper-bound multiplier

LP/MIP terminology:
  reduced cost is often a single variable-level marginal

NLP/IPM interpretation:
  lower and upper bound multipliers are separate KKT quantities
```

**Agent rule**

```text id="h8har3"
Do not collapse zL and zU into one reduced-cost number unless a downstream convention is explicitly defined.

If a single stationarity residual is needed:
  use KKT sign convention for the specific constraint representation
  validate with a small perturbation test
```

Ipopt distinguishes constraint multipliers from lower/upper variable-bound multipliers and exposes the bound multipliers separately as `zL` and `zU` channels. ([COIN-OR Documentation][3])

---

## 14.6 Warm-start round trip: suffix transfer

```python id="jjq0pz"
# First solve imports:
#   model.dual
#   model.ipopt_zL_out
#   model.ipopt_zU_out

results = opt.solve(model, tee=True)

# Copy output bound multipliers into input suffixes.
model.ipopt_zL_in.update(model.ipopt_zL_out)
model.ipopt_zU_in.update(model.ipopt_zU_out)

opt.options.update({
    "warm_start_init_point": "yes",
    "warm_start_bound_push": 1e-6,
    "warm_start_mult_bound_push": 1e-6,
    "mu_init": 1e-6,
})

results = opt.solve(model, tee=True)
```

Pyomo’s Ipopt warm-start example copies `ipopt_zL_out` into `ipopt_zL_in` and `ipopt_zU_out` into `ipopt_zU_in`, then sets `warm_start_init_point`, `warm_start_bound_push`, `warm_start_mult_bound_push`, and `mu_init`; the same example shows the warm-start iteration count dropping relative to the cold solve. ([Pyomo Documentation][1])

---

## 14.7 Suffix mechanics: direction, datatype, component mapping

### Direction

```python id="i3ztqs"
m.s1 = pyo.Suffix(direction=pyo.Suffix.LOCAL)
m.s2 = pyo.Suffix(direction=pyo.Suffix.IMPORT)
m.s3 = pyo.Suffix(direction=pyo.Suffix.EXPORT)
m.s4 = pyo.Suffix(direction=pyo.Suffix.IMPORT_EXPORT)
```

```text id="n4uqgv"
LOCAL:
  stays local; solver plugin does not import/export it

IMPORT:
  imported from solver to Pyomo

EXPORT:
  exported from Pyomo to solver

IMPORT_EXPORT:
  both imported and exported
```

Pyomo’s suffix docs define four suffix directions: `LOCAL`, `IMPORT`, `EXPORT`, and `IMPORT_EXPORT`; they also expose methods such as `importEnabled()` and `exportEnabled()` to test direction behavior. ([Pyomo Documentation][1])

### Component-keyed mapping

```python id="nytv9d"
model.dual[model.c] = 1.23
model.ipopt_zL_in[model.x] = 0.0
model.ipopt_zU_in[model.x] = 4.56
```

### Indexed component handling

```python id="5letma"
# Apply suffix value to parent indexed component.
model.priority.set_value(model.y, 1)

# Apply suffix value to individual component data.
model.ref[model.y[1]] = 0
model.ref[model.y[2]] = 1
model.ref[model.y[3]] = 2
```

Pyomo’s suffix docs show suffixes as mappings from Pyomo modeling components to values, including indexed components and individual indexed data entries, and show `set_value(...)` / dictionary assignment patterns for suffix population. ([Pyomo Documentation][1])

### Datatype

```python id="i2nqe6"
m.priority = pyo.Suffix(
    direction=pyo.Suffix.EXPORT,
    datatype=pyo.Suffix.INT,
)

m.dual = pyo.Suffix(
    direction=pyo.Suffix.IMPORT_EXPORT,
    datatype=pyo.Suffix.FLOAT,
)
```

**Agent rule**

```text id="qy3r0c"
For Ipopt dual and multiplier suffixes:
  use default FLOAT-compatible values
  do not store strings
  do not key by component names
  key by actual VarData / ConstraintData objects
```

---

## 14.8 Compatibility caveat: solver and interface support

```text id="cgu1h7"
Suffix declaration requests data.
It does not guarantee data exists.
Support depends on:
  solver
  solver interface
  problem type
  termination condition
  whether solution was loaded
  suffix name recognized by the interface
```

Pyomo states that suffix names available for import may be solver-specific and interface-specific, and that constraint dual collection assumes the solver supplies dual information. The APPSI base loader similarly raises runtime errors when primals, duals, slacks, or reduced costs are not valid for the current solution/problem type. ([Pyomo Documentation][1])

### Safe suffix access

```python id="ij1ow1"
def suffix_get(model, suffix_name, component, default=None):
    suffix = getattr(model, suffix_name, None)
    if suffix is None:
        return default
    return suffix.get(component, default)
```

### Check suffix population

```python id="j9ro8o"
def count_suffix_entries(model, suffix_name):
    suffix = getattr(model, suffix_name, None)
    if suffix is None:
        return 0
    return len(list(suffix.items()))
```

---

## 14.9 APPSI Ipopt result access: primals, duals, reduced costs, slacks

### APPSI solve and load primals

```python id="9atgft"
from pyomo.contrib import appsi

solver = appsi.solvers.Ipopt()
solver.ipopt_options["tol"] = 1e-8

res = solver.solve(model)

if res.termination_condition != appsi.base.TerminationCondition.optimal:
    raise RuntimeError(res.termination_condition)

solver.load_vars()
```

APPSI Ipopt documents `load_vars(vars_to_load=None)` as loading primal solution values into the `.value` attribute of variables; if `vars_to_load` is `None`, all primal variables are loaded. ([Pyomo Documentation][4])

### APPSI explicit primals

```python id="srtjo6"
primals = solver.get_primals()
x_value = primals[model.x]
```

### APPSI duals

```python id="usrrgf"
duals = solver.get_duals()
lambda_c = duals[model.c]

# Restricted load
duals_subset = solver.get_duals([model.c])
```

APPSI Ipopt documents `get_duals(cons_to_load=None)` as returning a dictionary mapping constraints to dual values, with an optional list restricting which constraints are loaded. ([Pyomo Documentation][4])

### APPSI reduced costs

```python id="0remr6"
reduced_costs = solver.get_reduced_costs()
rc_x = reduced_costs[model.x]

# Restricted load
reduced_costs_subset = solver.get_reduced_costs([model.x])
```

APPSI Ipopt documents `get_reduced_costs(vars_to_load=None)` as returning a mapping from variables to reduced costs, with an optional variable list restricting the returned values. ([Pyomo Documentation][4])

### APPSI slacks

```python id="8ss4wx"
slacks = solver.get_slacks()
slack_c = slacks[model.c]

# Restricted load
slacks_subset = solver.get_slacks([model.c])
```

APPSI Ipopt documents `get_slacks(cons_to_load=None)` as returning a dictionary mapping constraints to slack values, with an optional constraint list restricting the values. ([Pyomo Documentation][4])

---

## 14.10 APPSI result validity

```text id="m6229z"
APPSI solution-loader methods can become invalid after model/solver changes.
Do not cache primals/duals/reduced-costs/slacks across structural updates unless copied.
```

The APPSI base solution loader checks whether solution data is still valid before returning primals, duals, slacks, or reduced costs; if the solution is invalid or the solver did not provide that class of data, it raises runtime errors telling the user to check the termination condition and solver support. ([Pyomo Documentation][5])

### Defensive APPSI extraction

```python id="g1102y"
def safe_appsi_solution_snapshot(solver):
    snapshot = {}

    for name, method in [
        ("primals", solver.get_primals),
        ("duals", solver.get_duals),
        ("reduced_costs", solver.get_reduced_costs),
        ("slacks", solver.get_slacks),
    ]:
        try:
            snapshot[name] = dict(method())
        except Exception as exc:
            snapshot[name] = {
                "_error": f"{type(exc).__name__}: {exc}"
            }

    return snapshot
```

---

## 14.11 Sign convention: what agents should and should not assume

### Documentation reality

```text id="jmdn8j"
Classic suffix docs:
  document how to request/import/export duals
  do not provide a universal sign-convention guarantee for all solvers/interfaces

APPSI docs:
  get_duals docstring currently contains placeholder wording:
    "Declare sign convention in docstring here."
```

The APPSI Ipopt API page currently states “Declare sign convention in docstring here” under `get_duals`, then describes the returned object as a mapping from constraints to dual values; therefore, agents should not treat APPSI dual sign convention as self-documenting from that page alone. ([Pyomo Documentation][4])

### Agent policy

```text id="kq5l3p"
For dual-dependent algorithms:
  define sign convention explicitly in your application
  verify empirically on a one-row test
  document solver/interface/version
  do not mix classic suffix duals and APPSI duals without validation
```

### Empirical sign test: lower-bound row

```python id="np1mpy"
import pyomo.environ as pyo

def build_lower_bound_dual_test():
    m = pyo.ConcreteModel()
    m.x = pyo.Var(initialize=1.0)
    m.obj = pyo.Objective(expr=m.x)          # minimize x
    m.c = pyo.Constraint(expr=m.x >= 1.0)    # active lower row
    m.dual = pyo.Suffix(direction=pyo.Suffix.IMPORT)
    return m

m = build_lower_bound_dual_test()
opt = pyo.SolverFactory("ipopt")
res = opt.solve(m, tee=False)

print("x =", pyo.value(m.x))
print("dual(c) =", m.dual.get(m.c))
```

### Empirical sign test: upper-bound row

```python id="lgwo62"
def build_upper_bound_dual_test():
    m = pyo.ConcreteModel()
    m.x = pyo.Var(initialize=1.0)
    m.obj = pyo.Objective(expr=-m.x)         # minimize -x => maximize x
    m.c = pyo.Constraint(expr=m.x <= 1.0)    # active upper row
    m.dual = pyo.Suffix(direction=pyo.Suffix.IMPORT)
    return m
```

### Empirical sign test: equality row

```python id="nmf4ko"
def build_equality_dual_test():
    m = pyo.ConcreteModel()
    m.x = pyo.Var(initialize=1.0)
    m.obj = pyo.Objective(expr=2.0 * m.x)
    m.c = pyo.Constraint(expr=m.x == 1.0)
    m.dual = pyo.Suffix(direction=pyo.Suffix.IMPORT)
    return m
```

**Agent output rule**

```text id="lma7jv"
When reporting "shadow price":
  state the sign convention used.
When using duals for cuts/sensitivities:
  test sign on canonical one-row models.
When switching interface:
  re-test sign convention.
```

---

## 14.12 Classic Ipopt suffix result snapshot

```python id="ulsjf4"
def classic_ipopt_snapshot(model):
    snapshot = {
        "primals": {},
        "constraint_duals": {},
        "bound_multipliers_lower": {},
        "bound_multipliers_upper": {},
    }

    for v in model.component_data_objects(pyo.Var, active=True):
        snapshot["primals"][v.name] = pyo.value(v, exception=False)

        if hasattr(model, "ipopt_zL_out"):
            snapshot["bound_multipliers_lower"][v.name] = model.ipopt_zL_out.get(v, None)

        if hasattr(model, "ipopt_zU_out"):
            snapshot["bound_multipliers_upper"][v.name] = model.ipopt_zU_out.get(v, None)

    if hasattr(model, "dual"):
        for c in model.component_data_objects(pyo.Constraint, active=True):
            snapshot["constraint_duals"][c.name] = model.dual.get(c, None)

    return snapshot
```

### Use

```python id="fex4e7"
attach_ipopt_suffixes(model)

res = opt.solve(model, tee=True)

snap = classic_ipopt_snapshot(model)
print(snap)
```

---

## 14.13 APPSI solution snapshot

```python id="kxmjt8"
def appsi_ipopt_snapshot(model, solver):
    primals = solver.get_primals()
    duals = solver.get_duals()
    reduced_costs = solver.get_reduced_costs()
    slacks = solver.get_slacks()

    return {
        "primals": {
            v.name: primals.get(v, None)
            for v in model.component_data_objects(pyo.Var, active=True)
        },
        "duals": {
            c.name: duals.get(c, None)
            for c in model.component_data_objects(pyo.Constraint, active=True)
        },
        "reduced_costs": {
            v.name: reduced_costs.get(v, None)
            for v in model.component_data_objects(pyo.Var, active=True)
        },
        "slacks": {
            c.name: slacks.get(c, None)
            for c in model.component_data_objects(pyo.Constraint, active=True)
        },
    }
```

### Use

```python id="ezhsbr"
from pyomo.contrib import appsi

solver = appsi.solvers.Ipopt()
res = solver.solve(model)

if res.termination_condition == appsi.base.TerminationCondition.optimal:
    snap = appsi_ipopt_snapshot(model, solver)
    solver.load_vars()
else:
    raise RuntimeError(res.termination_condition)
```

---

## 14.14 Classic versus APPSI data-channel comparison

| Data                    | Classic `SolverFactory("ipopt")`                                              | APPSI Ipopt                                                      |
| ----------------------- | ----------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| primal variable values  | loaded into `Var.value` by result loading                                     | `load_vars()` or `get_primals()`                                 |
| constraint duals        | `model.dual[constraint]` with import suffix                                   | `get_duals()`                                                    |
| lower bound multipliers | `model.ipopt_zL_out[var]`                                                     | interface-dependent; use `get_reduced_costs()` where appropriate |
| upper bound multipliers | `model.ipopt_zU_out[var]`                                                     | interface-dependent; use `get_reduced_costs()` where appropriate |
| slacks                  | not a standard classic Ipopt suffix pattern                                   | `get_slacks()`                                                   |
| reduced costs           | not a single classic Ipopt suffix; lower/upper bound multipliers are separate | `get_reduced_costs()`                                            |
| warm-start export       | `dual`, `ipopt_zL_in`, `ipopt_zU_in` suffixes                                 | use APPSI/IPOPT options and supported update/result APIs         |
| sign convention         | solver/interface convention; validate                                         | docs currently incomplete; validate                              |

---

## 14.15 Suffix lifecycle hazards

```text id="w8zcsh"
Suffix data can become stale when:
  model structure changes
  variables are added/removed
  constraints are added/removed
  constraints are activated/deactivated
  fixed status changes
  bounds change materially
  solve failed but old suffix values remain
  load_solutions=False prevents current results from populating model values as expected
```

### Clear stale suffixes

```python id="yxuemq"
def clear_ipopt_suffix_values(model):
    for name in [
        "dual",
        "ipopt_zL_out",
        "ipopt_zU_out",
        "ipopt_zL_in",
        "ipopt_zU_in",
    ]:
        suffix = getattr(model, name, None)
        if suffix is not None:
            suffix.clearAllValues()
```

### Rebuild warm-start inputs only after accepted solve

```python id="y7erg0"
results = opt.solve(model, tee=True, load_solutions=False)

if results.solver.termination_condition == pyo.TerminationCondition.optimal:
    model.solutions.load_from(results)
    model.ipopt_zL_in.clearAllValues()
    model.ipopt_zU_in.clearAllValues()
    model.ipopt_zL_in.update(model.ipopt_zL_out)
    model.ipopt_zU_in.update(model.ipopt_zU_out)
else:
    clear_ipopt_suffix_values(model)
```

---

## 14.16 Dual and multiplier audit helpers

### Constraint-dual report

```python id="0iozkk"
def constraint_dual_report(model):
    rows = []
    dual = getattr(model, "dual", None)

    for c in model.component_data_objects(pyo.Constraint, active=True):
        body = pyo.value(c.body, exception=False)
        lb = pyo.value(c.lower, exception=False) if c.lower is not None else None
        ub = pyo.value(c.upper, exception=False) if c.upper is not None else None

        rows.append({
            "constraint": c.name,
            "body": body,
            "lower": lb,
            "upper": ub,
            "dual": None if dual is None else dual.get(c, None),
        })
    return rows
```

### Bound-multiplier report

```python id="ekrc5h"
def variable_multiplier_report(model):
    rows = []
    zL = getattr(model, "ipopt_zL_out", None)
    zU = getattr(model, "ipopt_zU_out", None)

    for v in model.component_data_objects(pyo.Var, active=True):
        val = pyo.value(v, exception=False)
        lb = pyo.value(v.lb, exception=False) if v.lb is not None else None
        ub = pyo.value(v.ub, exception=False) if v.ub is not None else None

        rows.append({
            "var": v.name,
            "value": val,
            "lower": lb,
            "upper": ub,
            "zL": None if zL is None else zL.get(v, None),
            "zU": None if zU is None else zU.get(v, None),
        })
    return rows
```

---

## 14.17 KKT-style consistency checks

### Complementarity-style bound check

```python id="3psh09"
def bound_complementarity_report(model):
    rows = []
    zL = getattr(model, "ipopt_zL_out", None)
    zU = getattr(model, "ipopt_zU_out", None)

    if zL is None or zU is None:
        return rows

    for v in model.component_data_objects(pyo.Var, active=True):
        val = pyo.value(v, exception=False)
        if val is None:
            continue

        lb = pyo.value(v.lb, exception=False) if v.lb is not None else None
        ub = pyo.value(v.ub, exception=False) if v.ub is not None else None

        zL_val = zL.get(v, 0.0) or 0.0
        zU_val = zU.get(v, 0.0) or 0.0

        comp_L = None if lb is None else zL_val * max(0.0, val - lb)
        comp_U = None if ub is None else zU_val * max(0.0, ub - val)

        rows.append({
            "var": v.name,
            "zL": zL_val,
            "zU": zU_val,
            "comp_L": comp_L,
            "comp_U": comp_U,
        })
    return rows
```

**Agent caveat**

```text id="y2ncs5"
Complementarity report is diagnostic only.
Ipopt uses internal scaling, bound relaxation, barrier terms, and sign conventions.
Use solver-reported residuals for official convergence status.
```

---

## 14.18 Result-loading policy table

| Situation                    |             `load_solutions` | Suffix use                    | Agent action                                  |
| ---------------------------- | ---------------------------: | ----------------------------- | --------------------------------------------- |
| trusted optimal solve        |            default or manual | optional                      | load primals                                  |
| production strict solve      |                      `False` | optional                      | inspect status, then load                     |
| infeasibility debugging      |                `False` often | duals optional                | inspect candidate separately                  |
| warm-start loop              | default/manual accepted only | required                      | load after accepted solve, then copy suffixes |
| acceptable-level solve       |                      `False` | useful                        | residual audit before load                    |
| APPSI repeated solve         |                APPSI methods | methods, not classic suffixes | call `load_vars()` after accepted solve       |
| dual-sensitive decomposition |                       manual | required                      | validate sign convention                      |
| structural model change      |              clear/redeclare | clear suffixes                | cold solve or rebuild suffix payload          |

---

## 14.19 Anti-pattern catalog

```text id="2i35fg"
BAD:
  use model.dual without declaring model.dual = Suffix(IMPORT)

GOOD:
  declare model.dual before solve.

BAD:
  read model.dual before loading solver results.

GOOD:
  solve, check termination, load results, then read duals.

BAD:
  assume suffix support is universal.

GOOD:
  check solver/interface docs and handle missing suffix entries.

BAD:
  use string names as suffix keys.

GOOD:
  use Pyomo component objects: model.dual[model.c].

BAD:
  treat ipopt_zL_out and ipopt_zU_out as interchangeable.

GOOD:
  zL = lower-bound multiplier, zU = upper-bound multiplier.

BAD:
  reuse warm-start suffixes after adding/removing constraints.

GOOD:
  clear suffixes and cold solve or rebuild suffix payload.

BAD:
  assume APPSI dual sign convention from incomplete docs.

GOOD:
  run sign-convention micro-tests and document the result.

BAD:
  equate APPSI reduced costs with classic Ipopt zL/zU without validation.

GOOD:
  document and test any conversion from bound multipliers to reduced-cost-like values.
```

---

## 14.20 Final checklist

```text id="19hwqo"
[ ] Use load_solutions=False when termination policy matters.
[ ] Manually call model.solutions.load_from(results) only after accepted termination.
[ ] Declare model.dual = Suffix(IMPORT) to import constraint duals.
[ ] Use model.dual = Suffix(IMPORT_EXPORT) for Ipopt warm-start round trips.
[ ] Declare ipopt_zL_out / ipopt_zU_out as IMPORT for bound multipliers.
[ ] Declare ipopt_zL_in / ipopt_zU_in as EXPORT for warm-start bound multipliers.
[ ] Copy zL_out → zL_in and zU_out → zU_in exactly.
[ ] Treat zL and zU as separate lower/upper bound multiplier channels.
[ ] Use APPSI load_vars() or get_primals() for APPSI primal handling.
[ ] Use APPSI get_duals(), get_reduced_costs(), get_slacks() only after valid accepted solve.
[ ] Treat dual/reduced-cost/slack availability as solver/interface/problem-type dependent.
[ ] Validate dual sign convention with micro-tests before using duals in cuts/sensitivities.
[ ] Clear suffix values after failed solves or structural model changes.
[ ] Key suffix data by Pyomo components, not component-name strings.
[ ] Archive primal/dual/bound-multiplier snapshots for reproducible sensitivity/warm-start studies.
```

[1]: https://pyomo.readthedocs.io/en/6.8.0/pyomo_modeling_components/Suffixes.html "Suffixes — Pyomo 6.8.0 documentation"
[2]: https://pyomo.readthedocs.io/en/latest/howto/solver_recipes.html "Solver Recipes — Pyomo 6.10.1.dev0 documentation"
[3]: https://coin-or.github.io/Ipopt/SPECIALS.html "Ipopt: Special Features"
[4]: https://pyomo.readthedocs.io/en/6.9.0/api/pyomo.contrib.appsi.solvers.ipopt.Ipopt.html "Ipopt — Pyomo 6.9.0 documentation"
[5]: https://pyomo.readthedocs.io/en/stable/_modules/pyomo/contrib/appsi/base.html "pyomo.contrib.appsi.base — Pyomo 6.10.0 documentation"

# Ipopt Advanced — Section 15: common Ipopt option bundles

Style target: dense advanced technical catalog / agent-ready reference. 

## 15.0 Bundle invariant

```text id="iot1lz"
Ipopt option bundle =
  named, reusable solver profile
  + explicit use case
  + exact Pyomo syntax
  + expected value
  + failure modes
  + production/development boundary
```

Ipopt options are string-named values typed as Number, Integer, or String; they can be set through calling code or an `ipopt.opt` file, and the option-file syntax is `option_name value` with `#` comments. Pyomo solver-object options persist across solves, while `solve(..., options={...})` options are solve-local temporary overrides. ([COIN-OR Documentation][1])

---

## 15.1 Option-bundle deployment channels

### Persistent Pyomo profile

```python id="vjq1qq"
opt = pyo.SolverFactory("ipopt")
opt.options.update({
    "tol": 1e-8,
    "max_iter": 1000,
})
res1 = opt.solve(m1, tee=True)
res2 = opt.solve(m2, tee=True)  # same options persist
```

### Solve-local profile

```python id="gjmzg0"
res = opt.solve(
    model,
    tee=True,
    options={
        "tol": 1e-6,
        "max_iter": 500,
    },
)
```

### `ipopt.opt` profile

```text id="k4ec7u"
# ipopt.opt
tol 1e-8
max_iter 1000
print_user_options yes
```

**Agent rule**

```text id="n8a7ws"
Use opt.options.update(...) for reusable solver-object profiles.
Use solve(options={...}) for one-off diagnostics.
Use ipopt.opt for executable-level reproducibility and file-output-only options.
Do not silently mix multiple channels unless precedence is documented.
```

---

## 15.2 Bundle: Debug derivatives

### Minimal requested bundle

```python id="x49w0q"
opt.options.update({
    "derivative_test": "first-order",
    "derivative_test_print_all": "yes",
    "max_iter": 0,
})
```

### Recommended full bundle

```python id="sr0gdu"
IPOPT_DEBUG_DERIVATIVES_FIRST = {
    "derivative_test": "first-order",
    "derivative_test_tol": 1e-4,
    "derivative_test_perturbation": 1e-8,
    "derivative_test_print_all": "yes",
    "max_iter": 0,
    "print_level": 7,
    "print_user_options": "yes",
}
```

### Second-order variant

```python id="qhh3uq"
IPOPT_DEBUG_DERIVATIVES_SECOND = {
    "derivative_test": "second-order",
    "derivative_test_tol": 1e-4,
    "derivative_test_perturbation": 1e-8,
    "derivative_test_print_all": "yes",
    "max_iter": 0,
    "print_level": 7,
    "print_user_options": "yes",
}
```

Ipopt’s derivative checker is explicitly “slow,” runs before optimization at the user-provided starting point, and supports `first-order`, `second-order`, and `only-second-order`; `derivative_test_perturbation` defaults to `1e-8`, `derivative_test_tol` defaults to `1e-4`, and `derivative_test_print_all` controls whether all derivative estimates are printed. ([COIN-OR Documentation][1])

### Value case

```text id="35ueeh"
Detect:
  wrong objective gradient
  wrong constraint Jacobian values
  missing Jacobian sparsity entries
  wrong Hessian entries
  external-function derivative defects
  nonsmooth/domain-boundary derivative artifacts
```

### Use when

```text id="putmsc"
[ ] new nonlinear Pyomo template
[ ] direct TNLP / cyipopt callback implementation
[ ] ExternalFunction used
[ ] Restoration_Failed with unclear cause
[ ] Error_In_Step_Computation
[ ] INVALID_NUMBER_DETECTED
[ ] exact Hessian used and second derivatives suspicious
```

### Avoid when

```text id="jo8lz6"
[ ] production solve
[ ] full-scale model with thousands/millions of variables
[ ] variables initialized at log/sqrt/division singularities
[ ] model is intentionally nonsmooth
```

### Pyomo application

```python id="b7v511"
opt = pyo.SolverFactory("ipopt")
opt.options.update(IPOPT_DEBUG_DERIVATIVES_FIRST)
res = opt.solve(model, tee=True)
```

### `ipopt.opt`

```text id="9zu0rx"
# Debug first derivatives only; do not optimize.
derivative_test first-order
derivative_test_tol 1e-4
derivative_test_perturbation 1e-8
derivative_test_print_all yes
max_iter 0
print_level 7
print_user_options yes
```

### Agent caveats

```text id="vg7nmx"
max_iter=0:
  checker runs, optimization does not proceed.

first-order before second-order:
  fix first-derivative defects before debugging Hessian defects.

small representative instance:
  required for runtime and log-size control.
```

---

## 15.3 Bundle: Fast quiet solve

### Minimal requested bundle

```python id="f6yx9r"
opt.options.update({
    "print_level": 0,
    "sb": "yes",
})
```

### Recommended quiet production bundle

```python id="zm53zp"
IPOPT_FAST_QUIET = {
    "print_level": 0,
    "sb": "yes",
    "tol": 1e-8,
    "max_iter": 1000,
}
```

### Conservative quiet bundle with timing disabled

```python id="ulkdu0"
IPOPT_QUIET_STRICT = {
    "print_level": 0,
    "sb": "yes",
    "print_user_options": "no",
    "print_timing_statistics": "no",
    "tol": 1e-8,
    "max_iter": 3000,
}
```

Ipopt’s `print_level` controls console verbosity from 0 to 12, defaulting to 5; Pyomo’s `tee=True` controls whether solver output is streamed at the Pyomo layer, so a quiet solve usually combines low Ipopt `print_level` with `tee=False` in production. ([COIN-OR Documentation][1])

### Syntax

```python id="fkybho"
opt = pyo.SolverFactory("ipopt")
opt.options.update(IPOPT_FAST_QUIET)

results = opt.solve(model, tee=False)
```

### Value case

```text id="o9e9jm"
Reduce:
  console noise
  notebook output bloat
  CI log volume
  repeated-solve loop overhead from logging
  operational log storage
```

### Use when

```text id="t0whiq"
[ ] model already validated
[ ] solver profile already audited
[ ] repeated solves / parametric sweep
[ ] batch production pipeline
[ ] service endpoint where logs are captured separately
```

### Avoid when

```text id="g414rd"
[ ] first solve of a new model
[ ] option profile under development
[ ] infeasibility/debugging
[ ] derivative or restoration issues suspected
[ ] termination handling depends on inspecting Ipopt text logs
```

### Agent caveat: `sb`

```text id="ehtv8d"
sb=yes:
  commonly used with Ipopt AMPL/executable interfaces to suppress banner-style output.
  It is not part of the main algorithmic option table in the generic Ipopt options page.
  Validate through `ipopt -=` / installed executable option dump if deployment portability matters.
```

### Installed-build check

```bash id="4h25to"
ipopt -= | grep -E '(^|[[:space:]])sb([[:space:]]|=|$)'
```

---

## 15.4 Bundle: Relaxed convergence

### Minimal requested bundle

```python id="bdpkuq"
opt.options.update({
    "tol": 1e-6,
    "acceptable_tol": 1e-5,
    "max_iter": 1000,
})
```

### Recommended engineering relaxed bundle

```python id="eaqapd"
IPOPT_RELAXED_CONVERGENCE = {
    "tol": 1e-6,
    "acceptable_tol": 1e-5,
    "acceptable_iter": 10,
    "constr_viol_tol": 1e-6,
    "compl_inf_tol": 1e-6,
    "max_iter": 1000,
    "print_level": 5,
}
```

### Fast screening variant

```python id="cv93na"
IPOPT_RELAXED_SCREENING = {
    "tol": 1e-5,
    "acceptable_tol": 1e-4,
    "acceptable_iter": 5,
    "acceptable_constr_viol_tol": 1e-4,
    "acceptable_compl_inf_tol": 1e-4,
    "max_iter": 300,
    "print_level": 0,
    "sb": "yes",
}
```

Ipopt’s `tol` is the desired convergence tolerance and successful termination additionally requires absolute criteria for dual infeasibility, constraint violation, and complementarity; `acceptable_tol` defines a secondary “acceptable” convergence level, and `acceptable_iter` controls how many acceptable iterates in a row trigger acceptable termination. ([COIN-OR Documentation][1])

### Value case

```text id="rp8vtx"
Trade:
  high-accuracy KKT target
for:
  faster solve
  fewer restoration/line-search stalls
  robust screening of many scenarios
  practical engineering accuracy
```

### Use when

```text id="ln0wri"
[ ] data accuracy does not justify 1e-8 KKT residuals
[ ] many related scenarios must be screened
[ ] subproblem in decomposition/heuristic loop
[ ] nonconvex multi-start initial sweep
[ ] early-stage model validation
```

### Avoid when

```text id="dvy53i"
[ ] final benchmark
[ ] post-optimality sensitivity
[ ] tight feasibility requirement
[ ] regulatory/safety constraints
[ ] small model where exact convergence is cheap
```

### Pyomo strict loading policy with relaxed solve

```python id="jol0z8"
from pyomo.opt import SolverStatus, TerminationCondition

opt.options.update(IPOPT_RELAXED_CONVERGENCE)
results = opt.solve(model, tee=True, load_solutions=False)

if (
    results.solver.status == SolverStatus.ok
    and results.solver.termination_condition == TerminationCondition.optimal
):
    model.solutions.load_from(results)
else:
    raise RuntimeError(
        f"Relaxed solve did not meet accepted policy: "
        f"{results.solver.status}, {results.solver.termination_condition}"
    )
```

### Agent warning

```text id="y8vc1p"
Relaxing tol does not automatically relax all absolute feasibility gates.
If physical feasibility is the priority:
  set constr_viol_tol and acceptable_constr_viol_tol explicitly.
If acceptable termination is allowed:
  label result as degraded/acceptable, not desired-optimal.
```

---

## 15.5 Bundle: Limited-memory Hessian

### Minimal requested bundle

```python id="g32slj"
opt.options.update({
    "hessian_approximation": "limited-memory",
})
```

### Recommended limited-memory bundle

```python id="dxd3sx"
IPOPT_LIMITED_MEMORY_HESSIAN = {
    "hessian_approximation": "limited-memory",
    "limited_memory_update_type": "bfgs",
    "limited_memory_max_history": 10,
    "hessian_approximation_space": "nonlinear-variables",
}
```

### Large-model reduced-memory variant

```python id="95524a"
IPOPT_LIMITED_MEMORY_LARGE = {
    "hessian_approximation": "limited-memory",
    "limited_memory_update_type": "bfgs",
    "limited_memory_max_history": 6,
    "hessian_approximation_space": "nonlinear-variables",
    "tol": 1e-6,
    "acceptable_tol": 1e-5,
}
```

Ipopt’s `hessian_approximation` defaults to `exact`; `limited-memory` performs a limited-memory quasi-Newton approximation. `hessian_approximation_space` defaults to `nonlinear-variables`, while `all-variables` is also available. ([COIN-OR Documentation][1])

### Value case

```text id="1n6txh"
Avoid:
  exact Hessian evaluation
  exact Hessian storage
  dense/expensive second derivatives
  bad/missing external-function Hessians

Accept:
  more major iterations
  weaker local convergence
  less curvature information
```

### Use when

```text id="y5q18p"
[ ] exact Hessian too expensive
[ ] Hessian memory/fill-in dominates
[ ] external functions lack Hessians
[ ] huge model with acceptable moderate accuracy
[ ] early solve where feasibility/rough optimum matters
```

### Avoid when

```text id="pixhlo"
[ ] small/medium smooth Pyomo algebraic NLP
[ ] final high-accuracy solve
[ ] highly constrained nonlinear equality system
[ ] exact derivatives are reliable and affordable
[ ] dual stationarity quality is critical
```

### Combine with acceptable objective-change criterion

```python id="5w3f9o"
opt.options.update({
    "hessian_approximation": "limited-memory",
    "acceptable_tol": 1e-5,
    "acceptable_obj_change_tol": 1e-8,
})
```

Ipopt notes that `acceptable_obj_change_tol` is useful for quasi-Newton mode because quasi-Newton approximations can have difficulty reducing dual infeasibility. ([COIN-OR Documentation][1])

### Agent warning

```text id="4kvsjy"
Do not use limited-memory to mask:
  nonsmooth expressions
  wrong Jacobians
  infeasible constraints
  undefined external functions
  bad scaling
```

---

## 15.6 Bundle: MUMPS tuning

### Minimal requested bundle

```python id="4ik4me"
opt.options.update({
    "linear_solver": "mumps",
    "mumps_pivtol": 1e-6,
    "mumps_pivtolmax": 0.1,
})
```

### Recommended portable MUMPS baseline

```python id="o5effl"
IPOPT_MUMPS_BASELINE = {
    "linear_solver": "mumps",
    "mumps_pivtol": 1e-6,
    "mumps_pivtolmax": 0.1,
    "mumps_print_level": 0,
}
```

### Stability-biased MUMPS bundle

```python id="c0a8wj"
IPOPT_MUMPS_STABILITY = {
    "linear_solver": "mumps",
    "mumps_pivtol": 1e-5,
    "mumps_pivtolmax": 0.1,
    "mumps_mem_percent": 2000,
    "mumps_print_level": 2,
}
```

### Memory-constrained diagnostic variant

```python id="i23pfr"
IPOPT_MUMPS_MEMORY_CONSTRAINED = {
    "linear_solver": "mumps",
    "mumps_mem_percent": 100,
    "mumps_print_level": 2,
}
```

Ipopt documents `mumps_print_level`, `mumps_pivtol`, `mumps_pivtolmax`, and `mumps_mem_percent`; smaller pivot tolerances favor sparsity, larger tolerances favor stability, and Ipopt may increase pivot tolerance up to `mumps_pivtolmax` for more accurate linear solves. ([COIN-OR Documentation][1])

### Value case

```text id="ov8ee4"
MUMPS baseline:
  portable conda-forge-friendly linear solver
  open/package-friendly deployment
  good default for generated Pyomo code

MUMPS tuning:
  improve numerical pivot stability
  expose MUMPS diagnostics
  mitigate workspace/fill-in failures
```

### Use when

```text id="e4h1eo"
[ ] conda-forge Ipopt deployment
[ ] no licensed HSL/Pardiso solver
[ ] cross-platform reproducibility desired
[ ] linear solver warnings/errors occur
[ ] KKT regularization or factorization instability suspected
```

### Avoid over-tuning when

```text id="0nc647"
[ ] derivative checker has not been run
[ ] model is badly scaled
[ ] constraints are locally infeasible
[ ] Hessian approximation strategy is the real issue
[ ] active bounds are pathological
```

### Agent workflow

```python id="7eh0iu"
opt = pyo.SolverFactory("ipopt")

if hasattr(opt, "has_linear_solver"):
    try:
        if not opt.has_linear_solver("mumps"):
            raise RuntimeError("MUMPS unavailable in this Ipopt build.")
    except Exception:
        # Decide whether to fail or proceed based on deployment policy.
        pass

opt.options.update(IPOPT_MUMPS_BASELINE)
res = opt.solve(model, tee=True)
```

---

## 15.7 Bundle: Strict final solve

```python id="jblgp3"
IPOPT_STRICT_FINAL = {
    "tol": 1e-9,
    "dual_inf_tol": 1e-8,
    "constr_viol_tol": 1e-8,
    "compl_inf_tol": 1e-8,
    "acceptable_iter": 0,
    "max_iter": 5000,
    "print_user_options": "yes",
    "print_level": 5,
}
```

### Value case

```text id="h1zjz2"
Use for:
  final report
  sensitivity study
  regression benchmark
  strict feasibility contract
  high-quality local KKT point
```

### Caveat

```text id="1ulkmc"
Strict tolerances require:
  good scaling
  correct derivatives
  robust linear solver
  meaningful data precision
```

`acceptable_iter=0` disables Ipopt’s acceptable-termination heuristic, and desired termination requires `tol` plus the absolute dual/constraint/complementarity thresholds. ([COIN-OR Documentation][1])

---

## 15.8 Bundle: Warm-start resolve

```python id="tlr7hl"
IPOPT_WARM_START = {
    "warm_start_init_point": "yes",
    "warm_start_bound_push": 1e-6,
    "warm_start_mult_bound_push": 1e-6,
    "mu_init": 1e-6,
}
```

### Conservative warm-start variant

```python id="aaqes1"
IPOPT_WARM_START_CONSERVATIVE = {
    "warm_start_init_point": "yes",
    "warm_start_bound_push": 1e-4,
    "warm_start_mult_bound_push": 1e-4,
    "mu_init": 1e-4,
}
```

`warm_start_init_point=yes` tells Ipopt to use a warm-start initialization with primal and dual values from a related problem; `warm_start_bound_push` and `warm_start_mult_bound_push` control warm-start pushes for primal bound positions and bound multipliers. ([COIN-OR Documentation][1])

### Required Pyomo suffix context

```python id="s4zm2p"
model.dual = pyo.Suffix(direction=pyo.Suffix.IMPORT_EXPORT)
model.ipopt_zL_out = pyo.Suffix(direction=pyo.Suffix.IMPORT)
model.ipopt_zU_out = pyo.Suffix(direction=pyo.Suffix.IMPORT)
model.ipopt_zL_in = pyo.Suffix(direction=pyo.Suffix.EXPORT)
model.ipopt_zU_in = pyo.Suffix(direction=pyo.Suffix.EXPORT)

# after accepted solve:
model.ipopt_zL_in.update(model.ipopt_zL_out)
model.ipopt_zU_in.update(model.ipopt_zU_out)
opt.options.update(IPOPT_WARM_START)
```

### Value case

```text id="7tbg08"
Use for:
  parametric sweeps
  MPC / rolling-horizon NLPs
  decomposition subproblems
  related solves with stable active sets
```

---

## 15.9 Bundle: Feasibility and restoration diagnostics

```python id="r9i0zo"
IPOPT_FEASIBILITY_DIAG = {
    "print_level": 7,
    "print_user_options": "yes",
    "inf_pr_output": "original",
    "expect_infeasible_problem": "yes",
    "required_infeasibility_reduction": 0.99,
    "max_resto_iter": 5000,
}
```

### Value case

```text id="lrz5lg"
Use when:
  Infeasible_Problem_Detected
  Restoration_Failed
  high inf_pr persists
  constraint residual report needed
  feasibility expected but not found
```

### Caveat

```text id="o83w3y"
Do not use this as a default solve accelerator.
It biases behavior toward infeasibility/restoration diagnostics.
```

---

## 15.10 Bundle: NaN/Inf derivative diagnostics

```python id="kiu2qk"
IPOPT_NANINF_DIAG = {
    "check_derivatives_for_naninf": "yes",
    "print_level": 7,
    "max_iter": 0,
}
```

### Value case

```text id="405mfh"
Detect:
  NaN/Inf in Jacobian
  NaN/Inf in Hessian of Lagrangian
  domain errors in derivatives
  external-function derivative failures
```

`check_derivatives_for_naninf=yes` makes Ipopt error on invalid numbers in derivative matrices and print the offending matrix at detailed output level; Ipopt warns that this can create large output. ([COIN-OR Documentation][1])

---

## 15.11 Bundle: Output audit

```python id="tbp4z2"
IPOPT_OUTPUT_AUDIT = {
    "print_level": 5,
    "print_user_options": "yes",
    "print_info_string": "yes",
    "inf_pr_output": "original",
    "print_timing_statistics": "yes",
}
```

### Value case

```text id="it20pa"
Use for:
  option-profile validation
  solver-log regression artifacts
  diagnosing restoration/watchdog/tiny-step behavior
  timing split between NLP evaluation and linear algebra
```

Ipopt supports `print_user_options`, `print_info_string`, `inf_pr_output`, and `print_timing_statistics`; `inf_pr_output=original` prints the original NLP constraint violation, while `internal` prints violation in Ipopt’s internal reformulation. ([COIN-OR Documentation][1])

---

## 15.12 Bundle composition rules

### Safe composition examples

```python id="7copfk"
opt.options.update(IPOPT_RELAXED_CONVERGENCE)
opt.options.update(IPOPT_MUMPS_BASELINE)
```

```python id="93gppd"
opt.options.update(IPOPT_LIMITED_MEMORY_HESSIAN)
opt.options.update(IPOPT_RELAXED_CONVERGENCE)
```

```python id="z81f0a"
opt.options.update(IPOPT_OUTPUT_AUDIT)
opt.options.update(IPOPT_MUMPS_STABILITY)
```

### Dangerous / contradictory composition

```python id="k2fx1h"
# contradictory: derivative checker only, but looks like normal solve profile
opt.options.update(IPOPT_DEBUG_DERIVATIVES_FIRST)
opt.options.update(IPOPT_FAST_QUIET)
```

```python id="7sjmc7"
# contradictory: strict desired convergence disabled by acceptable termination unless acceptable_iter=0
opt.options.update(IPOPT_STRICT_FINAL)
opt.options.update({"acceptable_iter": 15})
```

```python id="0i952x"
# conflicting with exact Hessian intent
opt.options.update({"hessian_approximation": "exact"})
opt.options.update(IPOPT_LIMITED_MEMORY_HESSIAN)
```

### Agent rule

```text id="ad80c2"
Last update wins.
Bundle order matters.
Expose final options before solve with print_user_options=yes during development.
```

---

## 15.13 Option-profile registry pattern

```python id="wyf37a"
IPOPT_BUNDLES = {
    "debug_derivatives_first": IPOPT_DEBUG_DERIVATIVES_FIRST,
    "debug_derivatives_second": IPOPT_DEBUG_DERIVATIVES_SECOND,
    "fast_quiet": IPOPT_FAST_QUIET,
    "relaxed": IPOPT_RELAXED_CONVERGENCE,
    "limited_memory": IPOPT_LIMITED_MEMORY_HESSIAN,
    "mumps": IPOPT_MUMPS_BASELINE,
    "mumps_stability": IPOPT_MUMPS_STABILITY,
    "strict_final": IPOPT_STRICT_FINAL,
    "warm_start": IPOPT_WARM_START,
    "feasibility_diag": IPOPT_FEASIBILITY_DIAG,
    "naninf_diag": IPOPT_NANINF_DIAG,
    "output_audit": IPOPT_OUTPUT_AUDIT,
}


def apply_ipopt_bundles(opt, *bundle_names, extra_options=None):
    final = {}
    for name in bundle_names:
        try:
            final.update(IPOPT_BUNDLES[name])
        except KeyError as exc:
            raise ValueError(f"Unknown Ipopt bundle: {name}") from exc

    if extra_options:
        final.update(extra_options)

    opt.options.update(final)
    return final
```

### Usage

```python id="fvpg0p"
opt = pyo.SolverFactory("ipopt")

final_options = apply_ipopt_bundles(
    opt,
    "output_audit",
    "relaxed",
    "mumps",
    extra_options={
        "max_iter": 2000,
    },
)

print(final_options)
res = opt.solve(model, tee=True)
```

---

## 15.14 Profile factory with termination policy

```python id="rouhxl"
from dataclasses import dataclass
from pyomo.opt import SolverStatus, TerminationCondition
import pyomo.environ as pyo


@dataclass(frozen=True)
class IpoptProfile:
    name: str
    options: dict[str, object]
    load_policy: str  # "strict", "allow_acceptable", "diagnostic"


PROFILES = {
    "debug_derivatives": IpoptProfile(
        name="debug_derivatives",
        options=IPOPT_DEBUG_DERIVATIVES_FIRST,
        load_policy="diagnostic",
    ),
    "fast_quiet": IpoptProfile(
        name="fast_quiet",
        options=IPOPT_FAST_QUIET,
        load_policy="strict",
    ),
    "relaxed": IpoptProfile(
        name="relaxed",
        options=IPOPT_RELAXED_CONVERGENCE,
        load_policy="allow_acceptable",
    ),
    "strict_final": IpoptProfile(
        name="strict_final",
        options=IPOPT_STRICT_FINAL,
        load_policy="strict",
    ),
}


def solve_with_ipopt_profile(model, profile_name: str, *, tee=True, extra_options=None):
    profile = PROFILES[profile_name]

    opt = pyo.SolverFactory("ipopt")
    opt.options.update(profile.options)
    if extra_options:
        opt.options.update(extra_options)

    results = opt.solve(model, tee=tee, load_solutions=False)

    status = results.solver.status
    tc = results.solver.termination_condition
    solver_text = str(results.solver).lower()

    if profile.load_policy == "diagnostic":
        return results

    if status == SolverStatus.ok and tc == TerminationCondition.optimal:
        model.solutions.load_from(results)
        return results

    if profile.load_policy == "allow_acceptable" and "acceptable" in solver_text:
        model.solutions.load_from(results)
        return results

    raise RuntimeError(f"Rejected Ipopt result: status={status}, termination={tc}")
```

---

## 15.15 Installed-build validation for bundles

```python id="h9cgw0"
def validate_bundle_for_installed_ipopt(opt, bundle):
    issues = []

    if bundle.get("linear_solver"):
        solver_name = bundle["linear_solver"]
        try:
            if not opt.has_linear_solver(solver_name):
                issues.append(f"linear_solver unavailable: {solver_name}")
        except Exception as exc:
            issues.append(f"could not probe linear_solver={solver_name}: {type(exc).__name__}: {exc}")

    if bundle.get("sb") == "yes":
        # `sb` is AMPL/executable-interface specific; validate externally if required.
        issues.append("sb=yes should be verified with `ipopt -=` for the installed executable.")

    return issues
```

Ipopt’s option docs warn that availability and defaults for linear-solver options depend on the build, and recommend printing installed option documentation; Pyomo also exposes solver availability/probe mechanisms. ([COIN-OR Documentation][1])

---

## 15.16 `ipopt.opt` equivalents

### Debug derivatives

```text id="dqgmlm"
derivative_test first-order
derivative_test_print_all yes
derivative_test_tol 1e-4
derivative_test_perturbation 1e-8
max_iter 0
print_level 7
```

### Fast quiet solve

```text id="dshiln"
print_level 0
sb yes
```

### Relaxed convergence

```text id="76baw6"
tol 1e-6
acceptable_tol 1e-5
acceptable_iter 10
max_iter 1000
```

### Limited-memory Hessian

```text id="axm4y6"
hessian_approximation limited-memory
limited_memory_update_type bfgs
limited_memory_max_history 10
hessian_approximation_space nonlinear-variables
```

### MUMPS tuning

```text id="mtc3ok"
linear_solver mumps
mumps_pivtol 1e-6
mumps_pivtolmax 0.1
mumps_print_level 0
```

---

## 15.17 Bundle decision table

| Bundle                  | Primary use                         | Mutually suspicious with       | Load solution?              |
| ----------------------- | ----------------------------------- | ------------------------------ | --------------------------- |
| Debug derivatives       | derivative validation               | fast quiet, production         | usually no                  |
| Fast quiet solve        | production / repeated solves        | first-run debug                | yes if termination accepted |
| Relaxed convergence     | screening / engineering accuracy    | strict final                   | maybe, policy-dependent     |
| Limited-memory Hessian  | large model / missing Hessian       | strict exact-Hessian benchmark | yes if termination accepted |
| MUMPS tuning            | portable linear solver baseline     | HSL/Pardiso profile            | yes if termination accepted |
| Strict final            | final report / benchmark            | relaxed convergence            | yes only on strict success  |
| Warm start              | related repeated solves             | least-square primal init       | yes after accepted solve    |
| Feasibility diagnostics | infeasibility/restoration debugging | quiet production               | diagnostic only             |
| NaN/Inf diagnostics     | derivative-domain debugging         | quiet production               | no                          |
| Output audit            | option/log validation               | fast quiet                     | yes if termination accepted |

---

## 15.18 Anti-pattern catalog

```text id="dxp1c7"
BAD:
  enable derivative_test bundle in production.

GOOD:
  run derivative bundle on small representative instances.

BAD:
  use print_level=0 during model bring-up.

GOOD:
  use print_level=5 or output_audit until solve behavior is known.

BAD:
  relaxed convergence profile but claim high-accuracy KKT solution.

GOOD:
  label as relaxed/degraded and audit residuals.

BAD:
  limited-memory Hessian as universal default.

GOOD:
  exact Hessian by default; limited-memory for explicit reason.

BAD:
  MUMPS pivot tuning before checking scaling and derivatives.

GOOD:
  derivative check + scaling audit first, then linear-solver tuning.

BAD:
  combine warm_start_init_point=yes with least_square_init_primal=yes.

GOOD:
  warm start preserves previous primal/dual data; least-square init intentionally overrides starts.

BAD:
  assume `sb=yes` is portable across all interfaces without installed-executable validation.

GOOD:
  validate with `ipopt -=` or omit `sb` if strict portability matters.
```

---

## 15.19 Final checklist

```text id="rdhaaz"
[ ] Give every bundle a name, use case, and load policy.
[ ] Use "yes"/"no" strings for Ipopt string toggles.
[ ] Use debug-derivative bundles only on small models.
[ ] Use fast-quiet only after model/option profile validation.
[ ] Pair relaxed convergence with explicit downstream acceptance policy.
[ ] Use limited-memory Hessian only for cost/memory/missing-Hessian reasons.
[ ] Treat MUMPS as portable conda baseline but still probe availability when robust deployment matters.
[ ] Add print_user_options=yes while developing bundles.
[ ] Archive final bundle dictionaries with solver logs.
[ ] Avoid contradictory bundle merges; last update wins.
[ ] Build a profile registry rather than scattering literal option dicts across code.
[ ] Prefer solve(load_solutions=False) plus explicit load policy for nontrivial bundles.
```

[1]: https://coin-or.github.io/Ipopt/OPTIONS.html "Ipopt: Ipopt Options"

# Ipopt Advanced — Section 16: failure modes and troubleshooting

Style target: dense advanced technical catalog / agent-ready reference. 

## 16.0 Troubleshooting invariant

```text id="9r317t"
Ipopt/Pyomo failure triage =
  environment/executable failure
  + option/deployment failure
  + model construction failure
  + derivative/domain failure
  + scaling/initialization failure
  + infeasibility/restoration failure
  + KKT/linear-solver numerical failure
  + result-loading/termination-policy failure
```

Pyomo solvers are not distributed with Pyomo; solver executables must be installed separately and accessible from the environment where Python is running. For Ipopt specifically, Pyomo’s FAQ says the `ipopt` command must invoke the solver from a terminal before Pyomo can use it through the standard executable workflow. ([Pyomo Documentation][1])

---

## 16.1 Global diagnostic preflight

### One-shot environment + solver probe

```python id="q1ynnd"
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys

import pyomo.environ as pyo


def run(cmd: list[str]) -> str:
    try:
        return subprocess.run(
            cmd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=30,
        ).stdout.strip()
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"


def ipopt_preflight():
    opt = pyo.SolverFactory("ipopt")

    print("python:", sys.executable)
    print("platform:", platform.platform())
    print("cwd:", os.getcwd())
    print("PATH:", os.environ.get("PATH", ""))
    print("which/where ipopt:", shutil.which("ipopt"))
    print("ipopt -v:", run(["ipopt", "-v"]) if shutil.which("ipopt") else "<not found>")

    print("pyomo SolverFactory available:", opt.available(exception_flag=False))
    try:
        print("pyomo executable:", opt.executable())
    except Exception as exc:
        print("pyomo executable error:", type(exc).__name__, exc)

    try:
        print("pyomo ipopt version:", opt.version())
    except Exception as exc:
        print("pyomo version error:", type(exc).__name__, exc)


ipopt_preflight()
```

### Minimal NLP smoke test

```python id="3hed8t"
import pyomo.environ as pyo

m = pyo.ConcreteModel()
m.x = pyo.Var(bounds=(0, None), initialize=2.0)
m.obj = pyo.Objective(expr=(m.x - 1.0) ** 2)

opt = pyo.SolverFactory("ipopt")
assert opt.available(exception_flag=False), "Ipopt unavailable to Pyomo."

res = opt.solve(m, tee=True, load_solutions=False)
print(res.solver.status)
print(res.solver.termination_condition)
```

### Installed option dump

```bash id="tja7hw"
ipopt -v
ipopt -=
ipopt --print-options > ipopt.print-options.txt
```

Ipopt options are named strings with Number, Integer, or String values, and the installed executable’s option documentation should be captured because option availability and linear-solver defaults can depend on the build. ([COIN-OR Documentation][2])

---

## 16.2 Failure: `No executable found for solver 'ipopt'`

### Symptom

```text id="eyyyl6"
pyomo.common.errors.ApplicationError:
  No executable found for solver 'ipopt'
```

### Primary causes

```text id="3xak4m"
ipopt executable not installed
ipopt installed in different conda/micromamba environment
Python interpreter not from intended environment
PATH does not include environment bin directory
Windows environment missing Library\bin on PATH
Jupyter kernel not from environment containing ipopt
SolverFactory called before environment activation
custom executable path wrong
```

Pyomo’s FAQ states that solvers are not installed with Pyomo and must be separately installed; the solver executable must be accessible through a terminal command, e.g. `ipopt -?` for Ipopt. ([Pyomo Documentation][1])

### Diagnostic commands

Linux/macOS:

```bash id="25d1qp"
which ipopt
ipopt -v
python -c "import sys, shutil; print(sys.executable); print(shutil.which('ipopt'))"
```

Windows:

```powershell id="waoquh"
where ipopt
ipopt -v
python -c "import sys, shutil; print(sys.executable); print(shutil.which('ipopt'))"
```

### Fix: conda/micromamba install

```bash id="wcipi7"
micromamba create -n nlp -c conda-forge python=3.11 pyomo ipopt
micromamba activate nlp
```

```bash id="428adc"
conda create -n nlp -c conda-forge python=3.11 pyomo ipopt
conda activate nlp
```

### Fix: explicit executable

```python id="mge62f"
opt = pyo.SolverFactory("ipopt", executable="/absolute/path/to/ipopt")
```

Pyomo solver recipes document `executable=` for selecting a solver binary path when it is not found through `PATH`. ([Pyomo Documentation][3])

### Agent policy

```text id="pz3lyt"
If SolverFactory("ipopt").available(False) is false:
  do not build or solve model.
  emit environment diagnostic.
  recommend installing ipopt in active environment or passing executable=.
```

---

## 16.3 Failure: solver available in shell but not in notebook/kernel

### Symptom

```text id="vksgbc"
Terminal:
  which ipopt -> /.../envs/nlp/bin/ipopt
  ipopt -v -> works

Notebook:
  SolverFactory("ipopt").available(False) -> False
  shutil.which("ipopt") -> None
```

### Root cause

```text id="imfgbq"
Jupyter kernel Python != shell Python.
PATH inside kernel != PATH inside activated shell.
```

### Notebook diagnostic cell

```python id="2u309t"
import os
import shutil
import sys
import pyomo.environ as pyo

print("sys.executable:", sys.executable)
print("PATH:", os.environ.get("PATH", ""))
print("ipopt:", shutil.which("ipopt"))

opt = pyo.SolverFactory("ipopt")
print("available:", opt.available(exception_flag=False))
```

### Fix: register environment kernel

```bash id="trpfix"
micromamba activate nlp
python -m pip install ipykernel
python -m ipykernel install --user --name nlp --display-name "Python (nlp)"
```

### Fix: explicit executable in notebook

```python id="n3drnt"
opt = pyo.SolverFactory("ipopt", executable="/absolute/path/to/ipopt")
```

### Agent policy

```text id="w24qe1"
Notebook failure triage:
  print sys.executable
  print shutil.which("ipopt")
  verify selected notebook kernel
  use explicit executable path only as deterministic override, not as hidden workaround
```

---

## 16.4 Failure: option typo or option unsupported by installed build

### Symptoms

```text id="wkfdy1"
EXIT: Invalid option encountered.
Unknown keyword.
Option value invalid.
Selected linear solver not available.
Solver log ignores intended option.
```

### Root causes

```text id="6rt8ff"
misspelled option key
Python boolean used instead of Ipopt "yes"/"no" string
wrong option value enum
linear_solver not compiled or loadable in installed Ipopt
option only works from ipopt.opt, not command-line channel
old/new Ipopt version mismatch
```

Ipopt’s options are typed as Number, Integer, or String values; string controls include algorithm details such as scaling method, so toggles should be passed as strings like `"yes"` / `"no"` rather than Python booleans. ([COIN-OR Documentation][2])

### Detection

```python id="r9a4we"
opt.options.update({
    "print_user_options": "yes",
    "tol": 1e-8,
})
```

```bash id="xcjq4u"
ipopt --print-options > ipopt.print-options.txt
grep -i "linear_solver" ipopt.print-options.txt
```

### Linear-solver probe

```python id="e7v5dn"
opt = pyo.SolverFactory("ipopt")

for ls in ["mumps", "spral", "ma57", "pardiso", "pardisomkl"]:
    try:
        print(ls, opt.has_linear_solver(ls))
    except Exception as exc:
        print(ls, type(exc).__name__, exc)
```

### Fix patterns

```python id="8cjgsn"
# BAD
opt.options["print_user_options"] = True

# GOOD
opt.options["print_user_options"] = "yes"
```

```python id="z4185n"
# BAD if not verified
opt.options["linear_solver"] = "ma57"

# GOOD
if opt.has_linear_solver("mumps"):
    opt.options["linear_solver"] = "mumps"
```

### Agent policy

```text id="h2ytm2"
For generated option bundles:
  validate spelling against installed option dump.
  probe linear_solver before setting nonbaseline solvers.
  enable print_user_options=yes during profile development.
```

---

## 16.5 Failure: `Restoration_Failed`

### Symptom

```text id="7u7bfe"
EXIT: Restoration Failed!
```

### Meaning

```text id="1wivw6"
Ipopt entered feasibility-restoration mode.
Restoration failed to find a point acceptable to original filter line search.
Common causes:
  infeasible model
  locally infeasible point
  wrong derivatives
  bad scaling
  constraint qualification failure
  singular/dependent constraints
  invalid function evaluations during restoration
```

Ipopt’s output docs state that `Restoration_Failed` means the restoration phase failed to find a feasible point acceptable to the original filter line search, and it can indicate degeneracy, constraint-qualification failure, or incorrect derivative information. ([COIN-OR Documentation][4])

### Immediate diagnostic bundle

```python id="a6dt2i"
opt.options.update({
    "print_level": 7,
    "print_user_options": "yes",
    "inf_pr_output": "original",
    "expect_infeasible_problem": "yes",
    "required_infeasibility_reduction": 0.99,
})
```

### Constraint residual report

```python id="oieodz"
def constraint_residual_report(model, tol=1e-7):
    import pyomo.environ as pyo

    rows = []
    for c in model.component_data_objects(pyo.Constraint, active=True):
        body = pyo.value(c.body, exception=False)
        lb = pyo.value(c.lower, exception=False) if c.lower is not None else None
        ub = pyo.value(c.upper, exception=False) if c.upper is not None else None

        if body is None:
            rows.append((c.name, "EVAL_FAILED", body, lb, ub, None))
            continue

        lviol = 0.0 if lb is None else max(0.0, lb - body)
        uviol = 0.0 if ub is None else max(0.0, body - ub)
        viol = max(lviol, uviol)

        if viol > tol:
            rows.append((c.name, "VIOLATED", body, lb, ub, viol))

    return sorted(rows, key=lambda r: r[-1] if r[-1] is not None else float("inf"), reverse=True)
```

### Fix ladder

```text id="x0br7m"
1. Run first-order derivative checker on small instance.
2. Check constraint residuals at start and returned point.
3. Protect log/sqrt/division domains.
4. Improve variable scaling and constraint scaling.
5. Try alternate starts / continuation.
6. Check equality dependency / rank deficiency.
7. Try exact Hessian if limited-memory was used.
8. Try different verified linear_solver only after model/derivative/scale checks.
```

Ipopt’s derivative checker is finite-difference based, runs before optimization, and is designed to catch derivative mistakes; it can test first- or second-order derivatives. ([COIN-OR Documentation][5])

---

## 16.6 Failure: `Infeasible_Problem_Detected`

### Symptom

```text id="qflzct"
EXIT: Converged to a point of local infeasibility. Problem may be infeasible.
```

### Meaning

```text id="080ghv"
Ipopt converged to a minimizer of constraint violation in restoration mode.
The model may be infeasible.
The returned point may be only locally infeasible.
This is not always a mathematical proof of global infeasibility.
```

Ipopt’s output docs explain that `Infeasible_Problem_Detected` means restoration converged to a point that minimizes constraint violation but does not satisfy original feasibility; Ipopt explicitly says the problem may be infeasible and the returned point can help identify problematic constraints. ([COIN-OR Documentation][4])

### Debug workflow

```text id="j1uuz2"
[ ] evaluate all constraint residuals at returned point
[ ] inspect largest violated constraints
[ ] verify signs and units
[ ] check impossible bounds
[ ] relax suspected constraints one class at a time
[ ] solve from alternate starts
[ ] solve feasibility objective / slack-augmented model
```

### Feasibility-slack model pattern

```python id="p8lvnv"
m.slack = pyo.Var(m.CONS, domain=pyo.NonNegativeReals, initialize=0.0)

# Example for a lower-bound-style constraint body >= lb:
m.relaxed_c = pyo.Constraint(
    m.CONS,
    rule=lambda m, i: m.body[i] + m.slack[i] >= m.lb[i],
)

m.feas_obj = pyo.Objective(expr=sum(m.slack[i] for i in m.CONS))
```

### Agent policy

```text id="07peu3"
Do not label one Ipopt local-infeasibility result as global infeasibility.
Report:
  local infeasibility detected,
  largest residuals,
  start used,
  options used,
  and whether alternate starts/relaxations were tested.
```

---

## 16.7 Failure: `Maximum_Iterations_Exceeded`

### Symptom

```text id="4z0t4y"
EXIT: Maximum Number of Iterations Exceeded.
```

Ipopt reports `Maximum_Iterations_Exceeded` when the iteration limit is exceeded; `max_iter` controls this limit. ([COIN-OR Documentation][4])

### Triage by trend

```text id="y7nxyq"
if inf_pr and inf_du decreasing steadily:
  raise max_iter or warm-start/continue

if inf_pr stuck:
  check feasibility, scaling, starts

if inf_du stuck:
  check scaling, derivatives, Hessian strategy, linear solver

if restoration appears repeatedly:
  treat as feasibility/restoration failure

if many line-search steps:
  check nonsmoothness, bad derivatives, domain errors
```

### Fix: allow more iterations

```python id="vzwwli"
opt.options["max_iter"] = 5000
```

### Fix: relaxed convergence

```python id="rfyrdl"
opt.options.update({
    "tol": 1e-6,
    "acceptable_tol": 1e-5,
    "acceptable_iter": 10,
    "max_iter": 2000,
})
```

### Agent policy

```text id="h4h8cg"
Max iteration is incomplete solve, not infeasibility.
Only increase max_iter if iteration log shows meaningful progress.
```

---

## 16.8 Failure: `Maximum_WallTime_Exceeded` / `Maximum_CpuTime_Exceeded`

### Symptom

```text id="4rltzi"
EXIT: Maximum wallclock time exceeded.
EXIT: Maximum CPU time exceeded.
```

Ipopt has `max_wall_time` and `max_cpu_time` options; the output docs list these exits as time-limit terminations. ([COIN-OR Documentation][4])

### Fix options

```python id="7518gv"
opt.options.update({
    "max_wall_time": 600.0,
    "max_cpu_time": 600.0,
})
```

### Agent policy

```text id="iysdlz"
Time limit is operational interruption.
Do not mark result optimal unless termination confirms accepted convergence.
Use load_solutions=False and explicit candidate policy.
```

---

## 16.9 Failure: `Search_Direction_Becomes_Too_Small`

### Symptom

```text id="6b38s4"
EXIT: Search Direction is becoming Too Small.
```

### Meaning

```text id="yvsvcv"
Ipopt cannot make meaningful steps.
May indicate:
  reached best attainable numerical accuracy
  badly scaled model
  degenerate KKT system
  nonsmooth point
  active-set degeneracy
  singular Jacobian
  poor Hessian / linear solver behavior
```

Ipopt’s output docs describe `Search_Direction_Becomes_Too_Small` as a state where the search direction becomes very small and Ipopt cannot make further progress, while the current point may still be a useful approximate solution. ([COIN-OR Documentation][4])

### Debug actions

```text id="chhxq1"
[ ] inspect final inf_pr, inf_du, complementarity
[ ] run residual audits
[ ] check scaling
[ ] run derivative checker
[ ] inspect lg(rg) regularization in iteration log
[ ] try exact Hessian if limited-memory used
[ ] try alternate starts
[ ] test tighter/looser tolerances
```

### Agent policy

```text id="93by4y"
If residuals are small:
  treat as possible near-solution with degraded termination, subject to audit.

If residuals are large:
  treat as numerical/model failure.
```

---

## 16.10 Failure: `Error_In_Step_Computation`

### Symptom

```text id="xkd8h3"
EXIT: Error in step computation!
```

### Meaning

```text id="l7ergh"
Ipopt could not compute a step and current iterate is not acceptable.
Common causes:
  invalid Hessian values
  NaN/Inf in derivative matrix
  singular/ill-conditioned KKT system
  linear solver failure
  severe degeneracy
  bad scaling
  wrong derivatives
```

Ipopt’s output docs say `Error_In_Step_Computation` is printed when Ipopt cannot compute a step toward a new iterate and the current iterate is not acceptable; the docs specifically mention that invalid Hessian values such as `NaN` or `Inf` can cause this, and recommend `check_derivatives_for_naninf` for this case. ([COIN-OR Documentation][4])

### Diagnostic options

```python id="mvk6hn"
opt.options.update({
    "check_derivatives_for_naninf": "yes",
    "derivative_test": "first-order",
    "derivative_test_print_all": "yes",
    "max_iter": 0,
    "print_level": 7,
})
```

Ipopt’s option docs state that `check_derivatives_for_naninf=yes` makes Ipopt error when invalid numbers occur in the Jacobian or Hessian, and derivative checking can be enabled through `derivative_test`. ([COIN-OR Documentation][2])

### Fix ladder

```text id="91r4wz"
1. Check objective/constraints evaluable at start.
2. Check derivatives for NaN/Inf.
3. Run derivative checker.
4. Protect domains.
5. Improve scaling.
6. Remove nonsmooth operators.
7. Try hessian_approximation=limited-memory if exact Hessian suspect.
8. Try different verified linear solver after derivative/scale checks.
```

---

## 16.11 Failure: NaN/Inf in objective or constraints

### Symptoms

```text id="txtk8j"
Invalid number in NLP function or derivative detected.
Evaluation error during backtracking.
NaN in objective.
NaN/Inf in constraint body.
EXIT: Invalid number in NLP function or derivative detected.
```

### Common model causes

```text id="kcaccu"
log(x) with x <= 0
sqrt(x) with x < 0
1 / x with x near 0
exp(x) overflow
power(x, fractional) with x < 0
external function returns NaN
initial value missing / invalid
finite-difference perturbation crosses invalid domain
```

### Pyomo evaluator check

```python id="8obyw6"
def eval_model_at_start(model):
    import math
    import pyomo.environ as pyo

    bad = []

    for obj in model.component_data_objects(pyo.Objective, active=True):
        val = pyo.value(obj.expr, exception=False)
        if val is None or not math.isfinite(float(val)):
            bad.append(("objective", obj.name, val))

    for c in model.component_data_objects(pyo.Constraint, active=True):
        val = pyo.value(c.body, exception=False)
        if val is None:
            bad.append(("constraint", c.name, None))
        else:
            try:
                if not math.isfinite(float(val)):
                    bad.append(("constraint", c.name, val))
            except Exception:
                bad.append(("constraint", c.name, val))

    return bad
```

### Domain-protection pattern

```python id="6lsoya"
eps = 1e-8

m.x_log = pyo.Var(bounds=(eps, None), initialize=1.0)
m.x_sqrt = pyo.Var(bounds=(eps, None), initialize=1.0)
m.x_den = pyo.Var(bounds=(eps, None), initialize=1.0)

m.c = pyo.Constraint(expr=pyo.log(m.x_log) + pyo.sqrt(m.x_sqrt) + 1 / m.x_den <= 10)
```

### Agent policy

```text id="ctlb0e"
Do not solve until all active objective and constraint bodies evaluate finite at the initial point.
```

---

## 16.12 Failure: nonsmooth expressions: `abs`, `max`, `min`, conditionals`

### Bad patterns

```python id="gf3cpo"
m.obj = pyo.Objective(expr=abs(m.x))
m.c = pyo.Constraint(expr=max(m.x, m.y) <= 10)
m.d = pyo.Constraint(expr=min(m.x, m.y) >= 1)
```

### Python conditional pitfall

```python id="u9vbhl"
# BAD: Pyomo expression in Python if condition.
if m.x >= 0:
    m.c = pyo.Constraint(expr=m.y >= 1)
```

Pyomo expression docs explain that comparisons involving Pyomo variables produce symbolic expressions, not evaluated Python booleans; using `value(...)` in Python conditionals evaluates the current value and freezes that construction-time branch, which is usually not valid as an optimization conditional. ([Pyomo Documentation][6])

### Smooth approximations

```python id="i63cxm"
eps = 1e-6

smooth_abs = pyo.sqrt(m.x**2 + eps)

smooth_max = 0.5 * (
    m.x + m.y + pyo.sqrt((m.x - m.y)**2 + eps)
)

smooth_min = 0.5 * (
    m.x + m.y - pyo.sqrt((m.x - m.y)**2 + eps)
)
```

### Exact convex epigraph pattern for `abs`

```python id="k49eww"
m.t = pyo.Var(domain=pyo.NonNegativeReals, initialize=1.0)
m.abs_pos = pyo.Constraint(expr=m.t >= m.x)
m.abs_neg = pyo.Constraint(expr=m.t >= -m.x)
m.obj = pyo.Objective(expr=m.t)
```

### Agent policy

```text id="ayfb5c"
Ipopt requires smooth NLP algebra.
If construct is logical/discrete/nonsmooth:
  reformulate
  smooth approximate
  use GDP/MIP/MINLP solver
  or fix discrete choices before Ipopt.
```

---

## 16.13 Failure: bad scaling

### Symptoms

```text id="zmqoaw"
large inf_du persists
lg(rg) frequent/large
many line-search steps
restoration enters repeatedly
Search_Direction_Becomes_Too_Small
acceptable but not desired convergence
MUMPS/linear solver instability
```

### Scaling diagnostic

```python id="e67xsj"
def variable_scale_report(model):
    import pyomo.environ as pyo

    rows = []
    for v in model.component_data_objects(pyo.Var, active=True):
        val = pyo.value(v, exception=False)
        lb = pyo.value(v.lb, exception=False) if v.lb is not None else None
        ub = pyo.value(v.ub, exception=False) if v.ub is not None else None
        rows.append((v.name, val, lb, ub))
    return rows
```

### Solver-side scaling options

```python id="wvgy4j"
opt.options.update({
    "nlp_scaling_method": "gradient-based",
    "nlp_scaling_max_gradient": 100.0,
})
```

```python id="dm158t"
opt.options["nlp_scaling_method"] = "none"
```

Ipopt’s option docs list `nlp_scaling_method` with values such as `none`, `gradient-based`, `user-scaling`, and `equilibration-based`; `nlp_scaling_max_gradient` controls the target gradient scale for gradient-based scaling. ([COIN-OR Documentation][2])

### Best fix: model-layer nondimensionalization

```python id="9l9hpt"
P_ref = 1e6
F_ref = 1e-4

m.P_hat = pyo.Var(bounds=(0.1, 10), initialize=1.0)
m.F_hat = pyo.Var(bounds=(0.01, 100), initialize=1.0)

P = P_ref * m.P_hat
F = F_ref * m.F_hat
```

### Agent policy

```text id="73jn0a"
Fix scaling before tuning:
  max_iter
  pivot tolerances
  acceptable tolerances
  hessian approximation
  restoration controls
```

---

## 16.14 Failure: missing or poor variable initial values

### Symptoms

```text id="9gopdc"
constraint body not evaluable at start
invalid number at iteration 0
immediate restoration
slow convergence
wrong local basin in nonconvex model
```

### Detect missing starts

```python id="rc5zlp"
missing = [
    v.name
    for v in model.component_data_objects(pyo.Var, active=True)
    if not v.fixed and v.value is None
]
print(missing)
```

### Initialize unset variables inside bounds

```python id="lmna1d"
def initialize_unset_variables(model, default=1.0, frac=0.1):
    for v in model.component_data_objects(pyo.Var, active=True):
        if v.fixed or v.value is not None:
            continue

        lb = pyo.value(v.lb, exception=False) if v.lb is not None else None
        ub = pyo.value(v.ub, exception=False) if v.ub is not None else None

        if lb is not None and ub is not None:
            val = lb + frac * (ub - lb)
        elif lb is not None:
            val = lb + frac * max(1.0, abs(lb))
        elif ub is not None:
            val = ub - frac * max(1.0, abs(ub))
        else:
            val = default

        v.set_value(val, skip_validation=True)
```

### Least-square initialization option

```python id="1bdn0u"
opt.options["least_square_init_primal"] = "yes"
```

Ipopt supports `least_square_init_primal`, which makes Ipopt ignore the user primal start and compute a least-square primal/slack initialization; this is useful when user starts are unknown or low quality, but it should not be used when a warm start should be respected. ([COIN-OR Documentation][2])

### Agent policy

```text id="6dk2zw"
Initialize every nonlinear variable.
Use physically plausible starts for nonconvex models.
Protect function domains before invoking Ipopt.
```

---

## 16.15 Failure: singular Jacobian or dependent equality constraints

### Symptoms

```text id="yxgu2v"
Restoration_Failed
Error_In_Step_Computation
large lg(rg)
linear solver singularity warnings
Search_Direction_Becomes_Too_Small
Not_Enough_Degrees_Of_Freedom
```

Ipopt’s output docs connect restoration failure to degeneracy and constraint qualification failure, and `Not_Enough_Degrees_Of_Freedom` to too few degrees of freedom after fixed variables are processed. ([COIN-OR Documentation][4])

### Structural checks

```python id="hiiivo"
def degrees_of_freedom_rough(model):
    n_free = sum(
        1
        for v in model.component_data_objects(pyo.Var, active=True)
        if not v.fixed
    )
    n_eq = sum(
        1
        for c in model.component_data_objects(pyo.Constraint, active=True)
        if c.equality
    )
    return n_free - n_eq, n_free, n_eq
```

### Ipopt dependency detector

```python id="454ycr"
opt.options["dependency_detector"] = "mumps"
```

Ipopt has `dependency_detector` options for experimental detection of linearly dependent equality constraints using linear solvers such as MUMPS, WSMP, or MA28, but the option docs warn that this feature does not work well and is not active by default. ([COIN-OR Documentation][2])

### Fix ladder

```text id="hm8k5s"
[ ] remove duplicate equality constraints
[ ] avoid fixing variables and also enforcing same value by equality
[ ] scale equality rows
[ ] relax or remove redundant balances
[ ] check active constraints at solution
[ ] use make_constraint fixed-variable treatment only intentionally
[ ] test smaller subsystem
```

---

## 16.16 Failure: linear-solver memory failures

### Symptoms

```text id="nyz52o"
EXIT: Not enough memory.
MUMPS memory allocation failure.
factorization failure.
process killed by OS / scheduler.
```

Ipopt’s output docs list `Insufficient_Memory` as a failure mode, and Ipopt’s option docs include MUMPS memory controls such as `mumps_mem_percent`. ([COIN-OR Documentation][4])

### First controls

```python id="izpz1f"
opt.options.update({
    "linear_solver": "mumps",
    "mumps_mem_percent": 2000,
    "mumps_print_level": 2,
})
```

### Sparse-model audit

```text id="qbkf1f"
[ ] eliminate dense all-to-all sums
[ ] use sparse index sets for nonzero coefficients
[ ] remove redundant constraints
[ ] reduce expression duplication
[ ] benchmark limited-memory Hessian if Hessian factorization burden is high
[ ] try verified alternative linear solver
```

### Dense sum anti-pattern

```python id="d99lh0"
# BAD: every row depends on every variable.
m.c = pyo.Constraint(
    m.I,
    rule=lambda m, i: sum(m.x[j] for j in m.J) >= demand[i],
)
```

### Sparse adjacency pattern

```python id="0senk2"
m.c = pyo.Constraint(
    m.I,
    rule=lambda m, i: sum(m.x[j] for j in neighbors[i]) >= demand[i],
)
```

---

## 16.17 Failure: Windows path and executable issues

### Symptoms

```text id="jkxni2"
'ipopt' is not recognized as an internal or external command
No executable found for solver 'ipopt'
path with spaces fails
wrong Python environment selected
SolverFactory sees shell solver but not notebook solver
```

### Diagnostic commands

```powershell id="buzfc2"
where ipopt
ipopt -v
python -c "import sys, shutil; print(sys.executable); print(shutil.which('ipopt'))"
```

### Explicit raw-string path

```python id="k5x4ll"
opt = pyo.SolverFactory(
    "ipopt",
    executable=r"C:\Users\USER\miniforge3\envs\nlp\Library\bin\ipopt.exe",
)
```

### `pathlib` path

```python id="aep4x6"
from pathlib import Path

ipopt_exe = Path.home() / "miniforge3" / "envs" / "nlp" / "Library" / "bin" / "ipopt.exe"
opt = pyo.SolverFactory("ipopt", executable=str(ipopt_exe))
```

### Agent policy

```text id="3qde43"
On Windows:
  use conda/micromamba environment
  confirm `where ipopt`
  prefer raw strings or pathlib for paths
  do not rely on shell activation inside IDE/notebook
  pass executable= for deterministic deployment
```

---

## 16.18 Failure: model can be constructed but not solved due to Pyomo expression logic

### Symptom

```text id="xlzubg"
PyomoException: Cannot convert non-constant Pyomo expression to bool
```

### Cause

```python id="ds4vh3"
if model.x >= 0:
    ...
```

Pyomo expression docs explain that `model.d >= 2` creates an expression, not an evaluated Python truth value; if conditional model construction depends on current numeric values, `value(model.d)` is needed, but that evaluates the current value and fixes the branch at construction time rather than creating optimization logic. ([Pyomo Documentation][6])

### Correct pattern: data-dependent branch

```python id="d8zcvw"
if data_flag:
    model.c = pyo.Constraint(expr=model.x >= 0)
else:
    model.c = pyo.Constraint(expr=model.x <= 0)
```

### Correct pattern: optimization-dependent logic

```text id="whk0ig"
Use:
  GDP reformulation
  binary variables + MIP/MINLP solver
  smooth relaxation
  complementarity/MPEC reformulation where appropriate
```

---

## 16.19 Unified troubleshooting decision tree

```text id="afddgh"
START

1. Solver unavailable?
   -> check sys.executable, PATH, shutil.which("ipopt"), explicit executable=

2. Solver starts but option error?
   -> print_user_options=yes, ipopt --print-options, validate linear_solver

3. Evaluation error / NaN?
   -> evaluate objective/constraints at start, protect domains, check derivatives

4. Derivative/numerical error?
   -> derivative_test first-order, check_derivatives_for_naninf, exact vs limited-memory

5. Restoration / infeasibility?
   -> residual report, alternate starts, slack feasibility model, scaling, signs

6. Iteration/time limit?
   -> inspect convergence trend, not just exit code

7. Tiny step / step computation error?
   -> scaling, degeneracy, Hessian, Jacobian, linear solver

8. Memory / factorization failure?
   -> sparsity audit, MUMPS memory, alternative linear solver, decomposition

9. Nonconvex inconsistent solution?
   -> multi-start, continuation, local-optimum caveat
```

---

## 16.20 Failure-to-action matrix

| Failure                     | Do first                                  | Do second                           | Do not do first              |
| --------------------------- | ----------------------------------------- | ----------------------------------- | ---------------------------- |
| No executable               | verify Python/env/PATH                    | install ipopt or pass `executable=` | tune model                   |
| Shell works, notebook fails | print `sys.executable` and `shutil.which` | register kernel                     | reinstall blindly            |
| Option typo                 | `print_user_options=yes`                  | check option dump                   | assume option used           |
| Unsupported linear solver   | `has_linear_solver(...)`                  | use MUMPS or deploy library         | set HSL/Pardiso blindly      |
| Restoration failed          | residual + derivative check               | scaling/alternate starts            | only raise `max_iter`        |
| Local infeasibility         | residual report                           | slack model/alternate starts        | claim global infeasible      |
| Max iterations              | inspect log trend                         | raise/relax only if improving       | claim infeasible             |
| Tiny step                   | residual audit                            | scaling/degeneracy check            | assume optimal               |
| Step computation error      | NaN/Inf derivative check                  | derivative checker                  | switch linear solver first   |
| NaN objective               | evaluate start                            | protect domains                     | reduce tolerance             |
| Nonsmooth model             | reformulate/smooth                        | choose different solver             | hide with limited-memory     |
| Bad scaling                 | nondimensionalize                         | user/gradient scaling               | tune pivots first            |
| Poor starts                 | initialize interior                       | continuation                        | least-square blindly         |
| Singular Jacobian           | DOF/rank reasoning                        | remove redundancy                   | increase tolerances only     |
| Linear memory               | sparsity audit                            | MUMPS memory/alternative solver     | add RAM without model review |
| Windows path                | `where ipopt`                             | raw `executable=` path              | hard-code POSIX path         |

---

## 16.21 Production-safe solve wrapper

```python id="3js8kz"
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import sys

import pyomo.environ as pyo
from pyomo.opt import SolverStatus, TerminationCondition


@dataclass(frozen=True)
class IpoptTroubleshootingContext:
    python: str
    ipopt_path: str | None
    status: str | None
    termination_condition: str | None
    log_path: str


def solve_ipopt_strict_with_context(
    model,
    *,
    options: dict[str, object] | None = None,
    executable: str | None = None,
    log_path: str = "ipopt.solve.log",
    tee: bool = True,
):
    kwargs = {}
    if executable is not None:
        kwargs["executable"] = executable

    opt = pyo.SolverFactory("ipopt", **kwargs)

    if not opt.available(exception_flag=False):
        raise RuntimeError(
            "Ipopt unavailable. "
            f"python={sys.executable}, "
            f"shutil.which('ipopt')={shutil.which('ipopt')}, "
            f"executable={executable}"
        )

    opt.options.update({
        "print_user_options": "yes",
        "inf_pr_output": "original",
        "print_level": 5,
    })
    if options:
        opt.options.update(options)

    results = opt.solve(
        model,
        tee=tee,
        logfile=log_path,
        load_solutions=False,
    )

    ctx = IpoptTroubleshootingContext(
        python=sys.executable,
        ipopt_path=shutil.which("ipopt"),
        status=str(results.solver.status),
        termination_condition=str(results.solver.termination_condition),
        log_path=str(Path(log_path).absolute()),
    )

    if (
        results.solver.status == SolverStatus.ok
        and results.solver.termination_condition == TerminationCondition.optimal
    ):
        model.solutions.load_from(results)
        return results, ctx

    raise RuntimeError(f"Ipopt solve rejected: {ctx}")
```

---

## 16.22 Agent anti-pattern catalog

```text id="qj8kaq"
BAD:
  catch all Ipopt failures and retry with max_iter=100000.

GOOD:
  classify failure by solver exit, residuals, and log tags.

BAD:
  treat Infeasible_Problem_Detected as proof of infeasibility.

GOOD:
  report local infeasibility and run residual/alternate-start checks.

BAD:
  switch linear solvers before checking derivatives and scaling.

GOOD:
  derivative_test + scaling audit first.

BAD:
  use limited-memory Hessian to handle nonsmooth abs/max/min.

GOOD:
  reformulate nonsmooth expressions.

BAD:
  rely on shell `which ipopt` inside notebook.

GOOD:
  inspect `sys.executable` and `shutil.which("ipopt")` inside the kernel.

BAD:
  load solution after failed solve.

GOOD:
  use load_solutions=False and manual policy.

BAD:
  hide option typos by suppressing output.

GOOD:
  print_user_options=yes during profile development.
```

---

## 16.23 Final troubleshooting checklist

```text id="g2v7ot"
[ ] Confirm active Python executable.
[ ] Confirm ipopt executable with shutil.which / which / where.
[ ] Confirm SolverFactory("ipopt").available(False).
[ ] Confirm minimal NLP smoke test solves.
[ ] Dump installed options with ipopt --print-options.
[ ] Enable print_user_options=yes for option debugging.
[ ] Use load_solutions=False for nontrivial failure-prone solves.
[ ] Evaluate objective and constraints at initial point.
[ ] Initialize all nonlinear variables.
[ ] Protect log/sqrt/division domains.
[ ] Remove or reformulate abs/max/min/conditionals.
[ ] Run first-order derivative checker on small instance.
[ ] Run second-order checker only after first-order passes.
[ ] Audit constraint residuals on infeasible/restoration exits.
[ ] Scale variables and constraints before deep Ipopt tuning.
[ ] Check degrees of freedom and redundant equalities.
[ ] Probe linear solver availability before setting linear_solver.
[ ] Address linear solver memory through sparsity, MUMPS memory options, or verified alternatives.
[ ] For Windows/notebooks, use explicit executable= when PATH is unreliable.
[ ] Archive log, options, environment, and model fingerprint for reproducibility.
```

[1]: https://pyomo.readthedocs.io/en/6.8.0/model_debugging/FAQ.html?utm_source=chatgpt.com "FAQ — Pyomo 6.8.0 documentation"
[2]: https://coin-or.github.io/Ipopt/OPTIONS.html?utm_source=chatgpt.com "Ipopt Options"
[3]: https://pyomo.readthedocs.io/en/latest/howto/solver_recipes.html?utm_source=chatgpt.com "Solver Recipes — Pyomo 6.10.1.dev0 documentation"
[4]: https://coin-or.github.io/Ipopt/OUTPUT.html?utm_source=chatgpt.com "Ipopt Output"
[5]: https://coin-or.github.io/Ipopt/SPECIALS.html?utm_source=chatgpt.com "Ipopt: Special Features"
[6]: https://pyomo.readthedocs.io/en/6.4.4/pyomo_modeling_components/Expressions.html?utm_source=chatgpt.com "Expressions — Pyomo 6.4.4 documentation"

# Ipopt Advanced — Section 17: best practices for Pyomo + Ipopt model quality

Style target: dense advanced technical catalog / agent-ready reference. 

## 17.0 Quality invariant

```text id="u2dfur"
High-quality Pyomo + Ipopt model =
  smooth continuous NLP
  meaningful bounded variables
  finite/evaluable starting point
  scaled variables/objective/constraints
  one active objective
  structurally nonredundant constraints
  sparse derivative structure
  exact derivatives unless explicitly too costly
  solver logs inspected before option tuning
  reproducible option/environment artifacts
```

Ipopt’s target problem is a continuous nonlinear program with variable bounds, constraint bounds, and twice continuously differentiable objective and constraint functions; it implements an interior-point line-search filter method that aims for a local solution, so model smoothness, scaling, initialization, and local-solve interpretation are core correctness conditions rather than cosmetic solver preferences. ([coin-or.github.io][1])

---

## 17.1 Initialize variables near feasible, meaningful values

### Construction-time initialization

```python id="uw0ihx"
import pyomo.environ as pyo

m = pyo.ConcreteModel()

m.x = pyo.Var(bounds=(0.0, 10.0), initialize=1.0)
m.y = pyo.Var(bounds=(1e-8, None), initialize=1.0)
```

Pyomo `Var` supports `bounds`, `domain`, and `initialize`; default variable domain is real-valued and bounds default to `(None, None)`, so Ipopt-facing nonlinear variables should be explicitly initialized wherever function evaluation or local convergence depends on a meaningful start. ([pyomo.readthedocs.io][2])

### Post-construction initialization

```python id="j283n1"
m.x.set_value(2.0)
m.y.value = 3.0
```

### Indexed initialization

```python id="5pu8t2"
m.I = pyo.Set(initialize=["A", "B", "C"])

x0 = {"A": 1.0, "B": 2.0, "C": 3.0}

m.x = pyo.Var(
    m.I,
    bounds=(0.0, None),
    initialize=lambda m, i: x0[i],
)
```

### Interior-start helper

```python id="h4w0zk"
def interior_start(lb, ub, *, default=1.0, frac=0.1, eps=1e-8):
    if lb is not None and ub is not None:
        if ub <= lb:
            return lb
        return lb + frac * (ub - lb)
    if lb is not None:
        return lb + max(eps, frac * max(1.0, abs(lb)))
    if ub is not None:
        return ub - max(eps, frac * max(1.0, abs(ub)))
    return default


def initialize_missing_values(model):
    for v in model.component_data_objects(pyo.Var, active=True):
        if v.fixed or v.value is not None:
            continue
        lb = pyo.value(v.lb, exception=False) if v.lb is not None else None
        ub = pyo.value(v.ub, exception=False) if v.ub is not None else None
        v.set_value(interior_start(lb, ub), skip_validation=True)
```

### Domain-protected starts

```python id="bynqqg"
eps = 1e-8

m.log_arg = pyo.Var(bounds=(eps, None), initialize=1.0)
m.sqrt_arg = pyo.Var(bounds=(eps, None), initialize=1.0)
m.denominator = pyo.Var(bounds=(eps, None), initialize=1.0)

m.c = pyo.Constraint(
    expr=pyo.log(m.log_arg) + pyo.sqrt(m.sqrt_arg) + 1 / m.denominator <= 10.0
)
```

### Agent rules

```text id="usyamx"
[ ] initialize every variable appearing in nonlinear expressions.
[ ] initialize log/sqrt/division arguments strictly inside domain.
[ ] initialize nonconvex models from multiple plausible starts.
[ ] avoid exact bound starts unless intended.
[ ] preserve previous Var.value values in parametric repeated solves.
[ ] never rely on Ipopt to repair undefined initial expressions.
```

---

## 17.2 Scale objectives and constraints to roughly similar magnitudes

### Model-layer nondimensionalization: preferred

```python id="iqqv7f"
P_ref = 1e6      # Pa
F_ref = 1e-4     # mol/s
C_ref = 1e6      # cost units

m.P_hat = pyo.Var(bounds=(0.1, 10.0), initialize=1.0)
m.F_hat = pyo.Var(bounds=(0.01, 100.0), initialize=1.0)
m.C_hat = pyo.Var(bounds=(0.0, 1000.0), initialize=1.0)

P = P_ref * m.P_hat
F = F_ref * m.F_hat
C = C_ref * m.C_hat

m.obj = pyo.Objective(expr=m.C_hat + (m.F_hat - 1.0) ** 2)
```

### Ipopt automatic scaling baseline

```python id="wk91k6"
opt.options.update({
    "nlp_scaling_method": "gradient-based",
    "nlp_scaling_max_gradient": 100.0,
})
```

Ipopt’s default NLP scaling method is `gradient-based`, which scales the problem so the maximum gradient at the starting point is the `nlp_scaling_max_gradient` target; `none`, `user-scaling`, and `equilibration-based` are also available. ([coin-or.github.io][3])

### Pyomo user scaling suffix

```python id="hgne64"
m.scaling_factor = pyo.Suffix(direction=pyo.Suffix.EXPORT)

m.scaling_factor[m.obj] = 1e-3
m.scaling_factor[m.mass_balance] = 100.0
m.scaling_factor[m.x] = 0.1

opt.options["nlp_scaling_method"] = "user-scaling"
```

The Pyomo NL writer can emit the model in scaled space using the `scaling_factor` suffix when scaling is enabled, and `symbolic_solver_labels=True` writes `.row` and `.col` files for debugging row/column mappings. ([pyomo.readthedocs.io][4])

### Disable scaling only intentionally

```python id="wmn3qw"
opt.options["nlp_scaling_method"] = "none"
```

### Agent rules

```text id="h8yzmv"
[ ] scale variables to O(1)–O(1e3) where possible.
[ ] scale active constraint bodies to comparable magnitudes.
[ ] scale objective terms before adding them.
[ ] use model-layer nondimensionalization before solver-layer patches.
[ ] keep nlp_scaling_method=gradient-based as a safe default for raw models.
[ ] disable scaling only for already nondimensionalized models or raw-residual diagnostics.
[ ] after acceptable/degraded termination, audit unscaled residuals manually.
```

---

## 17.3 Use bounds wherever physically meaningful

### Explicit finite bounds

```python id="zww5zs"
m.temperature = pyo.Var(bounds=(250.0, 1000.0), initialize=500.0)
m.flow = pyo.Var(bounds=(0.0, 100.0), initialize=10.0)
m.pressure_hat = pyo.Var(bounds=(0.1, 10.0), initialize=1.0)
```

### Nonnegative domain

```python id="0nsbub"
m.flow = pyo.Var(domain=pyo.NonNegativeReals, initialize=1.0)
```

### Avoid fake infinities

```python id="mqpb2b"
# BAD
m.x = pyo.Var(bounds=(0.0, 1e20), initialize=1.0)

# GOOD if truly unbounded above
m.x = pyo.Var(bounds=(0.0, None), initialize=1.0)

# GOOD if physically bounded
m.x = pyo.Var(bounds=(0.0, 1000.0), initialize=1.0)
```

### Bound audit

```python id="4c1x40"
def bound_quality_report(model, huge=1e19):
    rows = []
    for v in model.component_data_objects(pyo.Var, active=True):
        lb = pyo.value(v.lb, exception=False) if v.lb is not None else None
        ub = pyo.value(v.ub, exception=False) if v.ub is not None else None
        flags = []
        if lb is None and ub is None and not v.fixed:
            flags.append("FREE")
        if lb is not None and abs(lb) >= huge:
            flags.append("HUGE_LB")
        if ub is not None and abs(ub) >= huge:
            flags.append("HUGE_UB")
        if lb is not None and ub is not None and lb > ub:
            flags.append("INCONSISTENT")
        if flags:
            rows.append((v.name, lb, ub, flags))
    return rows
```

### Agent rules

```text id="8cl5f5"
[ ] bounds improve numerical stability and domain safety.
[ ] bounds encode physical feasibility and protect functions.
[ ] unbounded variables must be deliberate and documented.
[ ] avoid 1e20 / 1e30 fake infinities.
[ ] use None for true infinity and finite physical limits for real limits.
[ ] check fixed variables and equal lower/upper bounds intentionally.
```

---

## 17.4 Avoid nonsmooth functions; reformulate or transform

### Bad: nonsmooth functions in active NLP expressions

```python id="m291mo"
m.obj = pyo.Objective(expr=abs(m.x))
m.c1 = pyo.Constraint(expr=max(m.x, m.y) <= 10.0)
m.c2 = pyo.Constraint(expr=min(m.x, m.y) >= 1.0)
```

Ipopt requires objective and constraint functions to be twice continuously differentiable; Pyomo can build nonlinear expressions and call nonlinear solvers such as Ipopt, but expression validity for a smooth NLP is a modeling responsibility, not merely a Pyomo syntax question. ([coin-or.github.io][1])

### Smooth approximation: `abs`

```python id="ck138j"
eps = 1e-6
smooth_abs_x = pyo.sqrt(m.x**2 + eps)
```

### Exact convex epigraph: `abs` in minimization

```python id="01xex4"
m.t = pyo.Var(domain=pyo.NonNegativeReals, initialize=1.0)
m.abs_pos = pyo.Constraint(expr=m.t >= m.x)
m.abs_neg = pyo.Constraint(expr=m.t >= -m.x)
m.obj = pyo.Objective(expr=m.t)
```

### Smooth approximation: `max` and `min`

```python id="fwd96v"
eps = 1e-6

m.smooth_max_xy = pyo.Expression(
    expr=0.5 * (m.x + m.y + pyo.sqrt((m.x - m.y)**2 + eps))
)

m.smooth_min_xy = pyo.Expression(
    expr=0.5 * (m.x + m.y - pyo.sqrt((m.x - m.y)**2 + eps))
)
```

### Conditional logic: data-dependent only

```python id="ciqamq"
# OK: data-dependent branch
if data["use_limit"]:
    m.limit = pyo.Constraint(expr=m.x <= data["limit"])
else:
    m.limit = pyo.Constraint.Skip
```

### Bad: optimization-variable-dependent Python branch

```python id="bk9chx"
# BAD
if m.x >= 0:
    m.c = pyo.Constraint(expr=m.y >= 1.0)
```

Pyomo expressions involving model elements are symbolic expressions, not Python truth values; the docs explicitly warn that `model.d >= 2` creates an expression rather than an evaluated boolean and that `value(model.d)` evaluates the current value rather than creating optimization logic. ([pyomo.readthedocs.io][5])

### Piecewise/GDP routing

```python id="siy0ri"
# Piecewise models often introduce SOS or binary formulations.
m.pw = pyo.Piecewise(
    m.y,
    m.x,
    pw_pts=[0, 1, 2, 3],
    f_rule=[0, 1, 4, 9],
    pw_constr_type="EQ",
    pw_repn="SOS2",
)
```

Pyomo’s `Piecewise` component supports representations such as SOS2 and Big-M binary formulations; these are usually not smooth NLPs and may require a MIP/MINLP solver or a smooth approximation before Ipopt is appropriate. ([pyomo.readthedocs.io][5])

### Agent decision table

| Construct                       |            Ipopt direct use | Preferred action                                      |
| ------------------------------- | --------------------------: | ----------------------------------------------------- |
| `abs(x)`                        |                  no at kink | epigraph or smooth approximation                      |
| `max(x,y)`                      |                no at switch | epigraph if convex-compatible, GDP/MIP, or smooth max |
| `min(x,y)`                      |                no at switch | hypograph/epigraph or smooth min                      |
| variable-dependent `if`         |                          no | GDP/MIP/MINLP or smooth relaxation                    |
| piecewise linear exact          | usually discrete/non-smooth | MIP/MINLP or smooth approximation                     |
| complementarity                 |            not ordinary NLP | MPEC transformation, smoothing, or specialized solver |
| discontinuous external function |                          no | reformulate or different optimizer                    |

---

## 17.5 Check degrees of freedom for equality-constrained systems

### Rough degrees-of-freedom check

```python id="oy7lnk"
def rough_degrees_of_freedom(model):
    n_free = sum(
        1 for v in model.component_data_objects(pyo.Var, active=True)
        if not v.fixed
    )
    n_eq = sum(
        1 for c in model.component_data_objects(pyo.Constraint, active=True)
        if c.equality
    )
    return {
        "free_variables": n_free,
        "active_equalities": n_eq,
        "rough_dof": n_free - n_eq,
    }
```

### Report

```python id="0v7avv"
dof = rough_degrees_of_freedom(m)
print(dof)

if dof["rough_dof"] < 0:
    raise RuntimeError("Overdetermined equality system likely: inspect fixed vars and equalities.")
```

### Redundancy patterns

```text id="1hnji2"
Duplicate equality rows.
Mass balance repeated with total balance implied by unit balances.
Variable fixed and also constrained equal to same value.
Equality rows with identical left-hand sides and different right-hand sides.
Equality rows scaled versions of each other.
```

### Fixed variable anti-pattern

```python id="14e65y"
m.x.fix(3.0)
m.fix_x_again = pyo.Constraint(expr=m.x == 3.0)  # redundant
```

### Agent rules

```text id="y5x72l"
[ ] count free variables and active equalities before solving square/overdetermined systems.
[ ] avoid fixing variables and adding redundant equality constraints.
[ ] investigate Restoration_Failed / Not_Enough_Degrees_Of_Freedom with DOF checks.
[ ] remove duplicate or linearly dependent equalities before tuning Ipopt.
[ ] prefer model-structure fixes over dependency_detector as first-line remedy.
```

Ipopt output documentation notes that fixed variables may be removed internally from problem statistics, so the DOF seen by Ipopt can differ from raw Pyomo component counts when variables are fixed or lower/upper bounds coincide. ([coin-or.github.io][6])

---

## 17.6 Use `tee=True` and inspect iteration behavior before tuning options

### Bring-up solve

```python id="v4odqj"
opt = pyo.SolverFactory("ipopt")
opt.options.update({
    "print_level": 5,
    "print_user_options": "yes",
    "inf_pr_output": "original",
})

results = opt.solve(m, tee=True, load_solutions=False)
```

Pyomo documents `tee=True` as the solver-output streaming switch, and solver recipes show checking `results.solver.status` and `results.solver.termination_condition` before trusting results. ([pyomo.readthedocs.io][7])

### Read core columns

```text id="ikxnhd"
iter       iteration count; r suffix means restoration
objective  unscaled objective
inf_pr     original unscaled constraint violation by default
inf_du     scaled internal dual infeasibility
lg(mu)     log10 barrier parameter
||d||      primal step norm
lg(rg)     Hessian regularization
alpha_du   dual step length
alpha_pr   primal step length + acceptance tag
ls         backtracking count
```

Ipopt defines its standard iteration columns in the output docs, including restoration-phase suffixes, original unscaled constraint violation, scaled dual infeasibility, barrier parameter, step norms, regularization, step lengths, and line-search count. ([coin-or.github.io][6])

### Log triage before tuning

```text id="84ma0s"
high inf_pr:
  feasibility / bad starts / bad constraints

high inf_du:
  scaling / derivative / Hessian / dual issue

large/frequent lg(rg):
  Hessian/KKT degeneracy or scaling

many ls:
  line search trouble; check nonsmoothness/derivatives/scaling

r iterations:
  restoration phase; check feasibility and derivative correctness

objective nonmonotonic:
  not automatically failure under filter/barrier method
```

### Agent rules

```text id="m2z6pv"
[ ] inspect one default-ish `tee=True` log before tuning.
[ ] preserve logs for failures.
[ ] do not tune `max_iter` before reading convergence trend.
[ ] do not switch linear solvers before checking scaling/derivatives.
[ ] do not suppress output during first model validation.
```

---

## 17.7 Start with defaults, then tune one option family at a time

### Baseline profile

```python id="kuy38z"
BASELINE = {
    "tol": 1e-8,
    "max_iter": 3000,
    "print_level": 5,
    "print_user_options": "yes",
}
```

### Option-family buckets

```text id="u9n8qc"
Termination:
  tol, acceptable_tol, dual_inf_tol, constr_viol_tol, compl_inf_tol, max_iter

Scaling:
  nlp_scaling_method, nlp_scaling_max_gradient, scaling_factor suffix

Initialization:
  bound_push, bound_frac, least_square_init_primal, warm_start_* options

Hessian:
  hessian_approximation, limited_memory_* options

Linear solver:
  linear_solver, mumps_*, spral_*, pardiso_*, ma57_* options

Restoration:
  expect_infeasible_problem, required_infeasibility_reduction, max_resto_iter

Output:
  print_level, print_user_options, print_info_string, print_timing_statistics
```

Ipopt has many adjustable options split across termination, output, scaling, initialization, warm start, barrier updates, line search, linear solvers, restoration, Hessian approximation, and derivative checking; because options interact, controlled one-family-at-a-time tuning is safer than broad option mutation. ([coin-or.github.io][3])

### Controlled experiment pattern

```python id="1s0zie"
from copy import deepcopy

def solve_profile(model, profile, *, logfile):
    m = model.clone()
    opt = pyo.SolverFactory("ipopt")
    opt.options.update(profile)
    return opt.solve(m, tee=True, logfile=logfile, load_solutions=False), m


profiles = {
    "baseline": BASELINE,
    "scaled": {**BASELINE, "nlp_scaling_method": "gradient-based"},
    "limited_memory": {**BASELINE, "hessian_approximation": "limited-memory"},
    "mumps_stable": {**BASELINE, "linear_solver": "mumps", "mumps_pivtol": 1e-5},
}
```

### Agent rules

```text id="20pgi7"
[ ] compare profiles on cloned models or reset starts.
[ ] record option dictionary + log + termination + objective + residuals.
[ ] change one option family per experiment.
[ ] keep a baseline run for every benchmark.
[ ] preserve random/multistart seed metadata.
```

---

## 17.8 Prefer exact derivatives unless Hessians are too dense or expensive

### Exact Hessian default

```python id="5wv3a7"
opt.options["hessian_approximation"] = "exact"
```

### Limited-memory fallback

```python id="g2ufl3"
opt.options.update({
    "hessian_approximation": "limited-memory",
    "limited_memory_update_type": "bfgs",
    "limited_memory_max_history": 10,
})
```

Ipopt’s default Hessian mode is `exact`, which uses second derivatives from the NLP; `limited-memory` performs a limited-memory quasi-Newton approximation and can be selected when exact Hessians are unavailable or too expensive. ([coin-or.github.io][3])

### Exact derivative value case

```text id="ofb9de"
Exact Hessian:
  better Newton step quality
  fewer iterations
  stronger local convergence
  better dual/stationarity behavior
  preferred for smooth algebraic Pyomo NLPs
```

### Limited-memory value case

```text id="mslu3a"
Limited-memory:
  avoids exact second derivative cost
  lowers Hessian storage burden
  helpful for large models with expensive/dense Hessians
  useful when external functions lack Hessians
  often more iterations / weaker final stationarity
```

### Derivative checker for model quality

```python id="rqno37"
opt.options.update({
    "derivative_test": "first-order",
    "derivative_test_print_all": "yes",
    "max_iter": 0,
})
```

Ipopt’s derivative checker is a finite-difference test run before optimization at the user-provided starting point; it can test first derivatives, first and second derivatives, or only second derivatives, and it is explicitly marked as slow. ([coin-or.github.io][3])

### Agent rules

```text id="qtnx8a"
[ ] default to exact Hessian for smooth Pyomo algebraic models.
[ ] use limited-memory only with explicit reason.
[ ] run derivative checker before blaming Ipopt.
[ ] do not use limited-memory to hide nonsmoothness or bad Jacobians.
[ ] compare exact vs limited-memory with logs, residuals, and wall time.
```

---

## 17.9 Use `symbolic_solver_labels=True` for debugging, not necessarily production

### Classic interface

```python id="e5pyxk"
results = opt.solve(
    m,
    tee=True,
    keepfiles=True,
    symbolic_solver_labels=True,
)
```

### Newer Ipopt interface

```python id="jca8j0"
from pyomo.contrib.solver.solvers.ipopt import Ipopt

solver = Ipopt()
results = solver.solve(
    m,
    tee=True,
    working_dir="ipopt-debug",
    symbolic_solver_labels=True,
    solver_options={"tol": 1e-8},
)
```

The Pyomo NL writer’s `symbolic_solver_labels=True` option writes `.row` and `.col` files, while `file_determinism` controls deterministic file writing effort; row/column ordering can also be influenced through writer configuration, but the NL writer may group nonlinear rows/columns in solver-required ways. ([pyomo.readthedocs.io][4])

### Value case

```text id="kkdm68"
symbolic_solver_labels=True helps:
  map Ipopt row/column indices to Pyomo components
  interpret derivative-check output
  debug infeasible constraints
  archive reproducible solver artifacts
  trace generated .nl files
```

### Production caveat

```text id="iqbicu"
symbolic labels can:
  increase file size
  increase write time
  expose internal component names
  add unnecessary artifact volume in repeated solves
```

### Agent rules

```text id="3lcpgb"
[ ] enable symbolic labels for debugging, derivative checks, infeasibility triage.
[ ] disable for large production repeated solves unless traceability is required.
[ ] use keepfiles/working_dir only when artifacts are needed.
[ ] archive .row/.col/.nl only for reproducibility or support packages.
```

---

## 17.10 Keep `ipopt.opt` files version-controlled when option sets grow

### Minimal `ipopt.opt`

```text id="36vyha"
# ipopt.opt
tol 1e-8
max_iter 3000
print_user_options yes
nlp_scaling_method gradient-based
linear_solver mumps
```

Ipopt options can be set in code or by creating an `ipopt.opt` file in the execution directory; the file is read line-by-line as `option_name value` with `#` comments, and Ipopt notes that `ipopt.opt` takes preference over options set in an executable or AMPL model. ([coin-or.github.io][3])

### Recommended repository layout

```text id="me2zcd"
solver-options/
  ipopt.baseline.opt
  ipopt.debug-derivatives.opt
  ipopt.relaxed.opt
  ipopt.strict-final.opt
  README.md
```

### Option-file header convention

```text id="d6vfh1"
# Profile: strict-final
# Solver: Ipopt
# Interface: Pyomo SolverFactory("ipopt")
# Intended model family: refinery_nlp_v2
# Last validated with:
#   pyomo: <recorded version>
#   ipopt: <recorded version>
#   linear_solver: mumps
#   environment: environment.yml
# Notes:
#   Do not combine with derivative_test profiles.

tol 1e-9
dual_inf_tol 1e-8
constr_viol_tol 1e-8
compl_inf_tol 1e-8
acceptable_iter 0
max_iter 5000
print_user_options yes
```

### Agent rules

```text id="5w0q92"
[ ] move option sets out of Python once they become long/reused.
[ ] version-control ipopt.opt profiles with model code.
[ ] record intended interface and environment.
[ ] avoid undocumented mixtures of opt.options and ipopt.opt.
[ ] archive installed option dump with benchmark results.
```

---

## 17.11 Model-quality sanity checker

```python id="yft5l1"
from __future__ import annotations

import math
import pyomo.environ as pyo


def ipopt_quality_check(model, *, huge_bound=1e19, require_initial_values=True):
    errors = []
    warnings = []

    objectives = list(model.component_data_objects(pyo.Objective, active=True))
    if len(objectives) != 1:
        errors.append(f"Expected exactly one active objective; found {len(objectives)}.")

    for v in model.component_data_objects(pyo.Var, active=True):
        if not v.fixed and (v.is_binary() or v.is_integer()):
            errors.append(f"Active discrete variable invalid for Ipopt: {v.name}")

        if require_initial_values and not v.fixed and v.value is None:
            warnings.append(f"Missing initial value: {v.name}")

        val = pyo.value(v, exception=False)
        if val is not None:
            try:
                if not math.isfinite(float(val)):
                    errors.append(f"Nonfinite initial value: {v.name}={val}")
            except Exception:
                errors.append(f"Nonnumeric initial value: {v.name}={val!r}")

        lb = pyo.value(v.lb, exception=False) if v.lb is not None else None
        ub = pyo.value(v.ub, exception=False) if v.ub is not None else None

        if lb is not None and ub is not None and lb > ub:
            errors.append(f"Inconsistent bounds: {v.name}: lb={lb}, ub={ub}")

        if not v.fixed and lb is None and ub is None:
            warnings.append(f"Free active variable: {v.name}")

        if lb is not None and abs(lb) >= huge_bound:
            warnings.append(f"Huge lower bound may act like infinity: {v.name}: {lb}")

        if ub is not None and abs(ub) >= huge_bound:
            warnings.append(f"Huge upper bound may act like infinity: {v.name}: {ub}")

    for c in model.component_data_objects(pyo.Constraint, active=True):
        lb = pyo.value(c.lower, exception=False) if c.lower is not None else None
        ub = pyo.value(c.upper, exception=False) if c.upper is not None else None

        if lb is not None and ub is not None and lb > ub:
            errors.append(f"Inconsistent constraint bounds: {c.name}: lb={lb}, ub={ub}")

        body = pyo.value(c.body, exception=False)
        if body is None:
            warnings.append(f"Constraint body not evaluable at current start: {c.name}")
        else:
            try:
                if not math.isfinite(float(body)):
                    errors.append(f"Constraint body nonfinite at start: {c.name}: {body}")
            except Exception:
                errors.append(f"Constraint body nonnumeric at start: {c.name}: {body!r}")

    return errors, warnings
```

### Usage

```python id="8xcqtq"
errors, warnings = ipopt_quality_check(m)

for w in warnings:
    print("WARNING:", w)

for e in errors:
    print("ERROR:", e)

if errors:
    raise RuntimeError("Model violates Ipopt quality contract.")
```

---

## 17.12 Residual audit after solve

```python id="kb58m2"
def max_constraint_violation(model):
    worst = (None, 0.0, None, None, None)

    for c in model.component_data_objects(pyo.Constraint, active=True):
        body = pyo.value(c.body, exception=False)
        if body is None:
            continue

        lb = pyo.value(c.lower, exception=False) if c.lower is not None else None
        ub = pyo.value(c.upper, exception=False) if c.upper is not None else None

        lviol = 0.0 if lb is None else max(0.0, lb - body)
        uviol = 0.0 if ub is None else max(0.0, body - ub)
        viol = max(lviol, uviol)

        if viol > worst[1]:
            worst = (c.name, viol, body, lb, ub)

    return worst


def max_bound_violation(model):
    worst = (None, 0.0, None, None, None)

    for v in model.component_data_objects(pyo.Var, active=True):
        val = pyo.value(v, exception=False)
        if val is None:
            continue

        lb = pyo.value(v.lb, exception=False) if v.lb is not None else None
        ub = pyo.value(v.ub, exception=False) if v.ub is not None else None

        lviol = 0.0 if lb is None else max(0.0, lb - val)
        uviol = 0.0 if ub is None else max(0.0, val - ub)
        viol = max(lviol, uviol)

        if viol > worst[1]:
            worst = (v.name, viol, val, lb, ub)

    return worst
```

### Agent rules

```text id="67m0cz"
[ ] audit residuals after acceptable-level termination.
[ ] audit residuals after time/iteration-limited candidates.
[ ] audit residuals after restoring original units/scales.
[ ] audit original bounds when bound_relax_factor was nonzero.
```

---

## 17.13 Option tuning order

```text id="y6hx13"
Recommended order:
  1. validate model construction
  2. initialize variables
  3. check finite objective/constraints at start
  4. inspect default-ish tee log
  5. fix smoothness/domain issues
  6. scale model
  7. derivative_check on small instance
  8. tune tolerances
  9. tune Hessian strategy
  10. tune linear solver
  11. tune restoration/barrier/line-search internals only as expert moves
```

### Agent anti-order

```text id="8cqen9"
Do not:
  start with obscure line-search options
  switch to HSL/Pardiso before checking scaling/derivatives
  relax tolerances before checking physical residuals
  disable scaling blindly
  use limited-memory to hide derivative bugs
```

---

## 17.14 Production-ready solve wrapper

```python id="ivnbwv"
from dataclasses import dataclass
from pyomo.opt import SolverStatus, TerminationCondition


@dataclass(frozen=True)
class IpoptQualitySolveReport:
    status: str
    termination_condition: str
    objective: float | None
    max_constraint_violation: tuple
    max_bound_violation: tuple


def solve_ipopt_quality_checked(
    model,
    *,
    options: dict[str, object] | None = None,
    tee: bool = True,
    strict: bool = True,
):
    errors, warnings = ipopt_quality_check(model)
    for w in warnings:
        print("WARNING:", w)
    if errors:
        raise RuntimeError(f"Model quality errors: {errors}")

    opt = pyo.SolverFactory("ipopt")
    if not opt.available(exception_flag=False):
        raise RuntimeError("Ipopt unavailable.")

    opt.options.update({
        "tol": 1e-8,
        "max_iter": 3000,
        "print_level": 5 if tee else 0,
        "print_user_options": "yes" if tee else "no",
        "inf_pr_output": "original",
    })

    if options:
        opt.options.update(options)

    results = opt.solve(model, tee=tee, load_solutions=False)

    accepted = (
        results.solver.status == SolverStatus.ok
        and results.solver.termination_condition == TerminationCondition.optimal
    )

    if not accepted and strict:
        raise RuntimeError(
            f"Ipopt rejected: status={results.solver.status}, "
            f"termination={results.solver.termination_condition}"
        )

    if accepted:
        model.solutions.load_from(results)

    active_objs = list(model.component_data_objects(pyo.Objective, active=True))
    obj = pyo.value(active_objs[0], exception=False) if active_objs and accepted else None

    return results, IpoptQualitySolveReport(
        status=str(results.solver.status),
        termination_condition=str(results.solver.termination_condition),
        objective=obj,
        max_constraint_violation=max_constraint_violation(model) if accepted else (None, None, None, None, None),
        max_bound_violation=max_bound_violation(model) if accepted else (None, None, None, None, None),
    )
```

---

## 17.15 Best-practice matrix

| Practice                      | Value case                                  | Syntax / action                                           |
| ----------------------------- | ------------------------------------------- | --------------------------------------------------------- |
| Initialize variables          | finite evaluation, better local convergence | `Var(initialize=...)`, `.set_value(...)`                  |
| Scale model                   | stable residuals and linear solves          | nondimensionalize, `scaling_factor`, `nlp_scaling_method` |
| Use meaningful bounds         | domain protection and numerical stability   | `bounds=(lb, ub)`, `NonNegativeReals`                     |
| Avoid nonsmooth ops           | Ipopt smooth NLP contract                   | epigraph, smoothing, GDP/MIP/MINLP                        |
| Check DOF                     | avoid overdetermined equality systems       | count free vars vs active equalities                      |
| Inspect logs first            | diagnose before tuning                      | `tee=True`, `print_user_options=yes`                      |
| Tune one family at a time     | reproducible experiments                    | profile dictionaries                                      |
| Prefer exact Hessian          | best local convergence                      | `hessian_approximation="exact"`                           |
| Use symbolic labels for debug | row/column traceability                     | `symbolic_solver_labels=True`                             |
| Version-control options       | reproducible solver behavior                | `ipopt.opt`, option-profile registry                      |

---

## 17.16 Anti-pattern catalog

```text id="2srap7"
BAD:
  no initialization for nonlinear variables.

GOOD:
  initialize every nonlinear variable near meaningful feasible values.

BAD:
  raw mixed SI units everywhere.

GOOD:
  nondimensionalize and scale rows/objective terms.

BAD:
  fake infinite bounds like 1e20.

GOOD:
  None for true infinity; finite physical bounds for real limits.

BAD:
  abs/max/min/if-else inside active Ipopt NLP.

GOOD:
  smooth approximation, epigraph, GDP/MIP/MINLP, or complementarity reformulation.

BAD:
  multiple active objectives.

GOOD:
  one active scalar Objective; deactivate or scalarize.

BAD:
  tune many Ipopt options simultaneously.

GOOD:
  one option family per experiment.

BAD:
  limited-memory Hessian by default.

GOOD:
  exact Hessian unless dense/expensive/unavailable.

BAD:
  symbolic_solver_labels=True in massive production loops by default.

GOOD:
  use symbolic labels for debugging and reproducibility artifacts.

BAD:
  long ad hoc option dictionaries hidden in scripts.

GOOD:
  named profiles or version-controlled ipopt.opt files.
```

---

## 17.17 Final checklist

```text id="teapfi"
[ ] Exactly one active objective.
[ ] All Ipopt decision variables continuous.
[ ] All nonlinear variables initialized.
[ ] Starts are finite and inside nonlinear-function domains.
[ ] Bounds are physically meaningful or intentionally absent.
[ ] No fake-infinity bounds.
[ ] Objective and constraint terms scaled to comparable magnitudes.
[ ] Constraints use equality/inequality/ranged forms correctly.
[ ] No active nonsmooth abs/max/min/floor/ceil/round/conditionals.
[ ] Piecewise/GDP/discrete logic routed through appropriate reformulation or solver.
[ ] Rough degrees of freedom checked for equality-heavy models.
[ ] `tee=True` used during bring-up.
[ ] Solver logs inspected before option tuning.
[ ] Derivative checker run on small representative model if derivatives are suspect.
[ ] Exact Hessian used unless explicit reason for limited-memory.
[ ] Symbolic labels used for debugging, disabled for large production unless needed.
[ ] Option profiles named, documented, and version-controlled.
[ ] `ipopt.opt`, environment, option dump, and logs archived for reproducible studies.
```

[1]: https://coin-or.github.io/Ipopt/ "Ipopt: Documentation"
[2]: https://pyomo.readthedocs.io/en/latest/api/pyomo.core.base.var.Var.html "Var — Pyomo 6.10.1.dev0 documentation"
[3]: https://coin-or.github.io/Ipopt/OPTIONS.html "Ipopt: Ipopt Options"
[4]: https://pyomo.readthedocs.io/en/stable/api/pyomo.repn.plugins.nl_writer.NLWriter.html "NLWriter — Pyomo 6.10.0 documentation"
[5]: https://pyomo.readthedocs.io/en/6.4.4/pyomo_modeling_components/Expressions.html "Expressions — Pyomo 6.4.4 documentation"
[6]: https://coin-or.github.io/Ipopt/OUTPUT.html "Ipopt: Ipopt Output"
[7]: https://pyomo.readthedocs.io/en/latest/howto/solver_recipes.html "Solver Recipes — Pyomo 6.10.1.dev0 documentation"

# Ipopt Advanced — Section 18: performance engineering

Style target: dense advanced technical catalog / agent-ready reference. 

## 18.0 Performance invariant

```text id="svrfik"
Pyomo + Ipopt runtime =
  Python model construction time
  + expression/representation generation time
  + NL writer time
  + temporary-file I/O time
  + Ipopt function/derivative evaluation time
  + sparse KKT linear-solver time
  + result parsing/loading time
```

**Performance hierarchy**

```text id="eecru3"
First-order levers:
  sparse algebraic structure
  model reuse / mutable Params
  APPSI for repeated solves
  linear solver selection
  scaling and initialization
  BLAS/OpenMP threading policy
  parallel scenario orchestration

Second-order levers:
  symbolic labels / temporary-file management
  writer_config controls
  timing instrumentation
  option bundle tuning
  warm starts
```

Ipopt’s install docs emphasize that it requires a sparse symmetric indefinite linear solver and that the largest fraction of optimizer time is usually spent solving the linear system; the same docs recommend trying different linear solvers because linear-solver choice impacts speed and robustness. ([coin-or.github.io](https://coin-or.github.io/Ipopt/INSTALL.html))

---

## 18.1 Sparse expression construction in Pyomo

### Dense anti-pattern: all-to-all coupling

```python id="kqugb6"
# BAD: every constraint depends on every variable.
m.c = pyo.Constraint(
    m.I,
    rule=lambda m, i: sum(m.x[j] for j in m.J) >= m.demand[i],
)
```

### Sparse adjacency pattern

```python id="li1g9p"
# GOOD: each row depends only on known nonzero adjacency.
m.N = pyo.Set(m.I, initialize=lambda m, i: neighbors[i])

m.c = pyo.Constraint(
    m.I,
    rule=lambda m, i: sum(m.x[j] for j in m.N[i]) >= m.demand[i],
)
```

### Sparse coefficient set pattern

```python id="xemjjz"
# Nonzero coefficient tuples only.
m.ANZ = pyo.Set(dimen=2, initialize=list(A.keys()))

m.c = pyo.Constraint(
    m.I,
    rule=lambda m, i: sum(A[i, j] * m.x[j] for j in m.J if (i, j) in A) >= m.b[i],
)
```

Better: pre-index by row to avoid repeated membership checks inside each constraint rule.

```python id="33nl3s"
A_by_i = {i: [] for i in I}
for (i, j), val in A.items():
    A_by_i[i].append((j, val))

m.A_ROWS = pyo.Set(m.I, initialize=lambda m, i: [j for j, _ in A_by_i[i]])

def row_rule(m, i):
    return sum(A[i, j] * m.x[j] for j in m.A_ROWS[i]) >= m.b[i]

m.c = pyo.Constraint(m.I, rule=row_rule)
```

### Sparse quadratic objective

```python id="s6gzh0"
# BAD if Q is sparse but loops over all i,j.
m.obj = pyo.Objective(
    expr=sum(Q[i, j] * m.x[i] * m.x[j] for i in m.I for j in m.I)
)
```

```python id="hsh7td"
# GOOD: loop only over nonzero terms.
m.QNZ = pyo.Set(dimen=2, initialize=list(Q.keys()))
m.obj = pyo.Objective(
    expr=sum(Q[i, j] * m.x[i] * m.x[j] for (i, j) in m.QNZ)
)
```

### Value case

```text id="uv397l"
Sparse construction reduces:
  Pyomo expression tree size
  NL file size
  Jacobian/Hessian nonzeros
  KKT factorization fill-in
  linear-solver memory pressure
  solve time and numerical instability
```

Pyomo’s NL writer exposes row/column ordering and nonlinear-variable handling because row/column structure affects generated NL layout; the writer may move nonlinear constraints before linear ones and nonlinear variables before linear-only variables, which reinforces that structural sparsity is first-class solver input, not cosmetic code style. ([pyomo.readthedocs.io](https://pyomo.readthedocs.io/en/stable/api/pyomo.repn.plugins.nl_writer.NLWriter.html))

---

## 18.2 Avoid Python-side repeated construction inside solve loops

### Bad: rebuild model for every scenario

```python id="rya7vo"
for scenario in scenarios:
    m = build_model(scenario)
    opt = pyo.SolverFactory("ipopt")
    res = opt.solve(m)
```

### Better: build once, update mutable data

```python id="c3adee"
m = build_model(base_data)

opt = pyo.SolverFactory("ipopt")
opt.options.update({
    "tol": 1e-8,
    "print_level": 0,
    "sb": "yes",
})

for scenario in scenarios:
    for i in m.I:
        m.demand[i].set_value(scenario["demand"][i])

    # Previous Var.value values act as primal starts.
    res = opt.solve(m, tee=False)
```

### Best repeated-solve posture: APPSI where applicable

```python id="i259ot"
from pyomo.contrib import appsi

opt = appsi.solvers.Ipopt()
opt.ipopt_options["tol"] = 1e-8

for scenario in scenarios:
    for i in m.I:
        m.demand[i].set_value(scenario["demand"][i])

    res = opt.solve(m)
    assert res.termination_condition == appsi.base.TerminationCondition.optimal
    opt.load_vars()
```

APPSI solver interfaces are designed to look similar to other Pyomo solver interfaces while being efficient for resolving the same model with small changes; the Pyomo APPSI docs list Benders decomposition, optimization-based bounds tightening, progressive hedging, and outer approximation as examples and show repeated solves after updating a mutable `Param`. ([pyomo.readthedocs.io](https://pyomo.readthedocs.io/en/stable/reference/topical/appsi/appsi.html))

### Agent rule

```text id="nogxmf"
If only numeric data changes:
  use mutable Param
  reuse model instance
  reuse previous Var.value starts
  consider APPSI

If sets/index dimensions/expression topology change:
  rebuild model or use persistent/APPSI structural update methods carefully
```

---

## 18.3 Mutable `Param` for parametric studies

### Scalar mutable parameter

```python id="n0loml"
m.p = pyo.Param(initialize=1.0, mutable=True)

m.x = pyo.Var(initialize=0.0)
m.obj = pyo.Objective(expr=(m.x - m.p) ** 2)
```

### Indexed mutable parameter

```python id="l2zx6d"
m.I = pyo.Set(initialize=I)
m.demand = pyo.Param(m.I, mutable=True, initialize=0.0)

m.x = pyo.Var(m.I, bounds=(0, None), initialize=1.0)
m.c = pyo.Constraint(m.I, rule=lambda m, i: m.x[i] >= m.demand[i])
m.obj = pyo.Objective(expr=sum(m.x[i] ** 2 for i in m.I))
```

### Update loop

```python id="o2x0z7"
for data in scenario_data:
    for i in m.I:
        m.demand[i].set_value(data[i])
    res = opt.solve(m, tee=False)
```

### Performance value case

```text id="agecpr"
Mutable Param avoids:
  re-declaring variables
  re-declaring constraints
  re-building expression trees
  re-indexing components
  garbage-collecting many model instances
```

### Agent caveat

```text id="43l3ja"
Mutable Param changes numeric values, not model topology.
Do not use it to:
  add variables
  remove constraints
  change Set membership
  change expression forms
  switch between constraints and objectives
```

---

## 18.4 Reusing model instances versus rebuilding

### Reuse model instance when

```text id="sdhlvi"
[ ] same variables
[ ] same active constraints
[ ] same active objective
[ ] same index sets
[ ] same expression topology
[ ] different coefficients/RHS/targets
[ ] repeated solves need previous solution as start
```

### Rebuild model when

```text id="9a3wfm"
[ ] index set size changes
[ ] variable set changes
[ ] constraints added/removed
[ ] disjunctive structure changes
[ ] expression topology changes
[ ] active objective switches materially
[ ] component identity no longer maps to previous suffix/warm-start data
```

### Detect structural drift

```python id="nwh7ok"
def model_fingerprint(model):
    vars_ = tuple(v.name for v in model.component_data_objects(pyo.Var, active=True))
    cons_ = tuple(c.name for c in model.component_data_objects(pyo.Constraint, active=True))
    objs_ = tuple(o.name for o in model.component_data_objects(pyo.Objective, active=True))
    fixed = tuple((v.name, bool(v.fixed)) for v in model.component_data_objects(pyo.Var, active=True))
    return vars_, cons_, objs_, fixed
```

### Agent policy

```text id="a976x0"
Reuse model for:
  parametric sweeps
  homotopy
  multi-period rolling updates with fixed horizon
  local nonlinear subproblems with fixed algebra

Rebuild model for:
  variable-horizon models
  scenario-dependent topology
  activated/deactivated constraint families
  mixed-integer or GDP transformations that change structure
```

---

## 18.5 APPSI repeated-solve workflows

### Minimal APPSI Ipopt workflow

```python id="iqzymu"
from pyomo.contrib import appsi

solver = appsi.solvers.Ipopt()
solver.ipopt_options.update({
    "tol": 1e-8,
    "print_level": 0,
})

res = solver.solve(m)
if res.termination_condition == appsi.base.TerminationCondition.optimal:
    solver.load_vars()
```

### Repeated mutable-parameter solve

```python id="iq1iai"
import numpy as np
import pyomo.environ as pyo
from pyomo.contrib import appsi
from pyomo.common.timing import HierarchicalTimer

m = pyo.ConcreteModel()
m.x = pyo.Var(initialize=1.0)
m.y = pyo.Var(initialize=1.0)
m.p = pyo.Param(mutable=True, initialize=1.0)

m.obj = pyo.Objective(expr=m.x**2 + m.y**2)
m.c1 = pyo.Constraint(expr=m.y >= pyo.exp(m.x))
m.c2 = pyo.Constraint(expr=m.y >= (m.x - m.p)**2)

opt = appsi.solvers.Ipopt()
timer = HierarchicalTimer()

for p_val in np.linspace(1, 10, 100):
    m.p.value = float(p_val)
    res = opt.solve(m, timer=timer)
    assert res.termination_condition == appsi.base.TerminationCondition.optimal
    opt.load_vars()

print(timer)
```

This closely matches Pyomo’s APPSI example: it creates mutable `Param` `p`, updates it in a loop, solves with `appsi.solvers.Ipopt()`, asserts optimal termination, and prints a `HierarchicalTimer`; the docs explicitly motivate APPSI for efficient repeated resolves with small model changes. ([pyomo.readthedocs.io](https://pyomo.readthedocs.io/en/stable/reference/topical/appsi/appsi.html))

### APPSI update-config risk controls

```python id="1f8swg"
# Only when structure is guaranteed fixed.
opt.update_config.check_for_new_or_removed_constraints = False
opt.update_config.check_for_new_or_removed_vars = False
opt.update_config.update_constraints = False
opt.update_config.update_vars = False
```

### Agent policy

```text id="2j3j4e"
APPSI is high-value when:
  solve count is high
  model structure fixed
  Params change frequently
  decomposition loop calls many NLPs
  previous primal solution is useful as start

APPSI can be wrong/dangerous when:
  checks disabled and structure changes
  constraints are activated/deactivated silently
  variables added/removed
  objective replaced
  suffix/warm-start data becomes stale
```

---

## 18.6 Temporary file locations and working directories

### Classic Pyomo tempdir control

```python id="5ra3o4"
from pyomo.common.tempfiles import TempfileManager

TempfileManager.tempdir = "/scratch/$USER/pyomo-tmp"
```

Pyomo’s “Working with Models” docs state that a temporary directory is used for many intermediate files and that users can set it in scripts through `pyomo.common.tempfiles.TempfileManager.tempdir`; the command-line `--tempdir` option propagates to the same service. ([pyomo.readthedocs.io](https://pyomo.readthedocs.io/en/6.6.2/working_models.html))

### Classic keepfiles for debugging

```python id="0dsmlh"
res = opt.solve(
    model,
    tee=True,
    keepfiles=True,
    symbolic_solver_labels=True,
)
```

### New Ipopt interface working directory

```python id="aetfxk"
from pyomo.contrib.solver.solvers.ipopt import Ipopt

opt = Ipopt()
res = opt.solve(
    model,
    tee=True,
    working_dir="ipopt-work",
    symbolic_solver_labels=True,
    solver_options={"tol": 1e-8},
)
```

The new Pyomo Ipopt interface exposes `working_dir` for generated files and exposes writer configuration through `writer_config`; Pyomo’s redesigned-solver docs also state the new Ipopt interface can access writer capabilities such as linear presolve and scaling through `writer_config`. ([pyomo.readthedocs.io](https://pyomo.readthedocs.io/en/stable/explanation/experimental/solvers.html))

### NLWriter file-size and determinism controls

```python id="93as6k"
from pyomo.contrib.solver.solvers.ipopt import Ipopt

opt = Ipopt()
opt.config.writer_config.symbolic_solver_labels = False
opt.config.writer_config.linear_presolve = True
opt.config.writer_config.scale_model = True
opt.config.writer_config.export_defined_variables = True
```

The NL writer configuration includes `symbolic_solver_labels`, `scale_model`, `export_defined_variables`, and `linear_presolve`; `symbolic_solver_labels=True` writes `.row` and `.col` files, `scale_model=True` uses the `scaling_factor` suffix, `export_defined_variables=True` exports `Expression` objects as defined variables, and `linear_presolve=True` performs basic linear presolve through variable elimination without fill-in. ([pyomo.readthedocs.io](https://pyomo.readthedocs.io/en/stable/api/pyomo.repn.plugins.nl_writer.NLWriter.html))

### Agent rules

```text id="j3tk6b"
Use fast local scratch:
  TMPDIR=/scratch/... or TempfileManager.tempdir

Avoid network filesystem:
  many .nl/.sol/log temporary files can bottleneck

Use keepfiles/working_dir:
  debugging, reproducibility, support artifacts

Disable symbolic labels in production:
  smaller files, lower writer overhead

Enable symbolic labels in diagnostics:
  row/column traceability
```

---

## 18.7 Solver log timing: Ipopt timers

### Ipopt timing options

```python id="oocue1"
opt.options.update({
    "print_timing_statistics": "yes",
})
```

`print_timing_statistics=yes` tells Ipopt to print timing for selected tasks and implies `timing_statistics=yes`; default is `no`. ([coin-or.github.io](https://coin-or.github.io/Ipopt/OPTIONS.html))

### Full timing/audit profile

```python id="33zbwb"
opt.options.update({
    "print_timing_statistics": "yes",
    "print_user_options": "yes",
    "print_level": 5,
})
res = opt.solve(model, tee=True, logfile="ipopt-timing.log")
```

### Timing interpretation

```text id="4cmsty"
If Ipopt time dominates in linear algebra:
  benchmark linear_solver
  improve sparsity
  tune scaling
  inspect BLAS/OpenMP threads

If function/derivative evaluation dominates:
  simplify Pyomo expressions
  avoid external Python bottlenecks
  reduce expression duplication
  improve NL writer structure

If Pyomo-side model construction dominates:
  reuse model
  use mutable Params
  avoid rebuilding expression trees

If temporary file I/O dominates:
  use local scratch
  avoid keepfiles/symbolic labels in production
```

### Pyomo/APPSI timer

```python id="2gbe2w"
from pyomo.common.timing import HierarchicalTimer
from pyomo.contrib import appsi

timer = HierarchicalTimer()
opt = appsi.solvers.Ipopt()

res = opt.solve(m, timer=timer)
print(timer)
```

Pyomo’s APPSI docs demonstrate passing `HierarchicalTimer` into repeated APPSI solves and printing the timer after the loop. ([pyomo.readthedocs.io](https://pyomo.readthedocs.io/en/stable/reference/topical/appsi/appsi.html))

---

## 18.8 BLAS threading and conda BLAS variant control

### Inspect current conda BLAS stack

```bash id="3s71ec"
conda list "libblas|liblapack|openblas|mkl|blis|accelerate"
```

### Pin OpenBLAS variant

```yaml id="q57km0"
channels:
  - conda-forge
channel_priority: strict
dependencies:
  - python=3.11
  - pyomo
  - ipopt
  - libblas=*=*openblas
  - liblapack=*=*openblas
```

### Pin MKL variant where compatible

```yaml id="szm1tq"
channels:
  - conda-forge
channel_priority: strict
dependencies:
  - python=3.11
  - pyomo
  - ipopt
  - libblas=*=*mkl
  - liblapack=*=*mkl
```

Ipopt’s install docs recommend using an efficient BLAS/LAPACK implementation tailored to hardware and show MKL linking examples for custom builds; conda-forge packages depend on abstract BLAS/LAPACK packages, so environment constraints determine the implementation. ([coin-or.github.io](https://coin-or.github.io/Ipopt/INSTALL.html))

### Thread caps for many independent solves

```bash id="ke76n6"
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
```

### Thread policy

```text id="rmz0rw"
One large Ipopt solve:
  benchmark multiple BLAS/OpenMP thread counts

Many independent scenarios:
  cap threads to 1 per process to avoid oversubscription

SPRAL/Pardiso threaded solver:
  coordinate OMP_NUM_THREADS with solver-specific parallelism

Docker/CI:
  set thread env vars explicitly for reproducible timing
```

---

## 18.9 Parallel scenario solving: multiprocessing

### Process-level scenario solve

```python id="qhsfuf"
from __future__ import annotations

import os
from concurrent.futures import ProcessPoolExecutor
import pyomo.environ as pyo


def solve_scenario(scenario):
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    os.environ.setdefault("MKL_NUM_THREADS", "1")

    m = build_model(scenario)

    opt = pyo.SolverFactory("ipopt")
    opt.options.update({
        "tol": 1e-8,
        "print_level": 0,
        "sb": "yes",
    })

    res = opt.solve(m, tee=False, load_solutions=False)

    return {
        "scenario": scenario["name"],
        "status": str(res.solver.status),
        "termination": str(res.solver.termination_condition),
    }


with ProcessPoolExecutor(max_workers=8) as pool:
    results = list(pool.map(solve_scenario, scenarios))
```

### Multiprocessing rules

```text id="tbfdmg"
[ ] build model inside worker, or pass serializable data only.
[ ] do not share Pyomo model objects across processes.
[ ] do not share SolverFactory objects across processes.
[ ] set thread caps before workers import heavy numerical libraries if possible.
[ ] use per-worker temp directories if filesystem collisions occur.
[ ] avoid writing all logs to same file.
```

### Per-worker tempdir pattern

```python id="5xe6rj"
from pathlib import Path
from pyomo.common.tempfiles import TempfileManager

def solve_scenario(scenario):
    tmp = Path("/scratch") / os.environ["USER"] / "pyomo" / scenario["name"]
    tmp.mkdir(parents=True, exist_ok=True)
    TempfileManager.tempdir = str(tmp)

    m = build_model(scenario)
    opt = pyo.SolverFactory("ipopt")
    return opt.solve(m, tee=False)
```

---

## 18.10 Parallel scenario solving: MPI

### `mpi4py` sketch

```python id="6jyckd"
from mpi4py import MPI
import os
import pyomo.environ as pyo

comm = MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

local_scenarios = scenarios[rank::size]
local_results = []

for scenario in local_scenarios:
    m = build_model(scenario)
    opt = pyo.SolverFactory("ipopt")
    opt.options.update({"print_level": 0, "sb": "yes"})
    res = opt.solve(m, tee=False)
    local_results.append((scenario["name"], str(res.solver.termination_condition)))

all_results = comm.gather(local_results, root=0)
```

### MUMPS/MPI caveat

```text id="nrlqbi"
Conda/default MUMPS often uses sequential/fake-MPI variants.
Embedding many Ipopt+MUMPS solves inside MPI jobs can interact with MPI symbols in some builds.
Prefer process-per-scenario with thread caps unless a parallel-MUMPS/Ipopt build is explicitly validated.
```

Ipopt’s install docs warn that non-MPI MUMPS uses an internal fake MPI implementation that can interfere with using Ipopt and MUMPS inside an MPI program, and describe options involving MPI-parallel MUMPS builds. ([coin-or.github.io](https://coin-or.github.io/Ipopt/INSTALL.html))

---

## 18.11 Linear solver selection as first serious performance lever

### Baseline

```python id="gum7sd"
opt.options["linear_solver"] = "mumps"
```

### Probe and benchmark

```python id="pzj5ys"
def available_linear_solvers():
    opt = pyo.SolverFactory("ipopt")
    candidates = ["mumps", "spral", "ma57", "pardiso", "pardisomkl"]
    out = {}
    for ls in candidates:
        try:
            out[ls] = opt.has_linear_solver(ls)
        except Exception as exc:
            out[ls] = f"{type(exc).__name__}: {exc}"
    return out
```

### Benchmark harness

```python id="o7la78"
import time

def solve_with_solver(model, linear_solver):
    m = model.clone()
    opt = pyo.SolverFactory("ipopt")

    if not opt.has_linear_solver(linear_solver):
        return {"linear_solver": linear_solver, "available": False}

    opt.options.update({
        "linear_solver": linear_solver,
        "tol": 1e-8,
        "print_level": 0,
    })

    t0 = time.perf_counter()
    res = opt.solve(m, tee=False, load_solutions=True)
    elapsed = time.perf_counter() - t0

    return {
        "linear_solver": linear_solver,
        "available": True,
        "status": str(res.solver.status),
        "termination": str(res.solver.termination_condition),
        "elapsed_s": elapsed,
        "objective": pyo.value(next(m.component_data_objects(pyo.Objective, active=True))),
    }
```

### Agent policy

```text id="jzg02z"
Performance tuning order:
  1. preserve sparsity
  2. scale model
  3. initialize well
  4. profile default MUMPS
  5. test available alternative linear solvers
  6. tune MUMPS/SPRAL/Pardiso/HSL-specific options
```

Ipopt’s `linear_solver` option chooses the package used to solve the augmented linear system for search directions; documented values include HSL solvers, Pardiso variants, SPRAL, WSMP, MUMPS, and custom, but installed availability is build-dependent. ([coin-or.github.io](https://coin-or.github.io/Ipopt/OPTIONS.html))

---

## 18.12 NL writer controls for performance

### Disable symbolic labels in production

```python id="ux5c37"
res = opt.solve(
    model,
    tee=False,
    symbolic_solver_labels=False,
)
```

### New interface writer config

```python id="z4xzqa"
from pyomo.contrib.solver.solvers.ipopt import Ipopt

opt = Ipopt()
opt.config.writer_config.symbolic_solver_labels = False
opt.config.writer_config.linear_presolve = True
opt.config.writer_config.scale_model = True
opt.config.writer_config.export_defined_variables = True
```

### Writer controls and implications

| Control                         | Performance implication                                            |
| ------------------------------- | ------------------------------------------------------------------ |
| `symbolic_solver_labels=False`  | avoids `.row` / `.col` overhead                                    |
| `linear_presolve=True`          | eliminates variables through basic linear presolve without fill-in |
| `scale_model=True`              | emits scaled NL if `scaling_factor` suffix exists                  |
| `export_defined_variables=True` | can reduce repeated expression emission by using defined variables |
| `file_determinism=ORDERED`      | lower deterministic overhead than sorting everything               |
| `show_section_timing=True`      | writer diagnostic only; not production default                     |

The NL writer docs state that `symbolic_solver_labels=True` writes row/column name files; `linear_presolve=True` performs basic linear presolve through variable elimination without fill-in; and `show_section_timing=True` prints timing after each NL file section. ([pyomo.readthedocs.io](https://pyomo.readthedocs.io/en/stable/api/pyomo.repn.plugins.nl_writer.NLWriter.html))

---

## 18.13 Avoid expression duplication

### Bad: duplicate expensive expression in many places

```python id="j7sajm"
m.obj = pyo.Objective(expr=sum((m.x[i] + m.y[i])**4 for i in m.I))
m.c = pyo.Constraint(m.I, rule=lambda m, i: (m.x[i] + m.y[i])**4 <= m.ub[i])
```

### Better: named `Expression`

```python id="5wkcrz"
m.poly = pyo.Expression(m.I, rule=lambda m, i: (m.x[i] + m.y[i])**4)

m.obj = pyo.Objective(expr=sum(m.poly[i] for i in m.I))
m.c = pyo.Constraint(m.I, rule=lambda m, i: m.poly[i] <= m.ub[i])
```

### NL writer defined variables

```python id="ty63dh"
opt.config.writer_config.export_defined_variables = True
```

The NL writer has `export_defined_variables=True` by default, which exports `Expression` objects to the NL file as defined variables. ([pyomo.readthedocs.io](https://pyomo.readthedocs.io/en/stable/api/pyomo.repn.plugins.nl_writer.NLWriter.html))

### Agent rule

```text id="7z9o2u"
Use Expression when:
  nonlinear subexpression reused
  model readability improves
  derivative structure should avoid duplicated trees

Do not overuse Expression:
  for one-off tiny linear fragments
  if it obscures sparse indexing
```

---

## 18.14 Warm starts and continuation as performance tools

### Warm-start option bundle

```python id="evjfx9"
opt.options.update({
    "warm_start_init_point": "yes",
    "warm_start_bound_push": 1e-6,
    "warm_start_mult_bound_push": 1e-6,
    "mu_init": 1e-6,
})
```

### Suffix copy

```python id="cstyfx"
model.ipopt_zL_in.update(model.ipopt_zL_out)
model.ipopt_zU_in.update(model.ipopt_zU_out)
```

### Continuation loop

```python id="nd4wo8"
m.alpha = pyo.Param(mutable=True, initialize=0.0)

for alpha in [0.0, 0.25, 0.5, 0.75, 1.0]:
    m.alpha.set_value(alpha)
    res = opt.solve(m, tee=False)
```

### Value case

```text id="u99pvq"
Warm starts / continuation reduce:
  iterations for related solves
  restoration risk for hard nonconvex problems
  local-basin jumps in parameter sweeps

But:
  active-set changes can make warm starts worse
  stale multipliers can harm solve
  structural changes invalidate suffix data
```

---

## 18.15 Profiling model construction time

### Basic timers

```python id="tqsrfs"
import time

t0 = time.perf_counter()
m = build_model(data)
t_build = time.perf_counter() - t0

t1 = time.perf_counter()
res = opt.solve(m, tee=True)
t_solve = time.perf_counter() - t1

print({"build_s": t_build, "solve_s": t_solve})
```

### APPSI timer

```python id="5m5mf5"
from pyomo.common.timing import HierarchicalTimer

timer = HierarchicalTimer()
res = opt.solve(m, timer=timer)
print(timer)
```

### Agent interpretation

```text id="tfwc1d"
If build_s ≫ solve_s:
  reuse model instance
  reduce Python loops
  pre-index sparse data
  avoid repeated component construction

If solve_s ≫ build_s:
  inspect Ipopt timing
  test linear solvers
  scale/initialize
  reduce KKT size/sparsity
```

---

## 18.16 Performance benchmark artifact contract

```text id="ko36du"
Record:
  model fingerprint
  scenario count
  variable/constraint counts
  Jacobian/Hessian nonzero counts if available
  environment.yml
  conda list
  ipopt -v
  ipopt --print-options
  BLAS/LAPACK variant
  thread environment variables
  linear_solver
  Ipopt options
  solver log
  build time
  NL write time if measured
  solve time
  result load time
  termination condition
  objective/residuals
```

### Environment logging snippet

```python id="s9wl79"
import os
import shutil
import subprocess
import sys

def performance_environment_snapshot():
    return {
        "python": sys.executable,
        "ipopt": shutil.which("ipopt"),
        "OMP_NUM_THREADS": os.environ.get("OMP_NUM_THREADS"),
        "OPENBLAS_NUM_THREADS": os.environ.get("OPENBLAS_NUM_THREADS"),
        "MKL_NUM_THREADS": os.environ.get("MKL_NUM_THREADS"),
        "ipopt_version": subprocess.run(
            ["ipopt", "-v"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        ).stdout.strip() if shutil.which("ipopt") else None,
    }
```

---

## 18.17 Performance anti-patterns

```text id="zrroua"
BAD:
  rebuild model from scratch for 10,000 scenarios with only RHS changes.

GOOD:
  mutable Param + model reuse or APPSI.

BAD:
  dense all-to-all sums when coefficient matrix is sparse.

GOOD:
  nonzero index sets and row-wise adjacency lists.

BAD:
  symbolic_solver_labels=True in production loop.

GOOD:
  enable labels only for debug/repro artifacts.

BAD:
  write temp files to slow network filesystem.

GOOD:
  set local scratch TempfileManager.tempdir or working_dir.

BAD:
  run 64 scenario processes with each using 16 BLAS threads.

GOOD:
  cap BLAS/OpenMP threads per process.

BAD:
  tune obscure Ipopt line-search options before testing linear_solver and scaling.

GOOD:
  sparse model + scale + initialize + linear solver benchmark first.

BAD:
  compare linear solvers on toy model only.

GOOD:
  benchmark representative model family and scenario set.
```

---

## 18.18 Final checklist

```text id="hyx0dd"
[ ] Build sparse Pyomo expressions from nonzero index sets.
[ ] Precompute adjacency lists outside constraint rules.
[ ] Avoid dense all-to-all sums unless physically necessary.
[ ] Avoid rebuilding models when only coefficients/RHS values change.
[ ] Use mutable Param for parametric studies.
[ ] Preserve previous Var.value values as starts for related solves.
[ ] Use APPSI for repeated same-structure solves where overhead matters.
[ ] Do not disable APPSI update checks unless structure is guaranteed fixed.
[ ] Place temporary files on local scratch for large jobs.
[ ] Use keepfiles/working_dir only for debugging/reproducibility.
[ ] Disable symbolic_solver_labels in production unless traceability needed.
[ ] Use print_timing_statistics=yes for solver timing audits.
[ ] Use HierarchicalTimer for APPSI/Pyomo-side repeated-solve timing.
[ ] Pin or record BLAS/LAPACK variant for benchmarks.
[ ] Set thread caps for parallel scenario solves.
[ ] Use process-level parallelism carefully; do not share model/solver objects across processes.
[ ] Treat linear_solver selection as the first major Ipopt performance lever after model sparsity/scaling.
[ ] Archive environment, options, logs, timing, and residuals for every serious benchmark.
```

# Ipopt Advanced — Section 19: advanced Pyomo workflows

Style target: dense advanced technical catalog / agent-ready reference. 

## 19.0 Advanced-workflow invariant

```text id="de40kd"
Advanced Pyomo + Ipopt workflow =
  repeated related NLP solves
  + controlled model mutation
  + warm starts / continuation / slacks
  + decomposition subproblem orchestration
  + solver-interface selection
  + explicit local-vs-global guarantees
```

Ipopt is a local smooth-NLP solver. In advanced Pyomo workflows, Ipopt often appears as an **inner NLP engine**, not the whole algorithm: parameter sweeps, homotopy, feasibility repair, OBBT, APPSI repeated solves, decomposition subproblems, GDP/MINLP subproblems, DAE discretizations, and direct Python callback workflows through `cyipopt`.

---

## 19.1 Parametric sweeps

### Use case

```text id="lhcq3t"
Parametric sweep =
  same NLP structure
  different numeric data
  repeated solves
  previous solution used as next start
```

Best fit:

```text id="hbyab1"
mutable Param + model reuse
APPSI for high solve count
warm-start suffixes if active set stable
```

APPSI solver interfaces are explicitly designed to be efficient for resolving the same model with small changes; Pyomo’s APPSI docs list use cases such as Benders decomposition, optimization-based bounds tightening, progressive hedging, and outer approximation, and show repeated solves after changing a mutable `Param`. ([Pyomo Documentation][1])

### Classic `SolverFactory("ipopt")` sweep

```python id="tf2s6t"
import pyomo.environ as pyo

m = pyo.ConcreteModel()

m.p = pyo.Param(initialize=1.0, mutable=True)
m.x = pyo.Var(bounds=(0, 10), initialize=1.0)
m.y = pyo.Var(bounds=(0, 10), initialize=1.0)

m.obj = pyo.Objective(expr=(m.x - m.p)**2 + (m.y - 2.0)**2)
m.c = pyo.Constraint(expr=m.x * m.y >= 1.0)

opt = pyo.SolverFactory("ipopt")
opt.options.update({
    "tol": 1e-8,
    "print_level": 0,
    "sb": "yes",
})

records = []
for p_val in [1.0, 1.1, 1.2, 1.5, 2.0]:
    m.p.set_value(p_val)

    # Previous solution remains in Var.value and acts as next primal start.
    res = opt.solve(m, tee=False)

    records.append({
        "p": p_val,
        "x": pyo.value(m.x),
        "y": pyo.value(m.y),
        "obj": pyo.value(m.obj),
        "termination": str(res.solver.termination_condition),
    })
```

### APPSI sweep

```python id="j4x3hr"
from pyomo.contrib import appsi

solver = appsi.solvers.Ipopt()
solver.ipopt_options.update({
    "tol": 1e-8,
    "print_level": 0,
})

for p_val in grid:
    m.p.set_value(float(p_val))
    res = solver.solve(m)

    if res.termination_condition != appsi.base.TerminationCondition.optimal:
        raise RuntimeError(res.termination_condition)

    solver.load_vars()
```

### Agent rules

```text id="dlqg0f"
[ ] use mutable Param for numeric data changes.
[ ] do not rebuild model if topology is fixed.
[ ] preserve Var.value between related solves.
[ ] use APPSI if solve count is high and model changes are small.
[ ] benchmark cold solve vs primal-start vs full warm-start.
[ ] tag nonconvex sweeps as local-solution trajectories, not global paths.
```

---

## 19.2 Sequential solves

### Generic sequential solve

```text id="aoml23"
Sequential solve =
  solve stage k
  load solution
  modify model/data/bounds/objective
  solve stage k+1 using previous solution
```

### Pattern: staged relaxation → full model

```python id="wps9fw"
opt = pyo.SolverFactory("ipopt")
opt.options.update({"tol": 1e-8, "print_level": 5})

# Stage 1: relaxed/easy problem
m.alpha.set_value(0.0)
res1 = opt.solve(m, tee=True)

# Stage 2: intermediate problem
m.alpha.set_value(0.5)
res2 = opt.solve(m, tee=True)

# Stage 3: full problem
m.alpha.set_value(1.0)
res3 = opt.solve(m, tee=True)
```

### Pattern: fix–solve–unfix

```python id="2e62ya"
# Stage 1: fix hard variables to plausible values.
for v in hard_vars:
    v.fix(plausible_value[v])

res = opt.solve(m, tee=True)

# Stage 2: unfix and use stage-1 solution as initialization.
for v in hard_vars:
    v.unfix()

res = opt.solve(m, tee=True)
```

### Pyomo Network `SequentialDecomposition`

```python id="gyvn9x"
from pyomo.network.decomposition import SequentialDecomposition

seq = SequentialDecomposition()
seq.options.tear_method = "Direct"
seq.options.iterLim = 20

# Requires a Pyomo Network model with Arc/Port structure and unit-level solve callbacks.
seq.run(model, function=unit_solve_function)
```

Pyomo Network provides `SequentialDecomposition`, a tool for Pyomo Network models that computes units in a logically ordered sequence and supports options such as tear sets and iteration limits. ([Pyomo Documentation][2])

### Agent rules

```text id="zs7eim"
[ ] sequential solves are algorithmic scaffolding around Ipopt, not a different Ipopt mode.
[ ] manually manage fixed status, Param updates, and suffix freshness.
[ ] use load_solutions=False if a failed stage must not overwrite current incumbent.
[ ] for process networks, distinguish generic sequential solves from Pyomo Network SequentialDecomposition.
```

---

## 19.3 Homotopy / continuation

### Use case

```text id="0ld0ds"
Homotopy / continuation =
  introduce parameter α ∈ [0,1]
  α=0 easy model
  α=1 target model
  solve increasing α sequence
  previous solution initializes next solve
```

### Algebraic blend

```python id="byefxg"
m.alpha = pyo.Param(initialize=0.0, mutable=True)

easy_expr = m.x + m.y
hard_expr = pyo.exp(m.x) + m.y**2

m.c = pyo.Constraint(
    expr=(1 - m.alpha) * easy_expr + m.alpha * hard_expr == rhs
)
```

### Continuation loop

```python id="gtcd55"
alphas = [0.0, 0.05, 0.1, 0.2, 0.35, 0.5, 0.75, 1.0]

for a in alphas:
    m.alpha.set_value(a)
    res = opt.solve(m, tee=True, load_solutions=False)

    if res.solver.termination_condition == pyo.TerminationCondition.optimal:
        m.solutions.load_from(res)
    else:
        raise RuntimeError(f"Continuation failed at alpha={a}: {res.solver.termination_condition}")
```

### Adaptive step-size continuation

```python id="q21qmr"
alpha = 0.0
step = 0.2

while alpha < 1.0:
    trial = min(1.0, alpha + step)
    m.alpha.set_value(trial)

    res = opt.solve(m, tee=False, load_solutions=False)

    if res.solver.termination_condition == pyo.TerminationCondition.optimal:
        m.solutions.load_from(res)
        alpha = trial
        step = min(0.25, 1.5 * step)
    else:
        step *= 0.5
        if step < 1e-4:
            raise RuntimeError(f"Continuation failed near alpha={trial}")
```

### Value case

```text id="2t6ihc"
Continuation helps:
  nonconvex basin tracking
  stiff nonlinear equality systems
  hard feasibility problems
  DAE initialization
  parameter transitions
  avoiding immediate restoration failure
```

### Agent rules

```text id="rrm6n4"
[ ] choose easy model with same variables/constraints where possible.
[ ] avoid changing topology during continuation.
[ ] use previous solution as next start.
[ ] use small α steps near active-set changes.
[ ] do not claim global optimality from a continuation path.
```

---

## 19.4 Feasibility restoration workflows

### Solver-side restoration options

```python id="vhpru9"
opt.options.update({
    "expect_infeasible_problem": "yes",
    "required_infeasibility_reduction": 0.99,
    "inf_pr_output": "original",
    "print_level": 7,
})
```

### Model-side elastic slacks

```python id="57llir"
m.C = pyo.Set(initialize=list_of_constraint_ids)
m.s_pos = pyo.Var(m.C, domain=pyo.NonNegativeReals, initialize=0.0)
m.s_neg = pyo.Var(m.C, domain=pyo.NonNegativeReals, initialize=0.0)

def elastic_eq_rule(m, i):
    return original_body[i] + m.s_pos[i] - m.s_neg[i] == original_rhs[i]

m.elastic_eq = pyo.Constraint(m.C, rule=elastic_eq_rule)

rho = 1e6
m.elastic_obj = pyo.Objective(
    expr=original_objective_expr + rho * sum(m.s_pos[i] + m.s_neg[i] for i in m.C)
)
```

### Inequality relaxation

```python id="28dvmo"
# Original: body <= ub
m.s_ub = pyo.Var(m.C_UB, domain=pyo.NonNegativeReals, initialize=0.0)

m.relaxed_ub = pyo.Constraint(
    m.C_UB,
    rule=lambda m, i: body[i] <= ub[i] + m.s_ub[i],
)

m.feas_obj = pyo.Objective(expr=sum(m.s_ub[i] for i in m.C_UB))
```

### Two-stage feasibility workflow

```python id="4g2y79"
# Stage 1: minimize total violation.
m.obj.deactivate()
m.feas_obj.activate()
res = opt.solve(m, tee=True)

# Stage 2: fix or penalize slacks, restore original objective.
m.feas_obj.deactivate()
m.obj.activate()
res = opt.solve(m, tee=True)
```

### Agent rules

```text id="qt7ce0"
[ ] Ipopt restoration output is diagnostic; model-side slacks make violation explicit.
[ ] use original-scale residual reports after solve.
[ ] large slacks identify infeasible constraint families.
[ ] do not leave elastic slacks unpenalized in final model.
[ ] if slacks remain positive in final solution, report relaxed feasibility, not original feasibility.
```

Ipopt’s output docs describe local infeasibility and restoration as feasibility-oriented diagnostics, but they do not replace model-level feasibility analysis; the returned locally infeasible point can help identify problematic constraints. ([coin-or.github.io][3])

---

## 19.5 Manual warm starts

### Required suffixes

```python id="k19muz"
m.dual = pyo.Suffix(direction=pyo.Suffix.IMPORT_EXPORT)

m.ipopt_zL_out = pyo.Suffix(direction=pyo.Suffix.IMPORT)
m.ipopt_zU_out = pyo.Suffix(direction=pyo.Suffix.IMPORT)

m.ipopt_zL_in = pyo.Suffix(direction=pyo.Suffix.EXPORT)
m.ipopt_zU_in = pyo.Suffix(direction=pyo.Suffix.EXPORT)
```

Pyomo’s suffix documentation states that the NL file interface recognizes an export-style suffix named `dual` as constraint-multiplier initialization, and its Ipopt warm-start example uses `dual`, `ipopt_zL_out`, `ipopt_zU_out`, `ipopt_zL_in`, and `ipopt_zU_in`. ([Pyomo Documentation][4])

### Warm-start loop

```python id="r4xukd"
# Cold solve.
res = opt.solve(m, tee=True)

# Update related data.
m.p.set_value(new_p)

# Copy bound multiplier outputs into inputs.
m.ipopt_zL_in.update(m.ipopt_zL_out)
m.ipopt_zU_in.update(m.ipopt_zU_out)

opt.options.update({
    "warm_start_init_point": "yes",
    "warm_start_bound_push": 1e-6,
    "warm_start_mult_bound_push": 1e-6,
    "mu_init": 1e-6,
})

res = opt.solve(m, tee=True)
```

Ipopt’s `warm_start_init_point` option tells Ipopt to use provided primal and dual variable values from a previous related optimization, and Pyomo’s warm-start example copies the output lower/upper bound multipliers into the corresponding input suffixes before the second solve. ([coin-or.github.io][5])

### Agent rules

```text id="11mz4y"
[ ] warm-start only after accepted solve and loaded solution.
[ ] copy zL_out → zL_in and zU_out → zU_in exactly.
[ ] clear warm-start suffixes after structural changes.
[ ] benchmark warm start; active-set changes can make it worse.
[ ] do not combine warm_start_init_point=yes with least_square_init_primal=yes.
```

---

## 19.6 Bound tightening loops

### OBBT concept

```text id="fjat2s"
Optimization-based bound tightening (OBBT):
  for each variable x_j:
    minimize x_j subject to model constraints
    maximize x_j subject to model constraints
    update lb_j / ub_j
```

APPSI docs explicitly cite optimization-based bounds tightening as a use case where efficient repeated solves of nearly identical models are valuable. ([Pyomo Documentation][1])

### Classic OBBT skeleton

```python id="xroquj"
def obbt_variable(model, var, opt, *, tee=False):
    # Save original objective(s).
    active_objs = list(model.component_data_objects(pyo.Objective, active=True))
    for obj in active_objs:
        obj.deactivate()

    model._obbt_obj = pyo.Objective(expr=var, sense=pyo.minimize)
    res_min = opt.solve(model, tee=tee, load_solutions=True)
    lb = pyo.value(var, exception=False)

    model._obbt_obj.sense = pyo.maximize
    res_max = opt.solve(model, tee=tee, load_solutions=True)
    ub = pyo.value(var, exception=False)

    model.del_component(model._obbt_obj)

    for obj in active_objs:
        obj.activate()

    return lb, ub
```

### Safer clone-based OBBT

```python id="dft8de"
def obbt_on_clone(base_model, var_name, solver_options=None):
    m = base_model.clone()
    opt = pyo.SolverFactory("ipopt")
    if solver_options:
        opt.options.update(solver_options)

    var = m.find_component(var_name)
    active_objs = list(m.component_data_objects(pyo.Objective, active=True))
    for obj in active_objs:
        obj.deactivate()

    m.obbt_obj = pyo.Objective(expr=var, sense=pyo.minimize)
    opt.solve(m, tee=False)
    lb = pyo.value(var)

    m.obbt_obj.sense = pyo.maximize
    opt.solve(m, tee=False)
    ub = pyo.value(var)

    return lb, ub
```

### APPSI repeated OBBT concept

```python id="uii0dg"
solver = appsi.solvers.Ipopt()
solver.ipopt_options.update({"tol": 1e-7, "print_level": 0})

solver.set_instance(m)

for v in vars_to_tighten:
    m.obbt_obj.set_value(v)  # if objective built as mutable Expression pattern
    solver.set_objective(m.obbt_obj)
    res = solver.solve(m)
    solver.load_vars()
```

### Agent rules

```text id="wpj597"
[ ] OBBT with local Ipopt gives local bounds for nonconvex NLP, not global-valid bounds.
[ ] For convex NLP, local optimum can be useful as bound certificate under assumptions.
[ ] For nonconvex/global MINLP preprocessing, use global solvers or convex relaxations.
[ ] Avoid overwriting original objective permanently.
[ ] update variable bounds only when bound validity is mathematically justified.
[ ] parallelize OBBT carefully; each worker needs independent model instance.
```

---

## 19.7 NLP subproblems inside decomposition methods

### Generic decomposition pattern

```text id="k9s7w2"
outer algorithm:
  choose complicating variables / discrete decisions / cuts / parameters
  fix or update subproblem data
  solve continuous NLP with Ipopt
  extract primal/dual/cut information
  update master problem
```

### Benders-like NLP subproblem skeleton

```python id="src5y5"
def solve_nlp_subproblem(master_solution, subproblem):
    for i, val in master_solution.items():
        subproblem.y[i].fix(val)

    subproblem.dual = pyo.Suffix(direction=pyo.Suffix.IMPORT)

    opt = pyo.SolverFactory("ipopt")
    opt.options.update({"tol": 1e-8, "print_level": 0})

    res = opt.solve(subproblem, tee=False, load_solutions=False)

    if res.solver.termination_condition == pyo.TerminationCondition.optimal:
        subproblem.solutions.load_from(res)
        return {
            "objective": pyo.value(subproblem.obj),
            "duals": {
                c.name: subproblem.dual.get(c)
                for c in subproblem.component_data_objects(pyo.Constraint, active=True)
            },
        }

    raise RuntimeError(res.solver.termination_condition)
```

### Agent rules

```text id="8487yh"
[ ] fix complicating variables explicitly.
[ ] use mutable Params when values enter expressions but variables remain continuous.
[ ] import duals only after accepted solve.
[ ] validate dual sign convention before generating cuts.
[ ] treat Ipopt NLP subproblem as local unless subproblem is convex or global solve is supplied.
[ ] use APPSI for high-frequency repeated NLP subproblems.
```

---

## 19.8 NLP subproblems in GDP/MINLP algorithms

### GDP transformations to MINLP/MIP-style models

```python id="1cmxbj"
# Big-M reformulation
pyo.TransformationFactory("gdp.bigm").apply_to(m)

# Hull reformulation
pyo.TransformationFactory("gdp.hull").apply_to(m)
```

Pyomo GDP docs explain that Big-M creates a smaller transformed model with looser continuous relaxation, while Hull reformulation can be tighter but introduces extra variables and constraints; Big-M may estimate M values when variables are bounded, including for nonlinear models where finite expression bounds can be inferred. ([Pyomo Documentation][6])

### GDPopt

```python id="xhq2z8"
solver = pyo.SolverFactory("gdpopt")
res = solver.solve(
    m,
    algorithm="LOA",
    mip_solver="highs",
    nlp_solver="ipopt",
    tee=True,
)
```

GDPopt is Pyomo’s logic-based solver for nonlinear Generalized Disjunctive Programming models; it solves nonlinear GDP models using logic-based decomposition rather than first reformulating everything into a conventional MINLP. ([Pyomo Documentation][7])

### MindtPy

```python id="9b262l"
solver = pyo.SolverFactory("mindtpy")
res = solver.solve(
    m,
    strategy="OA",
    mip_solver="highs",
    nlp_solver="ipopt",
    tee=True,
)
```

MindtPy is Pyomo’s decomposition toolbox for MINLP and implements algorithms such as outer approximation; its docs emphasize decomposition into MILP and continuous NLP subproblems, and also note that some algorithms require NLP subproblems solved to global optimality, which local Ipopt does not provide for nonconvex NLPs. ([Pyomo Documentation][8])

### Agent policy

```text id="uq79hw"
Convex MINLP/GDP:
  Ipopt can be reasonable local NLP subsolver for OA/LOA, subject to convexity assumptions.

Nonconvex MINLP/GDP:
  Ipopt NLP subsolves are local.
  global guarantees require global NLP/MINLP solvers or valid relaxations.

Big-M:
  requires good variable bounds and M values.

Hull:
  tighter relaxation but larger model.

GDPopt/MindtPy:
  solver options must distinguish master MIP solver and NLP solver.
```

---

## 19.9 DAE discretization + Ipopt

### pyomo.dae model skeleton

```python id="n3evhd"
import pyomo.environ as pyo
import pyomo.dae as dae

m = pyo.ConcreteModel()

m.t = dae.ContinuousSet(bounds=(0, 10))

m.x = pyo.Var(m.t, initialize=1.0)
m.u = pyo.Var(m.t, bounds=(-1, 1), initialize=0.0)

m.dxdt = dae.DerivativeVar(m.x, wrt=m.t)

m.ode = pyo.Constraint(
    m.t,
    rule=lambda m, t: m.dxdt[t] == -m.x[t] + m.u[t],
)

m.ic = pyo.Constraint(expr=m.x[0] == 1.0)

m.obj = pyo.Objective(expr=sum(m.u[t] ** 2 for t in m.t))
```

### Finite difference discretization

```python id="z7tvfv"
pyo.TransformationFactory("dae.finite_difference").apply_to(
    m,
    nfe=100,
    wrt=m.t,
    scheme="BACKWARD",
)
```

### Collocation discretization

```python id="pt5s3p"
pyo.TransformationFactory("dae.collocation").apply_to(
    m,
    nfe=50,
    ncp=3,
    wrt=m.t,
    scheme="LAGRANGE-RADAU",
)
```

Pyomo.DAE provides finite-difference and collocation discretization transformations; these transformations discretize continuous domains and introduce algebraic equality constraints approximating derivatives/integrals at discretization points, converting the DAE/dynamic optimization model into an algebraic optimization model suitable for solvers such as Ipopt. ([Pyomo Documentation][9])

### Ipopt solve

```python id="cmt1k0"
opt = pyo.SolverFactory("ipopt")
opt.options.update({
    "tol": 1e-7,
    "max_iter": 5000,
    "linear_solver": "mumps",
})
res = opt.solve(m, tee=True)
```

### DAE performance/robustness rules

```text id="qky0vv"
[ ] initialize trajectories, not just scalar variables.
[ ] enforce initial conditions explicitly.
[ ] scale time, states, controls, and residual equations.
[ ] start with coarse nfe, then refine.
[ ] use continuation on difficult boundary conditions or parameters.
[ ] inspect restoration failures for stiff dynamics / bad discretization / inconsistent ICs.
[ ] collocation ncp/nfe controls problem size and KKT sparsity.
```

---

## 19.10 External functions and compiled callbacks

### Pyomo external function syntax

```python id="lbmx9q"
m.f_ext = pyo.ExternalFunction(
    library="/absolute/path/to/libmyfuncs.so",
    function="my_smooth_function",
)

m.obj = pyo.Objective(expr=m.f_ext(m.x, m.y))
```

Pyomo’s `ExternalFunction` represents non-algebraic functions embedded in expressions; the docs warn that a model being expressible with external functions does not imply it is solvable, and note that the ASL interface supports external functions for general nonlinear solvers only through compiled libraries using `AMPLExternalFunction`. ([Pyomo Documentation][10])

### Pyomo ASL function extension note

```bash id="me63yg"
pyomo build-extensions
```

Pyomo provides some AMPL user-defined functions through `aslfunctions`, but the docs state that these extensions must be built with `pyomo build-extensions` and the build status must be `ok`. ([Pyomo Documentation][11])

### Agent policy

```text id="9x9fv0"
Use native Pyomo algebra when possible.

Use ExternalFunction only when:
  function is smooth on all visited domains
  compiled shared library available on target platform
  derivative support is compatible with ASL/Ipopt path
  deployment path/ABI is controlled
  derivative checker passes on a small instance

Do not:
  call arbitrary Python functions on Var objects
  embed scipy/numpy black-box functions directly
  assume linear solvers accept external functions
  assume external function derivatives are automatically correct
```

---

## 19.11 Hybrid use with `cyipopt`

### When Pyomo is not the desired interface

```text id="qho5dn"
Use cyipopt when:
  direct Python callback control is required
  no algebraic Pyomo model needed
  in-memory callback solve preferred over NL-file workflow
  custom derivative/Jacobian/Hessian code exists
  tight integration with NumPy/SciPy data structures needed
  solver should be embedded in a custom algorithmic loop
```

`cyipopt` is a Python wrapper around Ipopt; its docs describe it as enabling use of Ipopt from Python, and the conda-forge page similarly identifies it as a Python wrapper around Ipopt. ([cyipopt.readthedocs.io][12])

### cyipopt problem-object skeleton

```python id="8stj0s"
import numpy as np
import cyipopt


class MyNLP:
    def objective(self, x):
        return (x[0] - 1.0) ** 2 + (x[1] - 2.0) ** 2

    def gradient(self, x):
        return np.array([
            2.0 * (x[0] - 1.0),
            2.0 * (x[1] - 2.0),
        ])

    def constraints(self, x):
        return np.array([
            x[0] * x[1],
        ])

    def jacobian(self, x):
        # flattened nonzero Jacobian values
        return np.array([
            x[1],  # dg/dx0
            x[0],  # dg/dx1
        ])

    def jacobianstructure(self):
        # row indices, col indices for nonzero Jacobian entries
        return np.array([0, 0]), np.array([0, 1])

    def hessianstructure(self):
        # lower triangular Hessian structure
        return np.array([0, 1, 1]), np.array([0, 0, 1])

    def hessian(self, x, lagrange, obj_factor):
        # Hessian of L = obj_factor*f + lagrange[0]*g
        return np.array([
            2.0 * obj_factor,      # d2/dx0dx0
            lagrange[0],           # d2/dx1dx0 from x0*x1
            2.0 * obj_factor,      # d2/dx1dx1
        ])


nlp = cyipopt.Problem(
    n=2,
    m=1,
    problem_obj=MyNLP(),
    lb=np.array([0.0, 0.0]),
    ub=np.array([10.0, 10.0]),
    cl=np.array([1.0]),
    cu=np.array([np.inf]),
)

nlp.add_option("tol", 1e-8)
nlp.add_option("mu_strategy", "adaptive")

x0 = np.array([1.0, 1.0])
x, info = nlp.solve(x0)
```

cyipopt’s docs state that the problem object implements methods such as objective, gradient, constraints, jacobian, and hessian, and that options are set through `Problem.add_option(...)`, with Ipopt option names reused. ([cyipopt.readthedocs.io][13])

### Pyomo `cyipopt` interface note

```text id="q8pqf6"
Pyomo also contains pynumero/cyipopt interface modules:
  pyomo.contrib.pynumero.interfaces.cyipopt_interface
  pyomo.contrib.pynumero.algorithms.solvers.cyipopt_solver
```

Pyomo’s `cyipopt_interface` module is documented as the Python interface to the Cythonized Ipopt solver `cyipopt`, and Pyomo’s `cyipopt_solver` docs list a `CyIpoptSolver` for `CyIpoptProblemInterface` and a `PyomoCyIpoptSolver` that operates directly on a Pyomo model. ([Pyomo Documentation][14])

### Agent rules

```text id="qkdz8j"
Pyomo SolverFactory("ipopt"):
  best for algebraic modeling, suffixes, NL-file workflow.

cyipopt:
  best for custom callback NLPs and NumPy-native algorithms.

Do not mix casually:
  Pyomo components are symbolic algebraic objects.
  cyipopt callbacks expect numeric arrays and derivative arrays.
```

---

## 19.12 Advanced workflow selection table

| Workflow                | Primary tool                          | Ipopt role                          | Main risk                         |
| ----------------------- | ------------------------------------- | ----------------------------------- | --------------------------------- |
| parametric sweep        | mutable `Param`, APPSI                | repeated local NLP solve            | stale starts/suffixes             |
| sequential solves       | manual stages, `fix`, `unfix`, Params | solve each stage                    | failed stage contaminates next    |
| homotopy                | mutable continuation parameter        | path-following local NLP            | wrong basin / step too large      |
| feasibility restoration | slacks + Ipopt restoration options    | find/diagnose feasible point        | relaxed feasibility mislabeled    |
| manual warm start       | suffixes + `warm_start_init_point`    | accelerate related NLP              | active-set change                 |
| OBBT                    | repeated min/max NLPs                 | bound subproblem solver             | local bounds in nonconvex case    |
| decomposition NLP       | APPSI / classic Ipopt                 | subproblem solver                   | local subproblem invalidates cuts |
| GDP/MINLP               | GDPopt/MindtPy + Ipopt                | NLP subsolver                       | global guarantee mismatch         |
| DAE                     | pyomo.dae + Ipopt                     | solve discretized algebraic NLP     | scaling/stiffness/discretization  |
| external functions      | compiled ASL functions + Ipopt        | evaluate non-algebraic smooth terms | derivative/deployment failure     |
| cyipopt hybrid          | cyipopt callbacks                     | direct callback optimizer           | callback derivative bugs          |

---

## 19.13 Workflow-safe solve policy

```python id="huxzc9"
from pyomo.opt import SolverStatus, TerminationCondition

def solve_ipopt_stage(model, opt, *, tee=False, load=True, stage_name="stage"):
    res = opt.solve(model, tee=tee, load_solutions=False)

    ok = (
        res.solver.status == SolverStatus.ok
        and res.solver.termination_condition == TerminationCondition.optimal
    )

    if not ok:
        raise RuntimeError(
            f"Ipopt failed in {stage_name}: "
            f"status={res.solver.status}, termination={res.solver.termination_condition}"
        )

    if load:
        model.solutions.load_from(res)

    return res
```

### Agent rules

```text id="30mizv"
[ ] load each stage only after accepted termination.
[ ] do not feed failed-stage Var.value into next stage.
[ ] clear stale suffixes after failure or structure change.
[ ] record stage name, options, parameters, and termination.
[ ] use cold-start fallback for warm-start loops.
```

---

## 19.14 Reproducibility bundle for advanced workflows

```text id="x4tova"
Record:
  model-generation code
  stage sequence / α schedule / scenario grid
  mutable parameter values
  fixed variable status per stage
  Ipopt options per stage
  solver interface used: classic / contrib / APPSI / cyipopt
  suffix usage and warm-start policy
  linear solver availability/probe
  environment.yml / conda list
  solver logs per failed stage
  final residual audit
```

### Stage record schema

```python id="08s5to"
stage_record = {
    "stage": "alpha_0.5",
    "alpha": 0.5,
    "options": dict(opt.options),
    "termination": str(res.solver.termination_condition),
    "objective": pyo.value(m.obj, exception=False),
    "max_constraint_violation": max_constraint_violation(m),
}
```

---

## 19.15 Anti-pattern catalog

```text id="4ec6mc"
BAD:
  rebuild model for every parametric point when only Params change.

GOOD:
  mutable Param + model reuse + APPSI if high-frequency.

BAD:
  use Ipopt OBBT bounds as globally valid for nonconvex MINLP.

GOOD:
  state local/convex/global conditions explicitly.

BAD:
  solve GDP/MINLP with Ipopt directly while active binary/disjunctive decisions remain.

GOOD:
  transform GDP or use GDPopt/MindtPy with appropriate master/NLP solvers.

BAD:
  use warm-start multipliers after constraints/variables changed.

GOOD:
  clear/rebuild suffixes after structure changes.

BAD:
  use DAE discretization with uninitialized trajectories.

GOOD:
  initialize state/control profiles and solve coarse-to-fine.

BAD:
  use ExternalFunction with arbitrary Python function.

GOOD:
  compiled smooth external function with derivative checks.

BAD:
  use cyipopt when the problem is already naturally algebraic Pyomo.

GOOD:
  use cyipopt for direct numeric callbacks / in-memory custom algorithms.
```

---

## 19.16 Final checklist

```text id="6f8hnq"
[ ] Identify whether the advanced workflow is repeated solve, decomposition, dynamic optimization, or direct callback optimization.
[ ] Use mutable Params for numeric data changes.
[ ] Use APPSI for high-frequency repeated same-structure solves.
[ ] Use continuation/homotopy for hard nonconvex or feasibility-sensitive transitions.
[ ] Use explicit slacks for feasibility-restoration workflows.
[ ] Use Ipopt warm-start suffixes only after accepted solves.
[ ] Clear warm-start suffixes after structural changes.
[ ] Treat OBBT with Ipopt as local unless convex/global conditions hold.
[ ] Use GDP transformations, GDPopt, or MindtPy for logic/discrete models; do not pass active discrete structure directly to Ipopt.
[ ] For MindtPy/GDPopt, distinguish MIP master solver from NLP solver.
[ ] For DAE, discretize with finite difference or collocation before Ipopt.
[ ] Initialize DAE trajectories and scale residual equations.
[ ] Use ExternalFunction only with compiled, smooth, differentiable functions.
[ ] Use cyipopt for NumPy-native callback NLPs when Pyomo is not the right front end.
[ ] Archive stage logs, parameters, options, suffix policies, and residual audits.
```

[1]: https://pyomo.readthedocs.io/en/stable/reference/topical/appsi/appsi.html?utm_source=chatgpt.com "APPSI - Pyomo Documentation 6.10.0"
[2]: https://pyomo.readthedocs.io/en/6.9.0/api/pyomo.network.decomposition.SequentialDecomposition.html?utm_source=chatgpt.com "SequentialDecomposition — Pyomo 6.9.0 documentation"
[3]: https://coin-or.github.io/Ipopt/SPECIALS.html?utm_source=chatgpt.com "Ipopt: Special Features"
[4]: https://pyomo.readthedocs.io/en/6.8.0/pyomo_modeling_components/Suffixes.html?utm_source=chatgpt.com "Suffixes — Pyomo 6.8.0 documentation"
[5]: https://coin-or.github.io/Ipopt/OPTIONS.html?utm_source=chatgpt.com "Ipopt Options"
[6]: https://pyomo.readthedocs.io/en/6.6.2/modeling_extensions/gdp/solving.html?utm_source=chatgpt.com "Solving Logic-based Models with Pyomo.GDP"
[7]: https://pyomo.readthedocs.io/en/stable/explanation/solvers/gdpopt.html?utm_source=chatgpt.com "GDPopt logic-based solver - Pyomo Documentation 6.10.0"
[8]: https://pyomo.readthedocs.io/en/6.9.5/api/pyomo.contrib.mindtpy.MindtPy.MindtPySolver.html?utm_source=chatgpt.com "MindtPySolver — Pyomo 6.9.5 documentation"
[9]: https://pyomo.readthedocs.io/en/6.8.1/_sources/explanation/modeling/dae.rst.txt?utm_source=chatgpt.com "dae.rst.txt"
[10]: https://pyomo.readthedocs.io/en/latest/api/pyomo.core.base.external.ExternalFunction.html?utm_source=chatgpt.com "ExternalFunction — Pyomo 6.10.1.dev0 documentation"
[11]: https://pyomo.readthedocs.io/en/6.9.3/explanation/modeling_utils/aslfunctions/index.html?utm_source=chatgpt.com "aslfunctions — Pyomo 6.9.3 documentation - Read the Docs"
[12]: https://cyipopt.readthedocs.io/?utm_source=chatgpt.com "Welcome to cyipopt's documentation! — cyipopt 1.7.0 ..."
[13]: https://cyipopt.readthedocs.io/_/downloads/en/latest/pdf/?utm_source=chatgpt.com "Release 1.8.0.dev0 cyipopt Developers"
[14]: https://pyomo.readthedocs.io/en/6.8.2/api/pyomo.contrib.pynumero.interfaces.cyipopt_interface.html?utm_source=chatgpt.com "cyipopt_interface — Pyomo 6.8.2 documentation"

# Ipopt Advanced — Section 20: direct Ipopt interfaces outside Pyomo

Style target: dense advanced technical catalog / agent-ready reference. 

## 20.0 Direct-interface invariant

```text id="b8wy83"
Pyomo workflow:
  algebraic model → NL writer → .nl file → ipopt executable

Direct Ipopt workflow:
  user code / modeling language → Ipopt callbacks or .nl file → Ipopt library/executable
```

Ipopt officially documents several non-Pyomo interfaces: AMPL / `.nl` executable usage, C++ TNLP, C, Fortran, Java JIpopt, and R `ipoptr`. The official interface guide explicitly states that direct code linking requires more programming effort but can be far more efficient for large problems. ([coin-or.github.io](https://coin-or.github.io/Ipopt/INTERFACES.html))

---

## 20.1 Interface selection table

| Interface                      | Primary artifact                            | Best use                                                    | Main burden                                  |
| ------------------------------ | ------------------------------------------- | ----------------------------------------------------------- | -------------------------------------------- |
| AMPL `.nl` command line        | `.nl` file + `ipopt` executable             | replay, solver isolation, AMPL/Pyomo-generated NL debugging | file workflow, AMPL/NL dependency            |
| C++ TNLP                       | subclass `Ipopt::TNLP` + `IpoptApplication` | maximum native control, compiled systems                    | implement callbacks, compile/link C++        |
| C interface                    | `IpoptProblem` + function pointers          | C systems, language bindings, thin wrappers                 | manual sparse structures, memory, callbacks  |
| Fortran interface              | Fortran wrapper over C interface            | legacy/scientific Fortran codes                             | pointer-size and array-handling details      |
| Java JIpopt                    | JNI wrapper class                           | JVM integration                                             | native library/JAR deployment                |
| R `ipoptr`                     | R function interface                        | statistical/R workflows                                     | R package and callback conventions           |
| `cyipopt`                      | Python Cython wrapper                       | NumPy/SciPy callback NLPs                                   | callback derivatives, direct-array model     |
| Pyomo `SolverFactory("ipopt")` | `.nl` via Pyomo                             | algebraic modeling                                          | file-based solve path, less callback control |

---

## 20.2 When direct interfaces beat Pyomo

```text id="kgk72u"
Choose direct Ipopt when:
  tight callback control required
  custom derivative code already exists
  exact sparse Jacobian/Hessian structures hand-coded
  avoid file-based .nl write/read overhead
  embed solver in C/C++/Fortran/Java/R/Python-native system
  use custom memory/data layout
  integrate with simulation kernels in compiled code
  intermediate_callback must control termination/telemetry
  many solves where callback overhead < NL-file overhead
  Pyomo expression system is not the desired abstraction
```

Direct interfaces require implementing both the problem representation and an executable/solve driver; Ipopt calls back into user code for objective, constraints, Jacobian, and Hessian data. The C++ guide says users implement a `TNLP` subclass and pass it to Ipopt through `IpoptApplication`; the C interface uses `CreateIpoptProblem`, callback function pointers, option setters, `IpoptSolve`, and `FreeIpoptProblem`. ([coin-or.github.io](https://coin-or.github.io/Ipopt/INTERFACES.html))

### Do **not** choose direct interfaces when

```text id="kuxhqp"
Do not choose direct Ipopt when:
  algebraic model clarity is primary
  model structure changes frequently
  symbolic expression generation is valuable
  automatic derivative generation is preferred
  suffix/results integration through Pyomo is enough
  file-based overhead is negligible relative to solve time
  agent cannot guarantee derivative correctness
  deployment team cannot maintain compiled bindings
```

---

## 20.3 AMPL `.nl` command-line usage

### Direct `.nl` solve

```bash id="n2gnty"
ipopt mytoy
```

### Show AMPL-interface options

```bash id="7243un"
ipopt -=
```

### Print detailed options

```bash id="8kt7n4"
ipopt mytoy 'print_options_documentation yes'
```

### Inline options

```bash id="p9pfbm"
ipopt mytoy 'max_iter 2 print_level 4'
```

### `ipopt.opt`

```text id="j515h0"
# ipopt.opt
tol 1e-8
max_iter 500
linear_solver mumps
print_user_options yes
```

Ipopt’s interface guide says `.nl` files can be solved directly from the command line; it shows `ipopt mytoy`, `ipopt -=`, `ipopt mytoy 'print_options_documentation yes'`, and inline option strings like `ipopt mytoy 'max_iter 2 print_level 4'`. It also states that many options can be collected in an automatically read `ipopt.opt` file. ([coin-or.github.io](https://coin-or.github.io/Ipopt/INTERFACES.html))

### Pyomo-generated `.nl` replay

```python id="sn4djk"
import pyomo.environ as pyo

opt = pyo.SolverFactory("ipopt")
res = opt.solve(
    model,
    tee=True,
    keepfiles=True,
    symbolic_solver_labels=True,
)
```

Then inspect printed temp-file paths and replay:

```bash id="77pmrb"
ipopt /path/to/model.nl -AMPL
```

### Value case

```text id="b5t9h3"
Use .nl command-line replay to:
  isolate solver from Pyomo model construction
  reproduce a failing solve outside Python
  test option-file behavior
  archive solver artifact packages
  validate installed executable and linear solver
  compare Pyomo interface versus raw Ipopt behavior
```

---

## 20.4 C++ TNLP interface

### Conceptual structure

```text id="p8jmgs"
class MyNLP : public Ipopt::TNLP
  get_nlp_info
  get_bounds_info
  get_starting_point
  eval_f
  eval_grad_f
  eval_g
  eval_jac_g
  eval_h
  finalize_solution
```

Ipopt’s C++ interface requires creating a class inheriting from the pure virtual `Ipopt::TNLP` base class; the main executable calls Ipopt through `Ipopt::IpoptApplication`. The official guide says headers are installed under `$PREFIX/include/coin-or` after installation. ([coin-or.github.io](https://coin-or.github.io/Ipopt/INTERFACES.html))

### C++ skeleton

```cpp id="m1chft"
// conceptual C++ skeleton; compile flags depend on Ipopt installation
#include "IpTNLP.hpp"
#include "IpIpoptApplication.hpp"

using namespace Ipopt;

class MyNLP : public TNLP {
public:
  bool get_nlp_info(
      Index& n,
      Index& m,
      Index& nnz_jac_g,
      Index& nnz_h_lag,
      IndexStyleEnum& index_style
  ) override;

  bool get_bounds_info(
      Index n,
      Number* x_l,
      Number* x_u,
      Index m,
      Number* g_l,
      Number* g_u
  ) override;

  bool get_starting_point(
      Index n,
      bool init_x,
      Number* x,
      bool init_z,
      Number* z_L,
      Number* z_U,
      Index m,
      bool init_lambda,
      Number* lambda
  ) override;

  bool eval_f(Index n, const Number* x, bool new_x, Number& obj_value) override;
  bool eval_grad_f(Index n, const Number* x, bool new_x, Number* grad_f) override;
  bool eval_g(Index n, const Number* x, bool new_x, Index m, Number* g) override;

  bool eval_jac_g(
      Index n,
      const Number* x,
      bool new_x,
      Index m,
      Index nele_jac,
      Index* iRow,
      Index* jCol,
      Number* values
  ) override;

  bool eval_h(
      Index n,
      const Number* x,
      bool new_x,
      Number obj_factor,
      Index m,
      const Number* lambda,
      bool new_lambda,
      Index nele_hess,
      Index* iRow,
      Index* jCol,
      Number* values
  ) override;

  void finalize_solution(
      SolverReturn status,
      Index n,
      const Number* x,
      const Number* z_L,
      const Number* z_U,
      Index m,
      const Number* g,
      const Number* lambda,
      Number obj_value,
      const IpoptData* ip_data,
      IpoptCalculatedQuantities* ip_cq
  ) override;
};

int main() {
  SmartPtr<TNLP> nlp = new MyNLP();
  SmartPtr<IpoptApplication> app = IpoptApplicationFactory();

  app->Options()->SetNumericValue("tol", 1e-8);
  app->Options()->SetStringValue("linear_solver", "mumps");

  ApplicationReturnStatus status = app->Initialize();
  if (status != Solve_Succeeded) {
    return static_cast<int>(status);
  }

  status = app->OptimizeTNLP(nlp);
  return static_cast<int>(status);
}
```

### Sparse Jacobian/Hessian callback contract

```text id="qlziv2"
eval_jac_g:
  first call:
    values == NULL
    fill iRow / jCol sparsity structure
  later calls:
    iRow == NULL and jCol == NULL
    fill values in same order

eval_h:
  first call:
    values == NULL
    fill lower-triangular Hessian structure
  later calls:
    fill Hessian-of-Lagrangian values:
      obj_factor * ∇²f + Σ λ_i ∇²g_i
```

The C++ interface guide says the Jacobian structure arrays only need to be filled once; later calls fill numeric values in the same order. For the Hessian, Ipopt requests either sparsity structure or values, and the Hessian used is `σ_f ∇²f(x) + Σ λ_i ∇²g_i(x)`. ([coin-or.github.io](https://coin-or.github.io/Ipopt/INTERFACES.html))

### Intermediate callback

```cpp id="k9sbth"
bool MyNLP::intermediate_callback(
    AlgorithmMode mode,
    Index iter,
    Number obj_value,
    Number inf_pr,
    Number inf_du,
    Number mu,
    Number d_norm,
    Number regularization_size,
    Number alpha_du,
    Number alpha_pr,
    Index ls_trials,
    const IpoptData* ip_data,
    IpoptCalculatedQuantities* ip_cq
) {
  // return false to terminate with User_Requested_Stop
  return true;
}
```

Ipopt’s C++ `intermediate_callback` provides iteration-level values such as mode, iteration number, objective, infeasibilities, barrier parameter, step norms, regularization, step sizes, and line-search trials; returning false terminates the solve with `User_Requested_Stop`. ([coin-or.github.io](https://coin-or.github.io/Ipopt/INTERFACES.html))

### Agent rules

```text id="ktzgoa"
[ ] implement sparse structures once and values in identical order.
[ ] use C_STYLE or FORTRAN_STYLE consistently.
[ ] return false on evaluation failure, not NaN/Inf values.
[ ] cache only when new_x/new_lambda semantics are respected.
[ ] run derivative_test before trusting callbacks.
[ ] prefer exact Hessian only when implemented correctly.
[ ] use limited-memory if Hessian is unavailable.
```

---

## 20.5 C interface

### Conceptual flow

```text id="6lpn71"
CreateIpoptProblem(...)
AddIpoptStrOption / AddIpoptNumOption / AddIpoptIntOption
IpoptSolve(...)
FreeIpoptProblem(...)
```

The C interface is declared in `IpStdCInterface.h` under `$PREFIX/include/coin-or`; users create an `IpoptProblem` via `CreateIpoptProblem`, set options using `AddIpoptStrOption`, `AddIpoptNumOption`, and `AddIpoptIntOption`, call `IpoptSolve`, then call `FreeIpoptProblem` to release internal memory. The C problem object stores dimensions, bounds, derivative nonzero information, and function pointers for objective/constraint/derivative callbacks. ([coin-or.github.io](https://coin-or.github.io/Ipopt/INTERFACES.html))

### C callback signatures: conceptual

```c id="ekxbvc"
// conceptual signatures; use IpStdCInterface.h for exact typedefs
Bool eval_f(Index n, Number* x, Bool new_x, Number* obj_value, UserDataPtr user_data);

Bool eval_grad_f(Index n, Number* x, Bool new_x, Number* grad_f, UserDataPtr user_data);

Bool eval_g(Index n, Number* x, Bool new_x, Index m, Number* g, UserDataPtr user_data);

Bool eval_jac_g(
    Index n,
    Number* x,
    Bool new_x,
    Index m,
    Index nele_jac,
    Index* iRow,
    Index* jCol,
    Number* values,
    UserDataPtr user_data
);

Bool eval_h(
    Index n,
    Number* x,
    Bool new_x,
    Number obj_factor,
    Index m,
    Number* lambda,
    Bool new_lambda,
    Index nele_hess,
    Index* iRow,
    Index* jCol,
    Number* values,
    UserDataPtr user_data
);
```

### C solve skeleton

```c id="izilt2"
// conceptual C skeleton; include exact headers and types from IpStdCInterface.h
#include "IpStdCInterface.h"

int main(void) {
  ipindex n = 4;
  ipindex m = 2;

  ipnumber x_L[4] = {1.0, 1.0, 1.0, 1.0};
  ipnumber x_U[4] = {5.0, 5.0, 5.0, 5.0};

  ipnumber g_L[2] = {25.0, 40.0};
  ipnumber g_U[2] = {2e19, 40.0};

  ipindex nele_jac = 8;
  ipindex nele_hess = 10;

  IpoptProblem prob = CreateIpoptProblem(
      n,
      x_L,
      x_U,
      m,
      g_L,
      g_U,
      nele_jac,
      nele_hess,
      0,          // C_STYLE
      eval_f,
      eval_g,
      eval_grad_f,
      eval_jac_g,
      eval_h
  );

  AddIpoptNumOption(prob, "tol", 1e-8);
  AddIpoptStrOption(prob, "linear_solver", "mumps");

  ipnumber x[4] = {1.0, 5.0, 5.0, 1.0};
  ipnumber mult_g[2];
  ipnumber mult_x_L[4];
  ipnumber mult_x_U[4];
  ipnumber obj;

  enum ApplicationReturnStatus status = IpoptSolve(
      prob,
      x,
      NULL,       // g; optional depending on API usage
      &obj,
      mult_g,
      mult_x_L,
      mult_x_U,
      NULL        // user_data
  );

  FreeIpoptProblem(prob);
  return (int)status;
}
```

### C bound/infinity semantics

`CreateIpoptProblem` copies variable/constraint bounds internally. Bounds at or below `nlp_lower_bound_inf` are treated as negative infinity; bounds at or above `nlp_upper_bound_inf` are treated as positive infinity. The same C interface reference also documents the intermediate callback state values and methods to retrieve current primal/dual iterate data during an intermediate callback. ([coin-or.github.io](https://coin-or.github.io/Ipopt/IpStdCInterface_8h.html))

### Agent rules

```text id="ua1kfv"
[ ] use IpStdCInterface.h as source of truth for typedefs and prototypes.
[ ] allocate all arrays with correct lengths.
[ ] keep callback data in UserDataPtr, not globals where avoidable.
[ ] fill sparse structures once, values later in same order.
[ ] call FreeIpoptProblem exactly once per created problem.
[ ] use AddIpopt*Option typed setters; do not stringify all options manually.
```

---

## 20.6 Fortran interface

### Conceptual flow

```text id="fk69qz"
IPCREATE
IPADD* option routines
IPSOLVE
IPFREE / cleanup equivalent
EV_* callbacks
```

The Fortran interface is essentially a wrapper around the C interface; its functions correspond one-to-one to the C and C++ interfaces. Special details include declaring the `IpoptProblem` handle large enough to hold a pointer on 64-bit systems, passing all arrays including dual-variable arrays to `IPSOLVE`, and setting `IERR=0` unless an evaluation error occurs. ([coin-or.github.io](https://coin-or.github.io/Ipopt/INTERFACES.html))

### Fortran callback/error policy

```text id="e4vtv7"
EV_* callbacks:
  evaluate objective / gradient / constraints / Jacobian / Hessian

IERR:
  0     success
  nonzero evaluation failure

IDAT / DAT:
  integer and double arrays passed unchanged through callbacks
  equivalent to user-data channel
```

### Agent rules

```text id="e7ezyf"
[ ] use INTEGER*8 or appropriate kind for IpoptProblem handle on 64-bit platforms.
[ ] pass every required primal/dual array to IPSOLVE.
[ ] use IERR to report evaluation failure.
[ ] use IDAT/DAT for private callback data.
[ ] confirm compiler/runtime linkage to C++ Ipopt library.
```

---

## 20.7 Java JIpopt interface

### Deployment surface

```text id="ob8cyp"
Java class:
  extends org.coinor.Ipopt

Native dependency:
  compiled Ipopt DLL/shared library

JAR:
  org.coinor.ipopt.jar
  installed under $PREFIX/share/java if Java interface built
```

The Ipopt Java interface offers an abstract base class with methods to specify the NLP, set options, solve, and retrieve a solution. If the Ipopt build includes Java support, `org.coinor.ipopt.jar` is installed in `$PREFIX/share/java`, and users must put it on the Java classpath. ([coin-or.github.io](https://coin-or.github.io/Ipopt/INTERFACES.html))

### Java conceptual skeleton

```java id="5p0g28"
// conceptual Java skeleton
import org.coinor.Ipopt;

public class MyNLP extends Ipopt {
    private int n = 4;
    private int m = 2;
    private int nele_jac = 8;
    private int nele_hess = 10;

    public MyNLP() {
        create(n, m, nele_jac, nele_hess, Ipopt.C_STYLE);
    }

    protected boolean get_bounds_info(
        int n,
        double[] x_L,
        double[] x_U,
        int m,
        double[] g_L,
        double[] g_U
    ) {
        for (int i = 0; i < n; i++) {
            x_L[i] = 1.0;
            x_U[i] = 5.0;
        }
        g_L[0] = 25.0;
        g_U[0] = 2e19;
        g_L[1] = 40.0;
        g_U[1] = 40.0;
        return true;
    }

    protected boolean get_starting_point(
        int n,
        boolean init_x,
        double[] x,
        boolean init_z,
        double[] z_L,
        double[] z_U,
        int m,
        boolean init_lambda,
        double[] lambda
    ) {
        x[0] = 1.0;
        x[1] = 5.0;
        x[2] = 5.0;
        x[3] = 1.0;
        return true;
    }

    // implement eval_f, eval_grad_f, eval_g, eval_jac_g, eval_h...
}
```

The Java interface guide says a user class extends `Ipopt`, calls `create(n, m, nele_jac, nele_hess, index_style)`, and implements methods such as `get_bounds_info`, `get_starting_point`, and evaluation callbacks analogous to the C++ interface. ([coin-or.github.io](https://coin-or.github.io/Ipopt/INTERFACES.html))

### Agent rules

```text id="sxg1dt"
[ ] verify JAR exists and is on classpath.
[ ] verify native shared library is loadable by JVM.
[ ] subclass Ipopt and implement abstract evaluation methods.
[ ] call create(...) before OptimizeNLP().
[ ] call dispose() or equivalent cleanup when finished.
[ ] do not expect pure-Java deployment; JNI/native library is required.
```

The Java source itself describes JIpopt as a JNI hook around the C++ interface and says it requires a natively compiled DLL/shared library; the class should be subclassed and native memory should be disposed when done. ([github.com](https://github.com/coin-or/Ipopt/blob/stable/3.14/src/Interfaces/Ipopt.java))

---

## 20.8 R interface `ipoptr`

### Conceptual R usage

```r id="kqpdgo"
library(ipoptr)

eval_f <- function(x) {
  x[1] * x[4] * (x[1] + x[2] + x[3]) + x[3]
}

eval_grad_f <- function(x) {
  c(
    x[4] * (2 * x[1] + x[2] + x[3]),
    x[1] * x[4],
    x[1] * x[4] + 1,
    x[1] * (x[1] + x[2] + x[3])
  )
}

eval_g <- function(x) {
  c(
    x[1] * x[2] * x[3] * x[4],
    sum(x^2)
  )
}

# eval_jac_g, eval_h, bounds, and options omitted in this conceptual sketch.
```

The official Ipopt interface guide describes the R interface `ipoptr` as an R package that offers an `ipoptr` function taking an NLP specification, a starting point, and Ipopt options as input, and returning run information such as status/message and a solution point. ([coin-or.github.io](https://coin-or.github.io/Ipopt/INTERFACES.html))

### Agent rules

```text id="qm1h59"
[ ] use R interface when R-native workflow matters.
[ ] provide analytic gradients/Jacobians/Hessians where possible.
[ ] benchmark callback overhead for large-scale NLPs.
[ ] avoid R loops in callback hotspots if vectorization/compiled code is possible.
```

---

## 20.9 `cyipopt` Python wrapper

### Install

```bash id="400h5z"
conda install -c conda-forge cyipopt
```

cyipopt is a Cython Python wrapper around Ipopt; its docs say conda-forge provides the easiest cross-platform install path and that conda-forge supplies a basic Ipopt build suitable for many use cases, while source builds are needed for customized Ipopt installations. ([cyipopt.readthedocs.io](https://cyipopt.readthedocs.io/_/downloads/en/stable/pdf/))

### Problem-object skeleton

```python id="oxafzz"
import numpy as np
import cyipopt


class HS071:
    def objective(self, x):
        return x[0] * x[3] * (x[0] + x[1] + x[2]) + x[2]

    def gradient(self, x):
        return np.array([
            x[0] * x[3] + x[3] * (x[0] + x[1] + x[2]),
            x[0] * x[3],
            x[0] * x[3] + 1.0,
            x[0] * (x[0] + x[1] + x[2]),
        ])

    def constraints(self, x):
        return np.array([
            x[0] * x[1] * x[2] * x[3],
            x[0]**2 + x[1]**2 + x[2]**2 + x[3]**2,
        ])

    def jacobianstructure(self):
        rows = np.array([0, 0, 0, 0, 1, 1, 1, 1])
        cols = np.array([0, 1, 2, 3, 0, 1, 2, 3])
        return rows, cols

    def jacobian(self, x):
        return np.array([
            x[1] * x[2] * x[3],
            x[0] * x[2] * x[3],
            x[0] * x[1] * x[3],
            x[0] * x[1] * x[2],
            2.0 * x[0],
            2.0 * x[1],
            2.0 * x[2],
            2.0 * x[3],
        ])

    def hessianstructure(self):
        # lower triangular Hessian positions
        rows, cols = np.tril_indices(4)
        return rows, cols

    def hessian(self, x, lagrange, obj_factor):
        # For production, implement exact lower-triangle Hessian of:
        # obj_factor * f(x) + lagrange[0] * g0(x) + lagrange[1] * g1(x)
        H = np.zeros((4, 4))

        # Fill H here.
        rows, cols = self.hessianstructure()
        return H[rows, cols]


nlp = cyipopt.Problem(
    n=4,
    m=2,
    problem_obj=HS071(),
    lb=np.array([1.0, 1.0, 1.0, 1.0]),
    ub=np.array([5.0, 5.0, 5.0, 5.0]),
    cl=np.array([25.0, 40.0]),
    cu=np.array([2.0e19, 40.0]),
)

nlp.add_option("tol", 1e-8)
nlp.add_option("linear_solver", "mumps")

x0 = np.array([1.0, 5.0, 5.0, 1.0])
x, info = nlp.solve(x0)
```

cyipopt wraps the same continuous NLP structure as Ipopt: variables with bounds, constraint functions with lower/upper bounds, equality constraints by equal lower/upper constraint bounds, and Ipopt options set through wrapper methods. ([cyipopt.readthedocs.io](https://cyipopt.readthedocs.io/_/downloads/en/stable/pdf/))

### SciPy-like route

```python id="1u1sx6"
from cyipopt import minimize_ipopt

res = minimize_ipopt(
    fun,
    x0,
    jac=grad,
    hess=hess,
    bounds=bounds,
    constraints=constraints,
    options={"tol": 1e-8},
)
```

### Agent rules

```text id="liwgcu"
[ ] use cyipopt for NumPy-native callback NLPs.
[ ] provide sparse Jacobian structure when possible.
[ ] provide exact Hessian or choose limited-memory.
[ ] avoid Python callback bottlenecks in huge NLPs.
[ ] use vectorized/compiled callback kernels for performance.
[ ] run derivative checker-equivalent validation before deployment.
```

---

## 20.10 Pyomo versus cyipopt versus direct C++ decision matrix

| Requirement                                      | Best front door                                |
| ------------------------------------------------ | ---------------------------------------------- |
| algebraic modeling, sets, Params, Suffixes       | Pyomo + Ipopt                                  |
| generated `.nl` replay/debug                     | command-line `ipopt model.nl`                  |
| maximum compiled performance/control             | C++ TNLP                                       |
| C library integration                            | C interface                                    |
| legacy Fortran codebase                          | Fortran interface                              |
| JVM application                                  | Java JIpopt                                    |
| R analytics/statistical workflow                 | `ipoptr`                                       |
| NumPy/SciPy callback model                       | `cyipopt`                                      |
| custom sparse derivative code in Python          | `cyipopt`                                      |
| dynamic model algebra with many components       | Pyomo                                          |
| callback telemetry / early stop inside iteration | direct C++/C/Cython or C intermediate callback |

---

## 20.11 Direct-interface derivative contract

```text id="ebj3xd"
Must provide:
  n, m
  x_L, x_U
  g_L, g_U
  x0
  f(x)
  ∇f(x)
  g(x)
  sparse structure of ∂g/∂x
  values of ∂g/∂x
  sparse lower-triangular structure of ∇²L
  values of ∇²L
```

### Hessian of Lagrangian

```text id="7q70qy"
∇²L(x, λ, σ_f) =
  σ_f ∇²f(x) + Σ_i λ_i ∇²g_i(x)
```

Ipopt’s C++ interface documentation states that the Hessian callback must return the Hessian of the Lagrangian, using objective factor `σ_f` and constraint multipliers `λ`, and that the Jacobian/Hessian callbacks request sparsity structure separately from values. ([coin-or.github.io](https://coin-or.github.io/Ipopt/INTERFACES.html))

### If Hessian unavailable

```text id="757sl7"
Option:
  hessian_approximation limited-memory

Consequence:
  no exact Hessian callback needed in many interfaces
  more iterations / weaker local convergence possible
```

---

## 20.12 Direct-interface option deployment

### C++ style

```cpp id="a3gtki"
app->Options()->SetNumericValue("tol", 1e-8);
app->Options()->SetIntegerValue("max_iter", 1000);
app->Options()->SetStringValue("linear_solver", "mumps");
```

### C style

```c id="udprf9"
AddIpoptNumOption(prob, "tol", 1e-8);
AddIpoptIntOption(prob, "max_iter", 1000);
AddIpoptStrOption(prob, "linear_solver", "mumps");
```

### cyipopt style

```python id="qzu7u2"
nlp.add_option("tol", 1e-8)
nlp.add_option("max_iter", 1000)
nlp.add_option("linear_solver", "mumps")
```

### `.nl` command line

```bash id="n12buh"
ipopt model.nl -AMPL tol=1e-8 max_iter=1000 linear_solver=mumps
```

### `ipopt.opt`

```text id="layi90"
tol 1e-8
max_iter 1000
linear_solver mumps
```

---

## 20.13 Build and deployment considerations

### Headers / libraries

```text id="1zzl58"
C++ headers:
  $PREFIX/include/coin-or

C interface header:
  $PREFIX/include/coin-or/IpStdCInterface.h

Libraries:
  libipopt + dependent linear solvers + BLAS/LAPACK + C++ runtime
```

Ipopt’s C++ guide states headers are installed in `$PREFIX/include/coin-or`, and the C guide identifies `IpStdCInterface.h` as the C interface header in that include tree. ([coin-or.github.io](https://coin-or.github.io/Ipopt/INTERFACES.html))

### pkg-config probe

```bash id="3yaalz"
pkg-config --libs --cflags ipopt
```

cyipopt’s source-install docs state that, on Linux/macOS source builds, `pkg-config --libs --cflags ipopt` should return valid results, and that custom/source installs may require setting library paths such as `LD_LIBRARY_PATH`. ([cyipopt.readthedocs.io](https://cyipopt.readthedocs.io/_/downloads/en/stable/pdf/))

### Conceptual compile command

```bash id="zvl6bo"
g++ -O3 my_nlp.cpp -o my_nlp $(pkg-config --cflags --libs ipopt)
```

### Runtime library path

```bash id="dz107h"
export LD_LIBRARY_PATH=/path/to/ipopt/lib:$LD_LIBRARY_PATH      # Linux
export DYLD_LIBRARY_PATH=/path/to/ipopt/lib:$DYLD_LIBRARY_PATH  # macOS, subject to SIP
```

### Windows notes

```text id="zzagyy"
Windows direct linking:
  match compiler ABI
  ensure Ipopt DLL and dependent DLLs are discoverable
  ensure Python extension compiler matches Python ABI for cyipopt
  prefer conda-forge binaries unless custom Ipopt build required
```

cyipopt’s Windows source-install docs state that building Python C extensions needs an appropriate C compiler such as Visual C++ for modern Python versions; they also discuss obtaining Ipopt binaries or building Ipopt from source. ([cyipopt.readthedocs.io](https://cyipopt.readthedocs.io/_/downloads/en/stable/pdf/))

---

## 20.14 Direct-interface memory and lifecycle rules

```text id="sndhl6"
C++:
  use SmartPtr where available
  manage TNLP object lifetime
  avoid dangling pointers to problem data

C:
  CreateIpoptProblem
  AddIpopt*Option
  IpoptSolve
  FreeIpoptProblem

Java:
  create(...)
  OptimizeNLP()
  dispose()

cyipopt:
  Problem object owns Ipopt problem wrapper
  Python object lifetime controls native resources
```

The C interface docs explicitly say `FreeIpoptProblem` should be called after everything is done to release internal memory; the Java interface source says native memory should be disposed when finished. ([coin-or.github.io](https://coin-or.github.io/Ipopt/INTERFACES.html))

---

## 20.15 Direct-interface debugging controls

### Derivative checker

```text id="ywi9qy"
derivative_test first-order
derivative_test_print_all yes
max_iter 0
```

### NaN/Inf derivative check

```text id="yotipk"
check_derivatives_for_naninf yes
print_level 7
```

### C++ / C / cyipopt rule

```text id="l63h37"
Direct interface without derivative checker =
  high risk of silent wrong derivative structure/value bugs.
```

Ipopt’s derivative checker uses finite differences at the starting point and can test first- or second-order derivatives before optimization starts. It is especially valuable for direct callback implementations where derivative code is hand-written. ([coin-or.github.io](https://coin-or.github.io/Ipopt/SPECIALS.html))

---

## 20.16 Intermediate callback use cases

```text id="t7kl48"
Use intermediate callback for:
  custom telemetry
  early stopping
  live progress streaming
  trust-region or outer-loop coordination
  current iterate inspection
  restoration-mode detection
```

### C interface state values

```text id="77vepr"
alg_mod:
  0 regular
  1 restoration

iter_count
obj_value
inf_pr
inf_du
mu
d_norm
regularization_size
alpha_du
alpha_pr
ls_trials
user_data
```

The C interface defines `Intermediate_CB` with iteration count, objective value, primal/dual infeasibilities, barrier parameter, step norm, Hessian regularization size, step lengths, line-search trials, and user data; returning false terminates optimization. ([coin-or.github.io](https://coin-or.github.io/Ipopt/IpStdCInterface_8h.html))

---

## 20.17 Direct-interface anti-patterns

```text id="m1a2cp"
BAD:
  use direct interface because it "seems faster" without profiling Pyomo NL write overhead.

GOOD:
  profile Pyomo build/write/solve times first.

BAD:
  implement Jacobian dense when model is sparse.

GOOD:
  declare exact sparse structure.

BAD:
  return NaN when function evaluation fails.

GOOD:
  return false / nonzero IERR from callback.

BAD:
  use inconsistent index bases.

GOOD:
  choose C_STYLE or FORTRAN_STYLE and use consistently.

BAD:
  forget obj_factor and lambda in Hessian callback.

GOOD:
  eval_h returns Hessian of Lagrangian.

BAD:
  skip derivative checker.

GOOD:
  first-order then second-order derivative tests on small instances.

BAD:
  assume conda ipopt package includes Java/R/Fortran interfaces.

GOOD:
  inspect installed build artifacts and compile required interfaces explicitly.

BAD:
  ship HSL/Pardiso-linked direct binary without license review.

GOOD:
  document third-party linear-solver dependencies and redistribution rights.
```

---

## 20.18 Interface-specific best-practice checklist

```text id="52gkax"
AMPL .nl:
  [ ] keep .nl + ipopt.opt + log together.
  [ ] replay failures outside Pyomo.
  [ ] use ipopt -= and --print-options for installed executable.

C++ TNLP:
  [ ] subclass TNLP.
  [ ] implement all required virtual callbacks.
  [ ] use sparse triplet structures.
  [ ] use SmartPtr / IpoptApplication.
  [ ] run derivative checker.

C:
  [ ] use IpStdCInterface.h.
  [ ] create IpoptProblem with dimensions/bounds/callbacks.
  [ ] use typed option setters.
  [ ] pass UserDataPtr for problem data.
  [ ] call FreeIpoptProblem.

Fortran:
  [ ] size problem handle for pointer width.
  [ ] pass all required arrays to IPSOLVE.
  [ ] use IDAT/DAT for private data.
  [ ] use IERR correctly.

Java:
  [ ] verify native Ipopt library and JAR.
  [ ] subclass org.coinor.Ipopt.
  [ ] call create before solve.
  [ ] dispose native resources.

R:
  [ ] use ipoptr for R-native NLP workflows.
  [ ] vectorize callbacks where possible.
  [ ] validate sign/derivative conventions.

cyipopt:
  [ ] install with conda-forge or custom Ipopt if needed.
  [ ] implement objective/gradient/constraints/Jacobian/Hessian.
  [ ] provide sparse structures.
  [ ] use add_option.
  [ ] benchmark callback overhead.
```

---

## 20.19 Migration guide: Pyomo → direct interface

```text id="u3kiii"
Step 1:
  profile Pyomo:
    build time
    NL writer time
    Ipopt solve time

Step 2:
  export .nl with symbolic labels:
    verify problem formulation

Step 3:
  identify bottleneck:
    Python model construction?
    NL file generation?
    Ipopt linear algebra?
    derivative evaluation?

Step 4:
  if NL/write overhead dominates:
    APPSI / model reuse first

Step 5:
  if callback/data-layout control needed:
    cyipopt or C++ TNLP

Step 6:
  port functions:
    f, grad_f, g, jac_g, hess_lag

Step 7:
  validate:
    finite evaluation
    derivative checker
    compare objective/constraints to Pyomo at same x
    compare solution on small instances

Step 8:
  benchmark:
    direct interface versus Pyomo on representative model family
```

---

## 20.20 Final checklist

```text id="8wku25"
[ ] Choose direct interface only for clear performance/control/deployment reason.
[ ] Use AMPL .nl command line for replay and solver isolation.
[ ] Use C++ TNLP for maximum compiled control.
[ ] Use C interface for language bindings and C systems.
[ ] Use Fortran interface for legacy scientific Fortran codes.
[ ] Use Java JIpopt only with native library/JAR deployment verified.
[ ] Use R ipoptr for R-native workflows.
[ ] Use cyipopt for NumPy/SciPy-style direct Python callbacks.
[ ] Implement exact sparse Jacobian and Hessian structures correctly.
[ ] Return evaluation-failure signals instead of NaN/Inf.
[ ] Run derivative tests on small instances.
[ ] Validate direct-interface results against Pyomo/AMPL prototype.
[ ] Use pkg-config or installation-provided compile flags.
[ ] Document compiler, ABI, BLAS/LAPACK, linear solver, and license dependencies.
[ ] Benchmark before replacing Pyomo.
```

# Ipopt Advanced — Section 21: reproducibility and environment capture

Style target: dense advanced technical catalog / agent-ready reference. 

## 21.0 Reproducibility invariant

```text id="xfkzvo"
A reproducible Pyomo + Ipopt run captures:

1. model source
2. model input data
3. solver executable identity
4. Ipopt option surface
5. exact option profile used
6. Python / Pyomo / package environment
7. platform and numerical libraries
8. random seeds / generation seeds
9. solver log
10. result status / termination / objective / residuals / solve time
```

**Agent rule:** a stored objective value without environment, options, linear solver, and termination condition is not a reproducible optimization result. Ipopt’s option docs explicitly recommend printing option documentation for the installed executable and warn that some option availability/defaults, especially around linear solvers, depend on build configuration. ([COIN-OR Documentation][1])

---

## 21.1 Required run metadata

```text id="twdoyy"
Run identity:
  run_id
  timestamp_utc
  git_commit
  git_dirty
  hostname
  user / job id
  working directory
  random seed(s)
  scenario id / data hash

Python stack:
  Python executable
  Python version
  Pyomo version
  NumPy/SciPy versions if used
  cyipopt version if used

Ipopt stack:
  ipopt executable path
  ipopt -v output
  ipopt --print-options output
  ipopt -= output
  linear_solver selected
  linear_solver availability probe
  BLAS/LAPACK variant
  thread env vars

Solver policy:
  option dictionary
  ipopt.opt contents if used
  load_solutions policy
  acceptable termination policy
  warm-start suffix policy
```

---

## 21.2 Environment capture: conda / micromamba

### History-only environment spec

```bash id="9m7np1"
conda env export --from-history > environment.from-history.yml
```

Purpose:

```text id="04mwll"
human-readable requested packages
portable across platforms
does not include every transitive dependency
good for documentation
not sufficient alone for bit-level reproduction
```

### Full environment spec

```bash id="j98lsx"
conda env export > environment.full.yml
```

Purpose:

```text id="15iaep"
captures transitive package set
more reproducible on same platform
can include platform-specific build strings
can be noisy
```

### Package list

```bash id="3cmppi"
conda list > conda-list.txt
conda list --explicit > conda-list-explicit.txt
```

Purpose:

```text id="y6n1ui"
conda list:
  readable package/version/build table

conda list --explicit:
  explicit package URLs/specs for exact environment recreation on compatible platform
```

### Micromamba equivalents

```bash id="cyxnco"
micromamba env export -n nlp > environment.full.yml
micromamba list -n nlp > micromamba-list.txt
micromamba list -n nlp --explicit > micromamba-list-explicit.txt
```

### Agent rule

```text id="iqvfy4"
Store both:
  environment.from-history.yml
  conda-list-explicit.txt

Reason:
  one documents intent
  one documents exact realized environment
```

Conda is a cross-platform package and environment manager, so environment-level package capture is the correct artifact for solver-stack reproducibility when deploying through conda-compatible environments. ([docs.conda.io][2])

---

## 21.3 Ipopt executable and option-surface capture

### Executable identity

```bash id="mutqxq"
which ipopt        # Linux/macOS
where ipopt        # Windows
ipopt -v
```

### AMPL-interface option list

```bash id="vu3ub0"
ipopt -= > ipopt-ampl-options.txt
```

### Full installed option documentation

```bash id="psdwix"
ipopt --print-options > ipopt-print-options.txt
```

Ipopt’s options page says `--print-options` generates option documentation for the executable, and the AMPL solver executable supports `-=` for available options. ([COIN-OR Documentation][1])

### Option profile file

```text id="yey9qj"
# ipopt.opt
tol 1e-8
max_iter 3000
linear_solver mumps
print_user_options yes
```

### Agent artifact set

```text id="cdxai2"
ipopt-executable.txt
ipopt-version.txt
ipopt-ampl-options.txt
ipopt-print-options.txt
ipopt.opt
solver-options.json
```

---

## 21.4 Pyomo and Python version capture

### Python one-liner

```bash id="d42ocs"
python - <<'PY'
import json
import platform
import sys

import pyomo
import pyomo.environ as pyo

info = {
    "python_executable": sys.executable,
    "python_version": sys.version,
    "platform": platform.platform(),
    "machine": platform.machine(),
    "processor": platform.processor(),
    "pyomo_version": pyomo.version.version,
}
print(json.dumps(info, indent=2))
PY
```

### Include NumPy/SciPy where model-generation uses them

```bash id="8a3vua"
python - <<'PY'
import json
import importlib.metadata as md

packages = ["pyomo", "numpy", "scipy", "pandas", "cyipopt"]
out = {}
for pkg in packages:
    try:
        out[pkg] = md.version(pkg)
    except md.PackageNotFoundError:
        out[pkg] = None
print(json.dumps(out, indent=2))
PY
```

### Agent rule

```text id="b4rbva"
Record Python executable, not just Python version.
Notebooks/IDEs frequently run a different interpreter than the shell.
```

---

## 21.5 BLAS/LAPACK and thread environment capture

### Conda BLAS packages

```bash id="r6asdd"
conda list "libblas|liblapack|openblas|mkl|blis|accelerate" > blas-lapack.txt
```

### Thread variables

```bash id="w23x19"
env | grep -E 'OMP_NUM_THREADS|OPENBLAS_NUM_THREADS|MKL_NUM_THREADS|NUMEXPR_NUM_THREADS|VECLIB_MAXIMUM_THREADS' > thread-env.txt
```

### Python capture

```python id="9nt5st"
import os

THREAD_ENV_KEYS = [
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
]

thread_env = {k: os.environ.get(k) for k in THREAD_ENV_KEYS}
```

### Agent rule

```text id="2kbqrh"
For performance comparisons:
  BLAS variant + thread env are required metadata.

For parallel scenario runs:
  thread caps are required metadata.
```

---

## 21.6 Linear solver capture

### Selected linear solver

```python id="bwmnhg"
solver_options = {
    "linear_solver": "mumps",
    "tol": 1e-8,
}
```

### Availability probe

```python id="e18cx2"
import pyomo.environ as pyo

def probe_ipopt_linear_solvers():
    opt = pyo.SolverFactory("ipopt")
    candidates = [
        "mumps",
        "spral",
        "ma27",
        "ma57",
        "ma77",
        "ma86",
        "ma97",
        "pardiso",
        "pardisomkl",
        "wsmp",
    ]
    out = {}
    for name in candidates:
        try:
            out[name] = bool(opt.has_linear_solver(name))
        except Exception as exc:
            out[name] = f"{type(exc).__name__}: {exc}"
    return out
```

### Store

```python id="7u5mnp"
import json
from pathlib import Path

Path("linear-solver-probe.json").write_text(
    json.dumps(probe_ipopt_linear_solvers(), indent=2, default=str)
)
```

Pyomo’s Ipopt interface exposes `has_linear_solver(...)`, which solves a small problem to determine whether the executable can access the specified linear solver. ([Pyomo Documentation][3])

### Agent rule

```text id="szrqky"
Record:
  requested linear_solver
  probed availability
  solver log confirming actual use
```

---

## 21.7 Random seed capture

### Python `random`, NumPy default RNG, legacy NumPy

```python id="5xssky"
import random
import numpy as np

SEED = 20260506

random.seed(SEED)
np.random.seed(SEED)  # legacy global RNG

rng = np.random.default_rng(SEED)  # preferred explicit RNG
```

### Store seed metadata

```python id="1du4ci"
seed_metadata = {
    "python_random_seed": SEED,
    "numpy_legacy_seed": SEED,
    "numpy_default_rng_seed": SEED,
    "scenario_generation_seed": SEED,
}
```

### Agent rule

```text id="v583w7"
If model data, starts, scenarios, samples, initial points, or multistart seeds are generated:
  record seed(s)
  record generator algorithm where possible
  record generated data hash
```

---

## 21.8 Solver logs for benchmark cases

### Pyomo log capture

```python id="q27tve"
results = opt.solve(
    model,
    tee=True,
    logfile="solver.log",
)
```

### Ipopt-native option log

```text id="gcoeb5"
# ipopt.opt
output_file ipopt-native.log
file_print_level 5
print_user_options yes
```

### Development audit options

```python id="f0bt1n"
opt.options.update({
    "print_user_options": "yes",
    "print_info_string": "yes",
    "print_timing_statistics": "yes",
    "inf_pr_output": "original",
})
```

Ipopt supports `print_user_options`, `print_timing_statistics`, and option-documentation printing; Pyomo’s solver recipe docs show `tee=True` and result-status access patterns for solver runs. ([COIN-OR Documentation][1])

### Store logs for

```text id="xa6hvy"
benchmark baseline
new best result
failure case
regression case
linear-solver comparison
scaling comparison
warm-start comparison
major model change
```

---

## 21.9 Result metadata capture

### Required fields

```text id="esrfnw"
results.solver.status
results.solver.termination_condition
objective value
max constraint infeasibility
max variable-bound infeasibility
wall-clock solve time
CPU time if available
iteration count if parsed from log
Ipopt exit message if parsed from log
option profile name
data/scenario id
```

Pyomo’s solver recipes show using `results.solver.status` and `results.solver.termination_condition`, and show `load_solutions=False` followed by manual `model.solutions.load_from(results)` when optimality is confirmed. ([Pyomo Documentation][3])

### Objective capture

```python id="403z2t"
def active_objective_value(model):
    objs = list(model.component_data_objects(pyo.Objective, active=True))
    if len(objs) != 1:
        return None
    return pyo.value(objs[0], exception=False)
```

### Constraint infeasibility

```python id="7yvqcz"
def max_constraint_violation(model):
    worst = {
        "component": None,
        "violation": 0.0,
        "body": None,
        "lower": None,
        "upper": None,
    }

    for c in model.component_data_objects(pyo.Constraint, active=True):
        body = pyo.value(c.body, exception=False)
        if body is None:
            continue

        lb = pyo.value(c.lower, exception=False) if c.lower is not None else None
        ub = pyo.value(c.upper, exception=False) if c.upper is not None else None

        lviol = 0.0 if lb is None else max(0.0, lb - body)
        uviol = 0.0 if ub is None else max(0.0, body - ub)
        viol = max(lviol, uviol)

        if viol > worst["violation"]:
            worst = {
                "component": c.name,
                "violation": viol,
                "body": body,
                "lower": lb,
                "upper": ub,
            }

    return worst
```

### Bound infeasibility

```python id="rp9k7b"
def max_bound_violation(model):
    worst = {
        "component": None,
        "violation": 0.0,
        "value": None,
        "lower": None,
        "upper": None,
    }

    for v in model.component_data_objects(pyo.Var, active=True):
        val = pyo.value(v, exception=False)
        if val is None:
            continue

        lb = pyo.value(v.lb, exception=False) if v.lb is not None else None
        ub = pyo.value(v.ub, exception=False) if v.ub is not None else None

        lviol = 0.0 if lb is None else max(0.0, lb - val)
        uviol = 0.0 if ub is None else max(0.0, val - ub)
        viol = max(lviol, uviol)

        if viol > worst["violation"]:
            worst = {
                "component": v.name,
                "violation": viol,
                "value": val,
                "lower": lb,
                "upper": ub,
            }

    return worst
```

---

## 21.10 Solve-time capture

```python id="o5bz1o"
import time

t0 = time.perf_counter()
results = opt.solve(model, tee=True, logfile="solver.log", load_solutions=False)
solve_wall_seconds = time.perf_counter() - t0
```

### Pyomo-side and solver-side timing

```python id="zds4z5"
opt.options["print_timing_statistics"] = "yes"
```

`print_timing_statistics=yes` asks Ipopt to print timing statistics and implies `timing_statistics=yes`; use this for solver-side timing attribution. ([COIN-OR Documentation][1])

---

## 21.11 Model and data fingerprinting

### File hash utility

```python id="23eysj"
from pathlib import Path
import hashlib

def sha256_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()
```

### JSON-stable hash

```python id="4t6348"
import hashlib
import json

def sha256_jsonable(obj):
    payload = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(payload).hexdigest()
```

### Model structural fingerprint

```python id="aqowb0"
def pyomo_model_fingerprint(model):
    return {
        "variables": [
            {
                "name": v.name,
                "fixed": bool(v.fixed),
                "lb": pyo.value(v.lb, exception=False) if v.lb is not None else None,
                "ub": pyo.value(v.ub, exception=False) if v.ub is not None else None,
            }
            for v in model.component_data_objects(pyo.Var, active=True)
        ],
        "constraints": [
            {
                "name": c.name,
                "equality": bool(c.equality),
                "lower": pyo.value(c.lower, exception=False) if c.lower is not None else None,
                "upper": pyo.value(c.upper, exception=False) if c.upper is not None else None,
            }
            for c in model.component_data_objects(pyo.Constraint, active=True)
        ],
        "objectives": [
            {"name": o.name, "sense": str(o.sense)}
            for o in model.component_data_objects(pyo.Objective, active=True)
        ],
    }
```

### Agent rule

```text id="z1mx9f"
For benchmark claims:
  hash input data files
  record model code commit
  record structural fingerprint
  record generated scenario id and seed
```

---

## 21.12 Unified reproducibility collector

```python id="8f1qn4"
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pyomo
import pyomo.environ as pyo


@dataclass
class ReproducibilityRecord:
    run_id: str
    timestamp_utc: str
    python_executable: str
    python_version: str
    platform: str
    machine: str
    pyomo_version: str
    ipopt_path: str | None
    ipopt_version: str | None
    solver_options: dict[str, Any]
    thread_env: dict[str, str | None]
    solver_status: str
    termination_condition: str
    objective: float | None
    max_constraint_violation: dict[str, Any]
    max_bound_violation: dict[str, Any]
    solve_wall_seconds: float
    log_path: str
    data_hash: str | None = None
    model_fingerprint_hash: str | None = None
    seed_metadata: dict[str, Any] | None = None


def run_text(cmd: list[str]) -> str | None:
    try:
        return subprocess.run(
            cmd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=30,
        ).stdout.strip()
    except Exception:
        return None


def utc_now_iso():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def collect_thread_env():
    keys = [
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
    ]
    return {k: os.environ.get(k) for k in keys}


def solve_with_repro_record(
    model,
    *,
    run_id: str,
    solver_options: dict[str, Any] | None = None,
    log_path: str = "ipopt.solve.log",
    seed_metadata: dict[str, Any] | None = None,
    data_hash: str | None = None,
):
    opt = pyo.SolverFactory("ipopt")
    if not opt.available(exception_flag=False):
        raise RuntimeError("Ipopt unavailable to Pyomo.")

    options = {
        "print_user_options": "yes",
        "inf_pr_output": "original",
        "print_level": 5,
    }
    if solver_options:
        options.update(solver_options)

    opt.options.update(options)

    t0 = time.perf_counter()
    results = opt.solve(
        model,
        tee=True,
        logfile=log_path,
        load_solutions=False,
    )
    elapsed = time.perf_counter() - t0

    # Load only if accepted by a strict policy.
    if str(results.solver.termination_condition).lower() in {"optimal", "locallyoptimal"}:
        model.solutions.load_from(results)

    fingerprint = pyomo_model_fingerprint(model)
    fingerprint_hash = sha256_jsonable(fingerprint)

    record = ReproducibilityRecord(
        run_id=run_id,
        timestamp_utc=utc_now_iso(),
        python_executable=sys.executable,
        python_version=sys.version,
        platform=platform.platform(),
        machine=platform.machine(),
        pyomo_version=pyomo.version.version,
        ipopt_path=shutil.which("ipopt"),
        ipopt_version=run_text(["ipopt", "-v"]) if shutil.which("ipopt") else None,
        solver_options=dict(options),
        thread_env=collect_thread_env(),
        solver_status=str(results.solver.status),
        termination_condition=str(results.solver.termination_condition),
        objective=active_objective_value(model),
        max_constraint_violation=max_constraint_violation(model),
        max_bound_violation=max_bound_violation(model),
        solve_wall_seconds=elapsed,
        log_path=str(Path(log_path).absolute()),
        data_hash=data_hash,
        model_fingerprint_hash=fingerprint_hash,
        seed_metadata=seed_metadata,
    )

    return results, record
```

### Write record

```python id="4f7k9n"
results, record = solve_with_repro_record(
    m,
    run_id="case001",
    solver_options={"tol": 1e-8, "linear_solver": "mumps"},
    seed_metadata={"numpy_default_rng_seed": 20260506},
    data_hash=sha256_file("case001-data.json"),
)

Path("repro-record.json").write_text(
    json.dumps(asdict(record), indent=2, default=str)
)
```

---

## 21.13 CLI capture script

```bash id="zzi6sj"
#!/usr/bin/env bash
set -euo pipefail

OUT="${1:-repro-artifacts}"
mkdir -p "$OUT"

date -u +"%Y-%m-%dT%H:%M:%SZ" > "$OUT/timestamp-utc.txt"

python - <<'PY' > "$OUT/python-platform.json"
import json, platform, sys
import pyomo
print(json.dumps({
  "python_executable": sys.executable,
  "python_version": sys.version,
  "platform": platform.platform(),
  "machine": platform.machine(),
  "pyomo_version": pyomo.version.version,
}, indent=2))
PY

command -v ipopt > "$OUT/ipopt-path.txt" || true
ipopt -v > "$OUT/ipopt-version.txt" 2>&1 || true
ipopt -= > "$OUT/ipopt-ampl-options.txt" 2>&1 || true
ipopt --print-options > "$OUT/ipopt-print-options.txt" 2>&1 || true

conda env export --from-history > "$OUT/environment.from-history.yml" 2>&1 || true
conda env export > "$OUT/environment.full.yml" 2>&1 || true
conda list > "$OUT/conda-list.txt" 2>&1 || true
conda list --explicit > "$OUT/conda-list-explicit.txt" 2>&1 || true

conda list "libblas|liblapack|openblas|mkl|blis|accelerate" > "$OUT/blas-lapack.txt" 2>&1 || true
env | grep -E 'OMP_NUM_THREADS|OPENBLAS_NUM_THREADS|MKL_NUM_THREADS|NUMEXPR_NUM_THREADS|VECLIB_MAXIMUM_THREADS' > "$OUT/thread-env.txt" || true
```

---

## 21.14 Benchmark-case directory layout

```text id="hz459e"
runs/
  2026-05-06T15-00-00Z_case001/
    README.md
    repro-record.json
    solver.log
    ipopt.opt
    solver-options.json
    ipopt-version.txt
    ipopt-ampl-options.txt
    ipopt-print-options.txt
    environment.from-history.yml
    environment.full.yml
    conda-list.txt
    conda-list-explicit.txt
    blas-lapack.txt
    thread-env.txt
    linear-solver-probe.json
    model-fingerprint.json
    data-hashes.json
    seed-metadata.json
    solution-primal.json
    solution-duals.json
    residual-report.json
```

---

## 21.15 Capturing primal/dual solution artifacts

### Primal values

```python id="92ltpg"
def primal_solution_dict(model):
    return {
        v.name: pyo.value(v, exception=False)
        for v in model.component_data_objects(pyo.Var, active=True)
    }
```

### Constraint duals

```python id="gcgj76"
def dual_solution_dict(model):
    dual = getattr(model, "dual", None)
    if dual is None:
        return {}
    return {
        c.name: dual.get(c, None)
        for c in model.component_data_objects(pyo.Constraint, active=True)
    }
```

### Ipopt bound multipliers

```python id="de7frg"
def ipopt_bound_multiplier_dict(model):
    zL = getattr(model, "ipopt_zL_out", None)
    zU = getattr(model, "ipopt_zU_out", None)
    return {
        v.name: {
            "zL": None if zL is None else zL.get(v, None),
            "zU": None if zU is None else zU.get(v, None),
        }
        for v in model.component_data_objects(pyo.Var, active=True)
    }
```

### Store

```python id="zfipgo"
Path("solution-primal.json").write_text(json.dumps(primal_solution_dict(m), indent=2, default=str))
Path("solution-duals.json").write_text(json.dumps(dual_solution_dict(m), indent=2, default=str))
Path("solution-bound-multipliers.json").write_text(json.dumps(ipopt_bound_multiplier_dict(m), indent=2, default=str))
```

---

## 21.16 Reproducible solve policy with `load_solutions=False`

```python id="zfrfyg"
from pyomo.opt import SolverStatus, TerminationCondition

results = opt.solve(m, tee=True, logfile="solver.log", load_solutions=False)

record = {
    "solver_status": str(results.solver.status),
    "termination_condition": str(results.solver.termination_condition),
}

if (
    results.solver.status == SolverStatus.ok
    and results.solver.termination_condition == TerminationCondition.optimal
):
    m.solutions.load_from(results)
    record["solution_loaded"] = True
else:
    record["solution_loaded"] = False
```

### Agent rule

```text id="afw86o"
Always record:
  whether the solution was loaded
  why it was loaded or rejected
  allowed termination policy
```

---

## 21.17 Option-profile reproducibility

### Store final option dictionary

```python id="4mfi6q"
final_options = dict(opt.options)

Path("solver-options.json").write_text(
    json.dumps(final_options, indent=2, sort_keys=True, default=str)
)
```

### Store `ipopt.opt` if used

```python id="a9qov0"
from pathlib import Path

if Path("ipopt.opt").exists():
    Path("saved-ipopt.opt").write_text(Path("ipopt.opt").read_text())
```

### Store option merge provenance

```json id="tq47oz"
{
  "base_profile": "strict-final",
  "bundles": ["mumps", "output-audit"],
  "overrides": {
    "max_iter": 5000
  },
  "final": {
    "tol": 1e-9,
    "linear_solver": "mumps"
  }
}
```

### Agent rule

```text id="71sc78"
Do not store only profile name.
Store final flattened options actually passed to Ipopt.
```

---

## 21.18 Regression and benchmark comparison schema

```json id="0k73c9"
{
  "run_id": "case001_mumps_tol1e-8",
  "model_hash": "sha256:...",
  "data_hash": "sha256:...",
  "ipopt_version": "...",
  "pyomo_version": "...",
  "linear_solver": "mumps",
  "blas_variant": "openblas",
  "thread_env": {
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1"
  },
  "termination_condition": "optimal",
  "solver_status": "ok",
  "objective": 123.456,
  "max_constraint_violation": 1e-9,
  "max_bound_violation": 0.0,
  "solve_wall_seconds": 8.532,
  "iteration_count": 47
}
```

### Comparison rules

```text id="ahwhec"
Objective comparison:
  only compare after matching termination policy.

Timing comparison:
  only compare with same hardware/thread/BLAS/linear-solver context.

Dual comparison:
  only compare after matching interface and sign convention.

Residual comparison:
  use original unscaled model residuals for application-level validation.
```

---

## 21.19 Agent anti-pattern catalog

```text id="xgko4k"
BAD:
  "Ipopt solved it" without version, options, termination condition.

GOOD:
  record ipopt -v, options, status, termination_condition, objective, residuals.

BAD:
  conda env export --from-history only.

GOOD:
  store both from-history and explicit package list.

BAD:
  store linear_solver option but not prove availability.

GOOD:
  store has_linear_solver probe and solver log.

BAD:
  compare timings with unknown BLAS threads.

GOOD:
  record OMP/OpenBLAS/MKL thread variables and BLAS variant.

BAD:
  load solutions blindly before checking status.

GOOD:
  use load_solutions=False and record accepted load policy.

BAD:
  use random starts without seed capture.

GOOD:
  store all seeds and generated data hashes.

BAD:
  keep only final answer, discard solver log.

GOOD:
  store logs for benchmark/failure/release cases.
```

---

## 21.20 Final checklist

```text id="aol04i"
[ ] Record Ipopt executable path.
[ ] Record ipopt -v output.
[ ] Record ipopt -= output.
[ ] Record ipopt --print-options output.
[ ] Record Pyomo version.
[ ] Record Python executable and version.
[ ] Record platform/machine/OS.
[ ] Record conda env export --from-history.
[ ] Record conda env export full environment.
[ ] Record conda list.
[ ] Record conda list --explicit.
[ ] Record BLAS/LAPACK package variant.
[ ] Record thread environment variables.
[ ] Record selected linear_solver.
[ ] Record linear-solver availability probe.
[ ] Record final flattened Ipopt options.
[ ] Record ipopt.opt contents if used.
[ ] Record random seeds and data hashes.
[ ] Store solver logs for benchmark and failure cases.
[ ] Capture status and termination_condition.
[ ] Capture objective value only after accepted load policy.
[ ] Capture original constraint and bound infeasibilities.
[ ] Capture solve wall time and, if available, Ipopt timing statistics.
[ ] Store primal/dual/bound-multiplier solution snapshots when relevant.
[ ] Store model/data fingerprint for benchmark claims.
```

[1]: https://coin-or.github.io/Ipopt/OPTIONS.html?utm_source=chatgpt.com "Ipopt Options"
[2]: https://docs.conda.io/?utm_source=chatgpt.com "Conda Documentation — conda-docs documentation"
[3]: https://pyomo.readthedocs.io/en/latest/howto/solver_recipes.html?utm_source=chatgpt.com "Solver Recipes — Pyomo 6.10.1.dev0 documentation"

# Ipopt Advanced — Section 22: testing and QA harness

Style target: dense advanced technical catalog / agent-ready reference. 

## 22.0 QA invariant

```text id="ladjhi"
Pyomo + Ipopt QA harness =
  executable/environment tests
  + model-contract tests
  + known-NLP regression tests
  + infeasibility/failure-mode tests
  + option propagation tests
  + suffix/warm-start tests
  + linear-solver capability tests
  + solver-log golden fragments
  + scaling/initialization regression tests
  + cross-platform CI matrix
```

**Agent rule:** test the optimization stack as a deployment artifact, not just Python model code. Pyomo’s solver recipes show checking `results.solver.status` and `results.solver.termination_condition`, using `load_solutions=False` to inspect results before loading, passing solver options through `opt.options` or `solve(..., options={...})`, and streaming output with `tee=True`; Ipopt’s option docs recommend installed-build option dumps because linear-solver option availability/defaults are build-dependent. ([Pyomo Documentation][1])

---

## 22.1 Test-suite dependency pattern

### `pytest` markers

```ini id="wugqq3"
# pytest.ini
[pytest]
markers =
    ipopt: requires Ipopt executable
    ipopt_slow: slow Ipopt solve
    ipopt_linear_solver: probes installed Ipopt linear solver support
    ipopt_warm_start: tests Ipopt suffix warm-start round trip
    ipopt_golden_log: tests solver log text fragments
```

### Skip-if-unavailable fixture

```python id="4l09u8"
# conftest.py
import shutil
import pytest
import pyomo.environ as pyo


@pytest.fixture(scope="session")
def ipopt_solver():
    opt = pyo.SolverFactory("ipopt")
    if not opt.available(exception_flag=False):
        pytest.skip(
            "Ipopt unavailable: install conda-forge::ipopt or pass executable path."
        )
    return opt


@pytest.fixture(scope="session")
def ipopt_executable_path():
    path = shutil.which("ipopt")
    if path is None:
        pytest.skip("ipopt executable not found on PATH.")
    return path
```

### Deterministic numeric tolerances

```python id="t27vp8"
import math

def assert_close(actual, expected, *, abs_tol=1e-7, rel_tol=1e-7):
    assert math.isclose(actual, expected, abs_tol=abs_tol, rel_tol=rel_tol), (
        actual,
        expected,
    )
```

### Agent rule

```text id="pzy7z8"
Tests that require the solver should skip cleanly if Ipopt is unavailable.
Deployment CI should include at least one required Ipopt job where skip is not allowed.
```

Pyomo’s classic Ipopt interface exposes `available()`, `version()`, `executable()`, and `has_linear_solver(...)`, and the newer Ipopt interface documents `has_linear_solver(...)` as solving a small problem to detect access to a specified linear solver. ([Pyomo Documentation][2])

---

## 22.2 Minimal availability test

### Test objective

```text id="obzrb2"
Verify:
  Python environment can import Pyomo
  SolverFactory("ipopt") resolves
  executable is available
  version query does not fail catastrophically
```

### Test code

```python id="d01w4x"
# tests/test_ipopt_availability.py
import shutil
import pyomo.environ as pyo


def test_ipopt_executable_on_path_or_solver_available():
    opt = pyo.SolverFactory("ipopt")

    assert opt.available(exception_flag=False), (
        "Ipopt unavailable to Pyomo. "
        f"shutil.which('ipopt')={shutil.which('ipopt')}"
    )


def test_ipopt_version_query(ipopt_solver):
    version = ipopt_solver.version()
    assert version is not None
```

### Strong deployment variant

```python id="q0cnp9"
def test_ipopt_executable_path(ipopt_solver):
    exe = ipopt_solver.executable()
    assert exe is not None
    assert "ipopt" in str(exe).lower()
```

### Agent value case

```text id="kgy12z"
Catches:
  missing solver package
  wrong Python environment
  PATH/kernel mismatch
  broken executable lookup
  CI image missing solver
```

Pyomo installation guidance treats solver installation as separate from Pyomo installation, and Pyomo’s solver recipes document `executable=` when a solver is not located through `PATH`; use availability tests to prevent model tests from failing with misleading algebraic errors. ([Pyomo Documentation][3])

---

## 22.3 Small known NLP test

### Model

```python id="nytzfp"
import pyomo.environ as pyo


def build_small_convex_nlp():
    m = pyo.ConcreteModel()

    m.x = pyo.Var(bounds=(0.0, None), initialize=0.5)
    m.y = pyo.Var(bounds=(0.0, None), initialize=0.5)

    # Unique known optimum: x=1, y=2, obj=0; constraint inactive.
    m.obj = pyo.Objective(expr=(m.x - 1.0) ** 2 + (m.y - 2.0) ** 2)
    m.c = pyo.Constraint(expr=m.x + m.y >= 0.1)

    return m
```

### Test

```python id="t8abxc"
from pyomo.opt import SolverStatus, TerminationCondition


def test_small_known_nlp_solution(ipopt_solver):
    m = build_small_convex_nlp()

    ipopt_solver.options.clear()
    ipopt_solver.options.update({
        "tol": 1e-8,
        "print_level": 0,
        "sb": "yes",
    })

    res = ipopt_solver.solve(m, tee=False, load_solutions=False)

    assert res.solver.status == SolverStatus.ok
    assert res.solver.termination_condition == TerminationCondition.optimal

    m.solutions.load_from(res)

    assert_close(pyo.value(m.x), 1.0, abs_tol=1e-6)
    assert_close(pyo.value(m.y), 2.0, abs_tol=1e-6)
    assert_close(pyo.value(m.obj), 0.0, abs_tol=1e-8)
```

### Agent rules

```text id="uv0i8f"
Known NLP test should be:
  tiny
  convex or analytically understood
  no external functions
  bounded where possible
  deterministic
  insensitive to linear solver variant
```

---

## 22.4 Infeasible model test

### Model

```python id="klmsjo"
def build_infeasible_nlp():
    m = pyo.ConcreteModel()
    m.x = pyo.Var(initialize=0.5)

    m.obj = pyo.Objective(expr=m.x**2)

    m.lb = pyo.Constraint(expr=m.x >= 1.0)
    m.ub = pyo.Constraint(expr=m.x <= 0.0)

    return m
```

### Test: accept multiple infeasibility mappings

```python id="sb6nvd"
from pyomo.opt import TerminationCondition


def test_infeasible_model_detected(ipopt_solver):
    m = build_infeasible_nlp()

    ipopt_solver.options.clear()
    ipopt_solver.options.update({
        "tol": 1e-8,
        "max_iter": 200,
        "print_level": 0,
        "sb": "yes",
    })

    res = ipopt_solver.solve(m, tee=False, load_solutions=False)

    assert res.solver.termination_condition in {
        TerminationCondition.infeasible,
        TerminationCondition.locallyInfeasible,
        TerminationCondition.other,
    } or "infeasible" in str(res.solver).lower()
```

### Golden log variant

```python id="ai43md"
def test_infeasible_model_log_fragment(ipopt_solver, tmp_path):
    m = build_infeasible_nlp()
    log_path = tmp_path / "infeasible.log"

    ipopt_solver.options.clear()
    ipopt_solver.options.update({
        "print_level": 5,
        "inf_pr_output": "original",
    })

    ipopt_solver.solve(m, tee=False, logfile=str(log_path), load_solutions=False)

    log = log_path.read_text()
    assert (
        "Converged to a point of local infeasibility" in log
        or "Problem may be infeasible" in log
        or "Infeasible_Problem_Detected" in log
    )
```

Ipopt’s output docs describe `Infeasible_Problem_Detected` / “Converged to a point of local infeasibility. Problem may be infeasible,” and explicitly frame the returned point as a diagnostic for problematic constraints rather than a universal global proof. ([COIN-OR Documentation][4])

---

## 22.5 Bad derivative / nonsmooth model test

### Nonsmooth model expected to fail derivative-check or not pass QA

```python id="4jxbo5"
def build_nonsmooth_model():
    m = pyo.ConcreteModel()
    m.x = pyo.Var(initialize=0.0)
    m.obj = pyo.Objective(expr=pyo.sqrt(m.x**2))  # abs-like nonsmooth at 0
    return m
```

### Derivative-check test

```python id="l1ldxq"
def test_nonsmooth_model_derivative_checker_flags_issue(ipopt_solver, tmp_path):
    m = build_nonsmooth_model()
    log_path = tmp_path / "derivative-check.log"

    ipopt_solver.options.clear()
    ipopt_solver.options.update({
        "derivative_test": "first-order",
        "derivative_test_print_all": "yes",
        "derivative_test_tol": 1e-4,
        "derivative_test_perturbation": 1e-8,
        "max_iter": 0,
        "print_level": 7,
    })

    ipopt_solver.solve(m, tee=False, logfile=str(log_path), load_solutions=False)

    log = log_path.read_text().lower()

    assert (
        "derivative checker" in log
        or "invalid number" in log
        or "error" in log
    )
```

### Better QA pattern: reject nonsmooth model by model checker

```python id="iism5j"
def test_model_quality_checker_rejects_uninitialized_or_bad_domains():
    m = pyo.ConcreteModel()
    m.x = pyo.Var(bounds=(0, None), initialize=0.0)
    m.obj = pyo.Objective(expr=pyo.log(m.x))

    errors, warnings = ipopt_quality_check(m)

    assert errors or warnings
```

### Agent rules

```text id="00dz2f"
Bad-derivative tests should not rely on one exact Ipopt string across versions.
Use:
  derivative-check summary fragments
  exception class if raised
  model checker warning/error
  finite/nonfinite expression evaluation check
```

Ipopt’s derivative checker is finite-difference-based, can test first- or second-order derivatives before optimization starts, and is explicitly intended to catch derivative implementation mistakes. ([COIN-OR Documentation][5])

---

## 22.6 Option propagation test

### Test `print_user_options`

```python id="vlk3ah"
def test_ipopt_option_propagation(ipopt_solver, tmp_path):
    m = build_small_convex_nlp()
    log_path = tmp_path / "option-prop.log"

    ipopt_solver.options.clear()
    ipopt_solver.options.update({
        "tol": 1e-6,
        "max_iter": 77,
        "print_user_options": "yes",
        "print_level": 5,
    })

    ipopt_solver.solve(m, tee=False, logfile=str(log_path), load_solutions=False)

    log = log_path.read_text().lower()

    assert "tol" in log
    assert "max_iter" in log or "max iter" in log
    assert "1e-06" in log or "1.000000e-06" in log or "1.0e-06" in log
```

### Solve-local options override persistent options

```python id="vwl6zr"
def test_solve_local_options_override_persistent(ipopt_solver, tmp_path):
    m = build_small_convex_nlp()
    log_path = tmp_path / "local-options.log"

    ipopt_solver.options.clear()
    ipopt_solver.options["max_iter"] = 999

    ipopt_solver.solve(
        m,
        tee=False,
        logfile=str(log_path),
        load_solutions=False,
        options={
            "max_iter": 3,
            "print_user_options": "yes",
            "print_level": 5,
        },
    )

    log = log_path.read_text().lower()
    assert "max_iter" in log
    assert "3" in log
```

Pyomo documents persistent solver-object options and solve-local options, with solve-local options temporarily overriding persistent values for the duration of that solve; Ipopt’s `print_user_options=yes` prints user-set options, values, and a usage indication. ([Pyomo Documentation][1])

### Agent rules

```text id="c4m7mn"
[ ] test option propagation with print_user_options=yes.
[ ] verify string toggles use "yes"/"no", not Python booleans.
[ ] test solve-local options separately from persistent opt.options.
[ ] do not assume invalid options fail at Python layer; Ipopt usually detects them.
```

---

## 22.7 Warm-start suffix round-trip test

### Model and suffix declarations

```python id="mmh5dl"
def build_warm_start_model():
    m = pyo.ConcreteModel()

    m.x1 = pyo.Var(bounds=(1, 5), initialize=1.0)
    m.x2 = pyo.Var(bounds=(1, 5), initialize=5.0)
    m.x3 = pyo.Var(bounds=(1, 5), initialize=5.0)
    m.x4 = pyo.Var(bounds=(1, 5), initialize=1.0)

    m.obj = pyo.Objective(
        expr=m.x1 * m.x4 * (m.x1 + m.x2 + m.x3) + m.x3
    )
    m.ineq = pyo.Constraint(expr=m.x1 * m.x2 * m.x3 * m.x4 >= 25.0)
    m.eq = pyo.Constraint(expr=m.x1**2 + m.x2**2 + m.x3**2 + m.x4**2 == 40.0)

    m.dual = pyo.Suffix(direction=pyo.Suffix.IMPORT_EXPORT)
    m.ipopt_zL_out = pyo.Suffix(direction=pyo.Suffix.IMPORT)
    m.ipopt_zU_out = pyo.Suffix(direction=pyo.Suffix.IMPORT)
    m.ipopt_zL_in = pyo.Suffix(direction=pyo.Suffix.EXPORT)
    m.ipopt_zU_in = pyo.Suffix(direction=pyo.Suffix.EXPORT)

    return m
```

### Test suffix import/export round trip

```python id="z8unnd"
def test_ipopt_warm_start_suffix_round_trip(ipopt_solver):
    m = build_warm_start_model()

    ipopt_solver.options.clear()
    ipopt_solver.options.update({
        "tol": 1e-8,
        "print_level": 0,
        "sb": "yes",
    })

    res1 = ipopt_solver.solve(m, tee=False)

    # Suffixes should be populated after a successful solve.
    assert len(list(m.ipopt_zL_out.items())) > 0
    assert len(list(m.ipopt_zU_out.items())) > 0
    assert m.ineq in m.dual
    assert m.eq in m.dual

    # Copy bound multiplier outputs to inputs.
    m.ipopt_zL_in.update(m.ipopt_zL_out)
    m.ipopt_zU_in.update(m.ipopt_zU_out)

    assert len(list(m.ipopt_zL_in.items())) > 0
    assert len(list(m.ipopt_zU_in.items())) > 0

    ipopt_solver.options.update({
        "warm_start_init_point": "yes",
        "warm_start_bound_push": 1e-6,
        "warm_start_mult_bound_push": 1e-6,
        "mu_init": 1e-6,
    })

    res2 = ipopt_solver.solve(m, tee=False)

    assert str(res2.solver.termination_condition).lower() in {
        "optimal",
        "locallyoptimal",
    }
```

Pyomo’s suffix documentation shows exactly this Ipopt warm-start pattern: declare `dual` as `IMPORT_EXPORT`, declare `ipopt_zL_out` and `ipopt_zU_out` as `IMPORT`, declare `ipopt_zL_in` and `ipopt_zU_in` as `EXPORT`, then copy output bound multipliers to input suffixes before the warm-started solve. ([Pyomo Documentation][6])

### Agent rules

```text id="by7fmn"
[ ] test suffix declarations before relying on warm starts.
[ ] test that output suffixes are populated after accepted solve.
[ ] test zL_out → zL_in and zU_out → zU_in exactly.
[ ] avoid asserting exact iteration-count reduction across platforms unless tightly controlled.
```

---

## 22.8 Linear solver availability test

### Baseline MUMPS required test

```python id="fyax2k"
@pytest.mark.ipopt_linear_solver
def test_ipopt_mumps_available(ipopt_solver):
    assert ipopt_solver.has_linear_solver("mumps")
```

### Optional solver probe matrix

```python id="rnqbew"
@pytest.mark.ipopt_linear_solver
@pytest.mark.parametrize("linear_solver", ["mumps", "spral", "ma57", "pardiso", "pardisomkl"])
def test_ipopt_linear_solver_probe_does_not_crash(ipopt_solver, linear_solver):
    try:
        result = ipopt_solver.has_linear_solver(linear_solver)
    except Exception as exc:
        pytest.fail(f"has_linear_solver({linear_solver!r}) raised {type(exc).__name__}: {exc}")

    assert isinstance(result, bool)
```

### Expected-optional pattern

```python id="s1oo4d"
@pytest.mark.ipopt_linear_solver
def test_optional_spral_if_expected(ipopt_solver):
    expected = False  # set from env/CI matrix if needed
    result = ipopt_solver.has_linear_solver("spral")

    if expected:
        assert result
```

### Agent rules

```text id="z917m0"
[ ] require only the project-supported baseline linear solver.
[ ] probe optional solvers without failing unless environment claims support.
[ ] store probe output as CI artifact for debugging.
[ ] never set `linear_solver=ma57/pardiso/spral` in tests without availability gate.
```

Pyomo’s legacy Ipopt plugin implements `has_linear_solver(...)` by solving a small model with `options={'linear_solver': linear_solver}` and checking for solver output indicating the chosen linear solver; the newer interface also documents the same high-level behavior. ([Pyomo Documentation][7])

---

## 22.9 Golden log fragments for termination messages

### Golden fragment test: optimal

```python id="ro2pt2"
def test_ipopt_optimal_log_fragment(ipopt_solver, tmp_path):
    m = build_small_convex_nlp()
    log_path = tmp_path / "optimal.log"

    ipopt_solver.options.clear()
    ipopt_solver.options.update({"print_level": 5})

    res = ipopt_solver.solve(m, tee=False, logfile=str(log_path), load_solutions=False)

    log = log_path.read_text()
    assert "EXIT: Optimal Solution Found" in log
```

### Golden fragment test: max iterations

```python id="bwrwjk"
def test_ipopt_max_iter_log_fragment(ipopt_solver, tmp_path):
    m = build_small_convex_nlp()
    log_path = tmp_path / "max-iter.log"

    ipopt_solver.options.clear()
    ipopt_solver.options.update({
        "max_iter": 0,
        "print_level": 5,
    })

    ipopt_solver.solve(m, tee=False, logfile=str(log_path), load_solutions=False)

    log = log_path.read_text()
    assert (
        "Maximum Number of Iterations Exceeded" in log
        or "Maximum_Iterations_Exceeded" in log
    )
```

### Golden fragment test: infeasible / local infeasibility

```python id="bsndns"
def test_ipopt_infeasible_log_fragment(ipopt_solver, tmp_path):
    m = build_infeasible_nlp()
    log_path = tmp_path / "infeasible.log"

    ipopt_solver.options.clear()
    ipopt_solver.options.update({"print_level": 5, "max_iter": 200})

    ipopt_solver.solve(m, tee=False, logfile=str(log_path), load_solutions=False)

    log = log_path.read_text()
    assert (
        "Converged to a point of local infeasibility" in log
        or "Problem may be infeasible" in log
        or "Infeasible_Problem_Detected" in log
    )
```

Ipopt’s output docs define exit messages including “Optimal Solution Found,” “Solved To Acceptable Level,” “Converged to a point of local infeasibility. Problem may be infeasible,” and iteration/time/numerical failure messages; golden fragments should target these stable semantic strings rather than full logs. ([COIN-OR Documentation][4])

### Agent rules

```text id="c0aq4v"
[ ] snapshot fragments, not full logs.
[ ] avoid exact iteration tables as goldens across platforms.
[ ] normalize paths/timing if full logs must be compared.
[ ] keep solver version in artifact metadata.
```

---

## 22.10 Regression test for model scaling and initialization

### Test all active expressions evaluate finite at start

```python id="70srjd"
import math


def assert_model_evaluable_at_start(model):
    for obj in model.component_data_objects(pyo.Objective, active=True):
        val = pyo.value(obj.expr, exception=False)
        assert val is not None
        assert math.isfinite(float(val))

    for c in model.component_data_objects(pyo.Constraint, active=True):
        val = pyo.value(c.body, exception=False)
        assert val is not None, c.name
        assert math.isfinite(float(val)), (c.name, val)
```

### Test no missing nonlinear starts

```python id="3rc55l"
def test_no_missing_variable_initial_values(model_factory):
    m = model_factory()

    missing = [
        v.name
        for v in m.component_data_objects(pyo.Var, active=True)
        if not v.fixed and v.value is None
    ]

    assert not missing
```

### Test no fake infinity bounds

```python id="a3xtsc"
def test_no_huge_fake_bounds(model_factory):
    m = model_factory()
    huge = []

    for v in m.component_data_objects(pyo.Var, active=True):
        lb = pyo.value(v.lb, exception=False) if v.lb is not None else None
        ub = pyo.value(v.ub, exception=False) if v.ub is not None else None

        if lb is not None and abs(lb) >= 1e19:
            huge.append((v.name, "lb", lb))
        if ub is not None and abs(ub) >= 1e19:
            huge.append((v.name, "ub", ub))

    assert not huge
```

### Test scaling suffix present for known raw-unit model

```python id="jr93eo"
def test_scaling_suffix_present_for_scaled_model(model_factory):
    m = model_factory()

    assert hasattr(m, "scaling_factor")

    # Example required components.
    assert m.obj in m.scaling_factor
    assert m.mass_balance in m.scaling_factor
```

### Solve-level scaling regression

```python id="9bxyfh"
def test_scaled_model_solves_with_low_residual(ipopt_solver, model_factory):
    m = model_factory()

    ipopt_solver.options.clear()
    ipopt_solver.options.update({
        "tol": 1e-8,
        "constr_viol_tol": 1e-6,
        "nlp_scaling_method": "gradient-based",
        "print_level": 0,
        "sb": "yes",
    })

    res = ipopt_solver.solve(m, tee=False, load_solutions=False)
    assert str(res.solver.termination_condition).lower() in {"optimal", "locallyoptimal"}

    m.solutions.load_from(res)

    worst = max_constraint_violation(m)
    assert worst["violation"] <= 1e-6
```

Ipopt’s `nlp_scaling_method` and `nlp_scaling_max_gradient` control NLP scaling behavior, and Pyomo’s NL writer can use a `scaling_factor` suffix for model scaling through the NL file path. ([COIN-OR Documentation][5])

---

## 22.11 Minimal model-quality helper used by tests

```python id="7vuu29"
def model_contract_errors(model, *, huge_bound=1e19):
    errors = []
    warnings = []

    objectives = list(model.component_data_objects(pyo.Objective, active=True))
    if len(objectives) != 1:
        errors.append(f"expected one active objective; got {len(objectives)}")

    for v in model.component_data_objects(pyo.Var, active=True):
        if not v.fixed and (v.is_binary() or v.is_integer()):
            errors.append(f"active discrete variable: {v.name}")

        if not v.fixed and v.value is None:
            warnings.append(f"missing start: {v.name}")

        lb = pyo.value(v.lb, exception=False) if v.lb is not None else None
        ub = pyo.value(v.ub, exception=False) if v.ub is not None else None

        if lb is not None and ub is not None and lb > ub:
            errors.append(f"bad bounds: {v.name}")

        if lb is not None and abs(lb) >= huge_bound:
            warnings.append(f"huge lower bound: {v.name}={lb}")

        if ub is not None and abs(ub) >= huge_bound:
            warnings.append(f"huge upper bound: {v.name}={ub}")

    for c in model.component_data_objects(pyo.Constraint, active=True):
        body = pyo.value(c.body, exception=False)
        if body is None:
            warnings.append(f"constraint body not evaluable: {c.name}")

    return errors, warnings
```

### Test

```python id="oy451b"
def test_model_contract(model_factory):
    m = model_factory()
    errors, warnings = model_contract_errors(m)

    assert not errors
    assert not warnings
```

---

## 22.12 Residual audit utilities for QA

```python id="ykan2h"
def max_constraint_violation(model):
    worst = {
        "component": None,
        "violation": 0.0,
        "body": None,
        "lower": None,
        "upper": None,
    }

    for c in model.component_data_objects(pyo.Constraint, active=True):
        body = pyo.value(c.body, exception=False)
        if body is None:
            continue

        lb = pyo.value(c.lower, exception=False) if c.lower is not None else None
        ub = pyo.value(c.upper, exception=False) if c.upper is not None else None

        lviol = 0.0 if lb is None else max(0.0, lb - body)
        uviol = 0.0 if ub is None else max(0.0, body - ub)
        viol = max(lviol, uviol)

        if viol > worst["violation"]:
            worst = {
                "component": c.name,
                "violation": viol,
                "body": body,
                "lower": lb,
                "upper": ub,
            }

    return worst
```

```python id="i0xn1r"
def max_bound_violation(model):
    worst = {
        "component": None,
        "violation": 0.0,
        "value": None,
        "lower": None,
        "upper": None,
    }

    for v in model.component_data_objects(pyo.Var, active=True):
        val = pyo.value(v, exception=False)
        if val is None:
            continue

        lb = pyo.value(v.lb, exception=False) if v.lb is not None else None
        ub = pyo.value(v.ub, exception=False) if v.ub is not None else None

        lviol = 0.0 if lb is None else max(0.0, lb - val)
        uviol = 0.0 if ub is None else max(0.0, val - ub)
        viol = max(lviol, uviol)

        if viol > worst["violation"]:
            worst = {
                "component": v.name,
                "violation": viol,
                "value": val,
                "lower": lb,
                "upper": ub,
            }

    return worst
```

---

## 22.13 Test expected solver status / termination policy

```python id="jt5ev6"
from pyomo.opt import SolverStatus, TerminationCondition


def assert_strict_optimal(results):
    assert results.solver.status == SolverStatus.ok
    assert results.solver.termination_condition == TerminationCondition.optimal


def assert_accepted_nlp_termination(results, *, allow_acceptable=False):
    if (
        results.solver.status == SolverStatus.ok
        and results.solver.termination_condition == TerminationCondition.optimal
    ):
        return

    if allow_acceptable and "acceptable" in str(results.solver).lower():
        return

    raise AssertionError(
        f"unexpected solve result: {results.solver.status}, "
        f"{results.solver.termination_condition}, {results.solver}"
    )
```

Pyomo’s solver recipes show the `SolverStatus.ok` and `TerminationCondition.optimal` pattern as the normal accepted-solve gate; use wrapper functions so tests encode explicit solver policy. ([Pyomo Documentation][1])

---

## 22.14 CI matrix: pinned and latest conda-forge

### `environment-pinned.yml`

```yaml id="wvvjli"
name: pyomo-ipopt-test
channels:
  - conda-forge
channel_priority: strict
dependencies:
  - python=3.11
  - pyomo
  - ipopt=3.14.19
  - pytest
```

### `environment-latest.yml`

```yaml id="ve8iik"
name: pyomo-ipopt-test-latest
channels:
  - conda-forge
channel_priority: strict
dependencies:
  - python=3.11
  - pyomo
  - ipopt
  - pytest
```

The conda-forge `ipopt` package page currently lists `ipopt` version 3.14.19, installation through `conda install conda-forge::ipopt`, and supported platforms including Linux, macOS, and Windows 64-bit targets. ([Anaconda][8])

### GitHub Actions matrix

```yaml id="b6ut9t"
name: pyomo-ipopt-tests

on:
  push:
  pull_request:
  schedule:
    - cron: "0 6 * * 1"

jobs:
  test:
    name: ${{ matrix.os }} / ${{ matrix.envfile }}
    runs-on: ${{ matrix.os }}
    continue-on-error: ${{ matrix.experimental }}
    strategy:
      fail-fast: false
      matrix:
        include:
          - os: ubuntu-latest
            envfile: environment-pinned.yml
            experimental: false
          - os: macos-latest
            envfile: environment-pinned.yml
            experimental: false
          - os: windows-latest
            envfile: environment-pinned.yml
            experimental: false
          - os: ubuntu-latest
            envfile: environment-latest.yml
            experimental: true

    defaults:
      run:
        shell: bash -el {0}

    steps:
      - uses: actions/checkout@v4

      - name: Set thread caps
        run: |
          echo "OMP_NUM_THREADS=1" >> "$GITHUB_ENV"
          echo "OPENBLAS_NUM_THREADS=1" >> "$GITHUB_ENV"
          echo "MKL_NUM_THREADS=1" >> "$GITHUB_ENV"
          echo "NUMEXPR_NUM_THREADS=1" >> "$GITHUB_ENV"

      - name: Setup micromamba
        uses: mamba-org/setup-micromamba@v2
        with:
          environment-file: ${{ matrix.envfile }}
          cache-environment: true
          cache-downloads: true

      - name: Environment diagnostics
        run: |
          python --version
          python -c "import sys; print(sys.executable)"
          python -c "import pyomo; print(pyomo.version.version)"
          which ipopt || where ipopt || true
          ipopt -v
          ipopt -= > ipopt-ampl-options.txt
          ipopt --print-options > ipopt-print-options.txt
          conda list > conda-list.txt

      - name: Run tests
        run: |
          pytest -q -m "not ipopt_slow"

      - name: Upload diagnostics
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: diagnostics-${{ matrix.os }}-${{ matrix.envfile }}
          path: |
            ipopt-ampl-options.txt
            ipopt-print-options.txt
            conda-list.txt
            **/*.log
```

GitHub Actions’ official workflow docs state that `strategy.fail-fast` controls the entire matrix, while `jobs.<job_id>.continue-on-error` applies to a single job; they can be combined so experimental matrix entries are allowed to fail while required entries still fail the workflow. ([GitHub Docs][9])

### Agent CI policy

```text id="xq3uey"
Required jobs:
  pinned env on supported OS targets

Allowed-to-fail jobs:
  latest conda-forge env
  optional OS targets
  optional linear solvers
  nightly dependency updates

Always upload:
  Ipopt option dumps
  conda list
  solver logs
  failing .nl files when keepfiles enabled
```

---

## 22.15 Windows/macOS/Linux-specific CI assertions

### Cross-platform executable test

```python id="s4pkpk"
def test_platform_ipopt_executable_resolution(ipopt_solver):
    exe = ipopt_solver.executable()
    assert exe is not None
```

### Avoid platform-specific exact logs

```text id="p1qrzg"
Do not assert:
  exact line breaks
  exact timing
  exact iteration count
  exact Ipopt banner path
  exact linear solver diagnostics across OS

Do assert:
  termination class
  key exit fragment
  objective within tolerance
  residual within tolerance
  suffix keys populated
```

### Agent rule

```text id="tzefmb"
CI goldens should be semantic, not byte-identical, unless the environment is fully pinned including OS image and solver binary.
```

---

## 22.16 Slow / nightly tests

### Mark slow tests

```python id="5336ka"
@pytest.mark.ipopt_slow
def test_large_representative_model(ipopt_solver):
    m = build_large_representative_model()
    res = ipopt_solver.solve(m, tee=False, load_solutions=False)
    assert_accepted_nlp_termination(res)
```

### Nightly invocation

```bash id="xj5d5p"
pytest -q -m "ipopt_slow or ipopt"
```

### PR invocation

```bash id="4jz0fs"
pytest -q -m "not ipopt_slow"
```

### Agent rule

```text id="vo1cit"
Keep PR tests small, deterministic, and fast.
Move large representative solves to nightly/scheduled CI.
```

---

## 22.17 Artifact capture on failure

### Pytest fixture

```python id="9gkkfm"
import pytest
from pathlib import Path


@pytest.fixture
def ipopt_log_path(tmp_path):
    return tmp_path / "ipopt-test.log"
```

### Test with log artifact

```python id="h0a2cr"
def test_model_with_log(ipopt_solver, ipopt_log_path):
    m = build_small_convex_nlp()

    res = ipopt_solver.solve(
        m,
        tee=False,
        logfile=str(ipopt_log_path),
        load_solutions=False,
    )

    assert ipopt_log_path.exists()
    assert_strict_optimal(res)
```

### CI upload

```yaml id="ow2mk3"
- name: Upload pytest logs
  if: always()
  uses: actions/upload-artifact@v4
  with:
    name: pytest-logs
    path: |
      ./**/*.log
      ./**/ipopt*.txt
```

---

## 22.18 Regression suite inventory

```text id="7dptf3"
Core tests:
  test_ipopt_available
  test_ipopt_version
  test_small_known_nlp_solution
  test_infeasible_model_detected
  test_option_propagation
  test_solve_local_options_override_persistent
  test_derivative_checker_small_model
  test_warm_start_suffix_round_trip
  test_mumps_available
  test_optional_linear_solver_probe_matrix
  test_optimal_log_fragment
  test_infeasible_log_fragment
  test_model_contract
  test_scaling_suffix_present
  test_initial_values_present
  test_no_huge_fake_bounds
  test_residual_after_solve
```

### Agent prioritization

```text id="d6zlyl"
Minimum CI:
  availability
  small known NLP
  infeasible model
  option propagation
  warm-start suffix round trip
  MUMPS availability
  model quality checks

Nightly:
  derivative checker
  large model
  linear-solver benchmark
  warm-start iteration comparison
  latest conda-forge
```

---

## 22.19 Anti-pattern catalog

```text id="eqtliy"
BAD:
  test exact Ipopt iteration counts across Linux/macOS/Windows.

GOOD:
  test objective/residual/termination and optionally compare iteration count only in pinned benchmark jobs.

BAD:
  rely on solver availability in every developer environment.

GOOD:
  skip solver tests cleanly locally, require solver in CI.

BAD:
  load solutions before checking termination in tests.

GOOD:
  use load_solutions=False and explicit load gates.

BAD:
  assert full solver logs byte-for-byte.

GOOD:
  assert stable semantic fragments.

BAD:
  run derivative checker on full model in PR CI.

GOOD:
  run derivative checker on small representative instance.

BAD:
  fail required CI on latest conda-forge dependency churn.

GOOD:
  make latest environment allowed-to-fail but upload diagnostics.

BAD:
  test optional HSL/Pardiso availability as required.

GOOD:
  require only project-supported baseline linear solver.
```

---

## 22.20 Final checklist

```text id="lzh1gx"
[ ] Add pytest marker for Ipopt-required tests.
[ ] Add minimal SolverFactory availability test.
[ ] Add small known NLP optimality test.
[ ] Add infeasible model termination/log test.
[ ] Add derivative/nonsmooth QA test on small instance.
[ ] Add option propagation test with print_user_options=yes.
[ ] Add solve-local option override test.
[ ] Add warm-start suffix round-trip test.
[ ] Add baseline linear solver availability test.
[ ] Add optional linear solver probe tests.
[ ] Add golden semantic log fragments for major termination messages.
[ ] Add model contract tests: one objective, continuous variables, starts, bounds.
[ ] Add scaling/initialization regression tests.
[ ] Use load_solutions=False in tests where termination policy matters.
[ ] Store logs and option dumps as CI artifacts.
[ ] Run pinned conda environment on required OS targets.
[ ] Run latest conda-forge environment as allowed-to-fail.
[ ] Avoid exact iteration-count and full-log goldens across platforms.
[ ] Keep PR CI fast; move large/performance solves to scheduled CI.
```

[1]: https://pyomo.readthedocs.io/en/latest/howto/solver_recipes.html?utm_source=chatgpt.com "Solver Recipes — Pyomo 6.10.1.dev0 documentation"
[2]: https://pyomo.readthedocs.io/en/latest/api/pyomo.solvers.plugins.solvers.IPOPT.IPOPT.html?utm_source=chatgpt.com "IPOPT — Pyomo 6.10.1.dev0 documentation"
[3]: https://pyomo.readthedocs.io/en/latest/getting_started/installation.html?utm_source=chatgpt.com "Installation — Pyomo 6.10.1.dev0 documentation"
[4]: https://coin-or.github.io/Ipopt/OUTPUT.html?utm_source=chatgpt.com "Ipopt Output"
[5]: https://coin-or.github.io/Ipopt/OPTIONS.html?utm_source=chatgpt.com "Ipopt Options"
[6]: https://pyomo.readthedocs.io/en/6.8.0/pyomo_modeling_components/Suffixes.html?utm_source=chatgpt.com "Suffixes — Pyomo 6.8.0 documentation"
[7]: https://pyomo.readthedocs.io/en/6.9.3/_modules/pyomo/solvers/plugins/solvers/IPOPT.html?utm_source=chatgpt.com "Source code for pyomo.solvers.plugins.solvers.IPOPT"
[8]: https://anaconda.org/conda-forge/ipopt?utm_source=chatgpt.com "ipopt - conda-forge"
[9]: https://docs.github.com/actions/using-workflows/workflow-syntax-for-github-actions?utm_source=chatgpt.com "Workflow syntax for GitHub Actions"
