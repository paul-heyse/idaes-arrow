---
name: sympy-ref
description: "Reference navigator for SymPy 1.14.x — the Python-native computer algebra system. Routes one deep-dive at docs-code-update/library_ref/symypy.md (28,701 lines, 26 chapters): scope/mental model + version anchors + numeric stack boundary (§0); core object model (§2); assumptions system (§3); manipulation primitives (§4); simplification strategy (§5); numbers/exact arithmetic/precision (§6); calculus (§7); solvers — equations/systems/inequalities/ODE/PDE/roots (§8); polynomials, domains, algebraic fields (§9); matrices, tensors, vectors, arrays (§10); functions — elementary/special/undefined/custom (§11); sets, logic, booleans, relations (§12); discrete math, combinatorics, number theory, cryptography (§13); geometry, differential geometry, holonomic, Lie, category (§14); physics modules (§15); statistics + probability (§16); plotting (§17); printing, parsing, external representation (§18); numeric bridge — subs/evalf/lambdify/ufuncify/autowrap (§19); code generation (§20); performance engineering (§21); best practices and pitfalls (§22); testing/QA (§23); interoperability with NumPy/SciPy/mpmath/JAX/CuPy/pandas/xarray/matplotlib (§24); extending SymPy (§25). Use when code touches `import sympy`, `from sympy`, `Symbol`/`symbols`/`Function`, `simplify`/`solve`/`solveset`/`integrate`/`diff`/`series`/`limit`, `lambdify`/`ufuncify`/`autowrap`/`codegen`, `Matrix`/`Poly`/`Q`/`ask`/`assuming`/`refine`, `Eq`/`.equals`/`.subs`/`.xreplace`/`.replace`, `Rational`/`Integer`/`Float`/`AlgebraicNumber`, `dsolve`/`pdsolve`, or any `sympy.*` submodule (`sympy.stats`/`sympy.physics`/`sympy.geometry`/`sympy.combinatorics`/`sympy.crypto`/`sympy.codegen`/`sympy.plotting`/`sympy.parsing`/`sympy.printing`/`sympy.matrices`/`sympy.tensor`/`sympy.vector`)."
allowed-tools: Read, Grep, Glob, Bash
model-baseline: claude-5 (2026-08)
---

# SymPy Reference Navigator

## Version anchor

All guidance assumes:

* **SymPy 1.14.0** (Python ≥ 3.9). Hard dependency on **mpmath**; performance-sensitive integer/polynomial paths benefit from optional **gmpy2**.
* **Symbolic-first**. SymPy is a Python-native computer algebra system: immutable symbolic expression trees, exact math by default, no implicit numerics.
* **Numeric bridge is explicit**. The route from SymPy to numeric execution is `.subs` + `.evalf`/`N`, `lambdify` (namespace translation to a numeric backend callable), or `sympy.codegen`/`autowrap`/`ufuncify` (compiled binaries).
* **mpmath underpins arbitrary-precision floating-point**; `gmpy2` accelerates integer + polynomial domains when present and is detected at import time.
* Stack contract:
  `SymPy expression tree → simplify/refine → lambdify (numeric callable) | codegen | LaTeX/ASCII/external | manual transcription into another solver / framework`

If a snippet pins a different SymPy version, treat it as version-sensitive and verify against the baseline above before adopting.

### Scope

This skill covers the SymPy 1.14 library surface end-to-end, organized around the canonical pipeline (declare symbols → build expressions → manipulate/simplify → solve/derive → cross numeric boundary). It does **not** cover:

* Pyomo, SCIP, or Ipopt as runtime optimization tooling — see the `pyomo-scip-ipopt-ref` skill. SymPy is used here only as a **derivation aid** that produces formulas later transcribed into Pyomo (NL-writer rules, see `pyomo-scip-ipopt-ref` operating rule "Pyomo's expression system is not SymPy").
* NumPy/SciPy/JAX/mpmath internals in their own right — they are covered here only as **lambdify backends and interop targets** (§19, §24).

---

## How the reference document is organized

`docs-code-update/library_ref/symypy.md` is 28,701 lines, organized as 26 chapter-level H1 sections. There is no upfront catalog. The chapter sequence is **§0, §2, §3, … §25** — §1 is **folded into §0** and does not exist as a separate chapter. Most chapters follow this internal shape:

| Subsection family | Typical labels |
|-------------------|----------------|
| Mental model + scope | §N.0 |
| Numbered topical deep-dives | §N.1, §N.2, … |
| Deployment recipes / patterns | §N.X (variable index) |
| Anti-pattern inventory | §N.(K-2) |
| Testing matrix | §N.(K-1) |
| Minimal full-code harness | §N.K |

Heading style is consistent: H1 `# N) <title> — agent-ready deep dive` for chapters; H2 `## N.M <title>` for subsections; H3 `## N.M.K <title>` (yes — H2 markup for the third level — see e.g. §2.3.1, §2.7.1, §4.2.1, §8.2-style three-dot indexing).

**Reading strategy.** Chapter sizes range from ~600 lines (§0) to ~2,500 lines (§19, §20, §22). Use the line ranges in the section index to load only the chapter you need: `Read(file, offset=N, limit=M)`. For agent recipes, every chapter closes with the four-subsection tail above — read the closing 200-400 lines for the deployment + anti-pattern + test + harness package.

---

## symypy.md — full section index

The table below lists every chapter with line range, key subsections, and the kind of question that routes there. Numbers are line numbers in `docs-code-update/library_ref/symypy.md` (28,701 lines total).

| § | Line | Title | Key subsections / agent value |
|---|------|-------|-------------------------------|
| **0** | 1 | Scope, versioning, mental model | §0.0 version anchor + runtime contract (1.14.0 + mpmath required + gmpy2 optional), §0.1 scope contract (what SymPy *is*: Python-native CAS, immutable expression tree, exact math), §0.2 SymPy vs NumPy/SciPy/mpmath/JAX stack boundary (decision matrix for symbolic vs numeric vs autodiff vs GPU), §0.3 core execution model + canonical pipeline (declare→construct→transform→specialize→evaluate→deploy→external), §0.4 exact-by-default philosophy, §0.5 expression tree model, §0.6 equality semantics (structural vs `Eq` vs `.equals`), §0.7 assumptions + fuzzy logic, §0.8 evaluation modes (symbolic / forced / numeric / callable / codegen), §0.9 string-input policy, §0.10 deployment archetypes (interactive / library / batch / NumPy / compiled), §0.11 "when SymPy is right vs switch now", §0.12 agent guardrails (high-priority invariants), §0.13 minimal production skeleton |
| **2** | 589 | Core object model — symbols, expressions, atoms, expression trees | §2.0 operating premise, §2.1 import policy (programmatic vs notebook), §2.2 object hierarchy map (`Basic` → `Atom`/`Expr` → `Symbol`/`Number`/`Function`/etc.), §2.3 symbol constructors (§2.3.1 `Symbol`, §2.3.2 `symbols`, §2.3.3 `Dummy`, §2.3.4 `Wild`, §2.3.5 `Function`), §2.4 assumptions at construction, §2.5 Python-operator expression construction, §2.6 strings are not expression IR, §2.7 `Basic`/`Expr`/`Number`/`Function`/Matrix taxonomy (§2.7.1-§2.7.5), §2.8 structural `==` vs `Eq` vs `.equals` (§2.8.1-§2.8.3), §2.9 expression tree anatomy (§2.9.1-§2.9.5: `.func`, `.args`, `.atoms`, `.free_symbols`, traversal), §2.10 immutability + hashability, §2.11 evaluation control (§2.11.1-§2.11.4: automatic / `evaluate=False` / `UnevaluatedExpr` / unevaluated symbolic classes), §2.12 agent recipes A-F (symbol factory / tree inspector / structural transform / equality with escalation / Wild pattern rule / evaluation-suppressed expression), §2.13 failure modes, §2.14 deployment advisory, §2.15 minimal harness |
| **3** | 1675 | Assumptions system and symbolic truth values | §3.0 contract surface, §3.1 old/core assumptions system (§3.1.1 declaration via `Symbol(name, **assumptions)`, §3.1.2 query via `is_*`, §3.1.3 common predicates), §3.2 three-valued fuzzy logic + safe-branch templates, §3.3 vanilla symbols vs weak knowledge, §3.4 assumptions-driven simplification (§3.4.1 `sqrt(x**2)` canonical, §3.4.2 Integral convergence / Piecewise reduction), §3.5 symbol identity + same-name hazards, §3.6 `Q`/`ask`/`assuming` (§3.6.1 predicate namespace, §3.6.2 `ask`, §3.6.3 contextual `assuming`), §3.7 `refine` (assumption-specific transform), §3.8 old `is_*` vs `Q`/`ask` selection rules, §3.9 other `is_*` properties (not all are assumptions), §3.10 custom function integration, §3.11 new assumptions system practical position, §3.12 deployment patterns A-F (domain registry / strict input contract / permissive contract / temp query / refinement-before-codegen / validation report), §3.13 testing matrix, §3.14 anti-patterns, §3.15 minimal harness |
| **4** | 2554 | Basic expression operations and manipulation primitives | §4.0 manipulation model, §4.1 primitive selection map, §4.2 substitution family (§4.2.1 `.subs` semantic, §4.2.2 `.xreplace` exact-node, §4.2.3 `.replace` with query/value/predicate), §4.3 evaluation (§4.3.1 `.doit(**hints)`, §4.3.2 `.evalf`/`.n`/`N`), §4.4 expansion (§4.4.1 `expand`, §4.4.2 dedicated wrappers `expand_trig`/`expand_log`/`expand_func`/`expand_complex`), §4.5 collection/factoring/rational forms (§4.5.1 `collect`, §4.5.2 `factor`, §4.5.3 `cancel`/`together`/`apart`), §4.6 term/coefficient access (`.as_coeff_add`/`.as_coeff_mul`/`.as_numer_denom`/`.coeff`), §4.7 pattern matching (`.match`/`Wild`), §4.8 traversal/structure rendering/operation counting (`srepr`/`preorder_traversal`/`bottom_up`/`count_ops`), §4.9 normalization strategies, §4.10 deployment recipes A-G, §4.11 failure-mode matrix, §4.12 minimal manipulation harness |
| **5** | 3963 | Simplification strategy and expression rewriting | §5.0 simplification contract, §5.1 automatic vs manual, §5.2 `simplify()` catchall heuristic (API + cost + custom measure), §5.3 targeted simplification map, §5.4 rational/polynomial (`factor`/`cancel`/`together`/`ratsimp`/`apart`), §5.5 trig (`trigsimp`/`expand_trig`), §5.6 power (`powsimp`/`powdenest`), §5.7 logarithmic (`logcombine`/`expand_log`), §5.8 radical (`radsimp`/`sqrtdenest`), §5.9 combinatorial + gamma (`combsimp`), §5.10 function rewriting (`.rewrite`/`expand_func`/`hyperexpand`), §5.11 canonical form vs visually-simple form, §5.12 measuring cost (`count_ops` / weighted / expression-swell audit), §5.13 pipeline profiles (rational-equality / polynomial-human / trig / power-log / radical / combinatorial / hypergeometric / codegen-prep), §5.14 CSE as simplification-adjacent, §5.15 rewriting vs simplifying, §5.16 anti-patterns, §5.17 test matrix, §5.18 minimal harness |
| **6** | 5317 | Numbers, exact arithmetic, precision, numerical evaluation | §6.0 numeric model contract, §6.1 core number classes + constants (`Integer`/`Rational`/`Float`/`AlgebraicNumber`/`pi`/`E`/`I`/`oo`/`zoo`/`nan`), §6.2 exact arithmetic + float-leakage detection, §6.3 precision control (`evalf`/`.n`/`N`/`chop`/`strict`/`maxn`/`quad`), §6.4 precision vs accuracy, §6.5 `nsimplify` (recover exact from approximate), §6.6 mpmath integration + arbitrary precision, §6.7 gmpy2 performance dependency, §6.8 numeric conversion boundaries (`float()`/`complex()`/`nfloat`), §6.9 decision matrix, §6.10 agent guardrails (prevent Python division leakage / math module leakage / detect floats before exact algorithms / normalize external numeric inputs), §6.11 evaluation recipes A-F, §6.12 testing matrix, §6.13 anti-patterns, §6.14 minimal numeric harness |
| **7** | 6344 | Calculus: differentiation, integration, limits, series | §7.0 calculus surface map, §7.1 differentiation (`diff`/`Derivative`/undefined functions/higher-order/`idiff`), §7.2 integration (`integrate`/`Integral`/convergence `conds`/algorithms/numeric `Integral.evalf`/`as_sum`/principal value/transforms), §7.3 limits (`limit`/`Limit`/Gruntz algorithm), §7.4 series expansions (`expr.series`/`series`/`Order`/`O`/leading term), §7.5 finite differences (`Derivative.as_finite_difference`/`differentiate_finite`/`finite_diff_weights`/`apply_finite_diff`), §7.6 residues/singularities/continuity-domain (`residue`/`singularities`/`continuous_domain`), §7.7 unevaluated calculus objects + `.doit()` policy, §7.8 symbolic-derive → deploy workflow, §7.9 agent decision matrix, §7.10 normalization profiles after calculus, §7.11 anti-patterns, §7.12 testing matrix, §7.13 minimal calculus harness |
| **8** | 7612 | Solving: equations, systems, inequalities, ODEs, PDEs, roots | §8.0 solver-selection map, §8.1 equation input conventions, §8.2 `solve` broad legacy solver, §8.3 `solve` return-shape taxonomy, §8.4 `solveset` set-oriented univariate, §8.5 linear systems (`linsolve`), §8.6 matrix equation solving, §8.7 nonlinear systems (`nonlinsolve`), §8.8 numerical solving (`nsolve`), §8.9 ODEs (`dsolve`), §8.10 PDEs (`pdsolve`), §8.11 inequalities (`reduce_inequalities`), §8.12 diophantine equations, §8.13 polynomial roots, §8.14 return-shape normalization, §8.15 solver-preprocessing strategy, §8.16 deployment recipes, §8.17 anti-patterns, §8.18 testing matrix, §8.19 minimal solver harness |
| **9** | 8719 | Polynomials, domains, algebraic fields, and exact algebra | §9.0 exact-polynomial mental model, §9.1 `Expr` vs `Poly`, §9.2 polynomial domains, §9.3 domain elements vs SymPy expressions, §9.4 polynomial arithmetic + exact division, §9.5 factoring/GCD/resultants/discriminants, §9.6 Groebner bases + elimination, §9.7 polynomial systems, §9.8 root isolation / `RootOf` / algebraic roots, §9.9 algebraic numbers + number fields, §9.10 `DomainMatrix`, §9.11 AGCA (ideals, modules, quotient rings), §9.12 performance rules, §9.13 agent decision matrix, §9.14 deployment recipes, §9.15 anti-patterns, §9.16 testing matrix, §9.17 minimal exact-polynomial harness |
| **10** | 9841 | Matrices, linear algebra, tensors, vectors, arrays | §10.0 layer map (related, not interchangeable), §10.1 explicit matrices: dense/sparse, mutable/immutable, §10.2 construction + shape discipline, §10.3 matrix arithmetic, §10.4 determinants/inverses/ranks/spaces/eigen-data, §10.5 solving linear systems, §10.6 matrix normal forms, §10.7 `MatrixExpr` abstract symbolic matrix algebra, §10.8 N-dim arrays, §10.9 array expressions (unevaluated tensor algebra), §10.10 `IndexedBase`/Einstein notation, §10.11 abstract tensors + canonicalization, §10.12 `sympy.vector` (coordinate systems + vector calculus), §10.13 interop boundaries, §10.14 performance + deployment rules, §10.15 common anti-patterns, §10.16 testing matrix, §10.17 minimal matrix/tensor/vector harness |
| **11** | 10944 | Functions: elementary, special, undefined, and custom symbolic functions | §11.0 function-system mental model, §11.1 built-in elementary functions, §11.2 special functions, §11.3 undefined symbolic functions, §11.4 function assumptions + evaluation, §11.5 rewriting functions (`.rewrite`), §11.6 custom `Function` subclassing (full lifecycle: `eval`/`fdiff`/`_eval_*`/printing/assumptions hooks), §11.7 numerical deployment (`evalf`/`lambdify`/`_imp_`/`implemented_function`), §11.8 function-library design rules, §11.9 anti-patterns, §11.10 testing matrix, §11.11 minimal custom-function harness |
| **12** | 12192 | Sets, logic, booleans, and relational mathematics | §12.0 layer map (fuzzy booleans vs symbolic booleans vs sets), §12.1 symbolic booleans (`And`/`Or`/`Not`/`Implies`/`Xor`/`Equivalent`/`ITE`), §12.2 relational objects (`Eq`/`Ne`/`Lt`/`Le`/`Gt`/`Ge`/`Rel`), §12.3 fuzzy booleans vs symbolic booleans, §12.4 sets (construction + operations: `Interval`/`FiniteSet`/`Union`/`Intersection`/`Complement`/`SymmetricDifference`/`ConditionSet`/`ImageSet`/`Range`), §12.5 set-logic conversion, §12.6 domain-aware solving with sets, §12.7 boolean simplification + SAT workflows (`simplify_logic`/`to_cnf`/`to_dnf`/`satisfiable`), §12.8 relational/inequality reduction workflows, §12.9 deployment recipes, §12.10 anti-patterns, §12.11 testing matrix, §12.12 minimal sets/logic harness |
| **13** | 13312 | Discrete math, combinatorics, number theory, cryptography | §13.0 scope map, §13.1 combinatorial functions (`binomial`/`factorial`/`Catalan`/`bell`/`stirling`/`harmonic`/etc.), §13.2 partitions + integer partitions, §13.3 permutations, §13.4 permutation groups + named groups, §13.5 polyhedra + symmetry groups, §13.6 Prüfer sequences / subsets / Gray code, §13.7 number theory: primes / factorization / divisors (`isprime`/`factorint`/`divisors`/`totient`/`mobius`/etc.), §13.8 modular arithmetic + residues, §13.9 continued fractions, §13.10 diophantine solving, §13.11 cryptography module (`sympy.crypto`), §13.12 finite fields + algebraic domains, §13.13 use-case mapping, §13.14 deployment recipes, §13.15 anti-patterns, §13.16 testing matrix, §13.17 minimal discrete-math harness |
| **14** | 14526 | Geometry, differential geometry, holonomic functions, specialized topics | §14.0 scope map, §14.1 geometry entities + construction (`Point`/`Line`/`Segment`/`Ray`/`Polygon`/`Triangle`/`Circle`/`Ellipse`/`Plane`), §14.2 operations + robustness rules, §14.3 maturity + production posture, §14.4 differential geometry module (`sympy.diffgeom`: manifolds, patches, coord systems, tensors), §14.5 holonomic functions (`sympy.holonomic`: D-finite functions, recurrence/differential operators), §14.6 Lie algebra module, §14.7 category theory module, §14.8 production maturity matrix, §14.9 deployment recipes, §14.10 anti-patterns, §14.11 testing matrix, §14.12 minimal specialized-topics harness |
| **15** | 15482 | Physics modules | §15.0 physics-module boundary map, §15.1 vector physics (frames, vectors, dyadics, kinematics; `sympy.physics.vector`), §15.2 mechanics (particles, rigid bodies, inertias, loads; `sympy.physics.mechanics`), §15.3 Kane's method, §15.4 Lagrange's method, §15.5 joints / `System` / actuators / linearization, §15.6 control systems (`sympy.physics.control`), §15.7 units / dimensions / quantities / unit systems (`sympy.physics.units`), §15.8 optics (`sympy.physics.optics`), §15.9 continuum mechanics, §15.10 quantum mechanics (`sympy.physics.quantum`), §15.11 biomechanics, §15.12 high-energy physics / Pauli algebra / hydrogen / oscillator / Wigner, §15.13 production maturity matrix, §15.14 deployment recipes, §15.15 anti-patterns, §15.16 testing matrix, §15.17 minimal physics harness |
| **16** | 16750 | Statistics, probability, random variables, symbolic distributions | §16.0 `sympy.stats` mental model (symbolic probability IR), §16.1 random variable construction, §16.2 interface functions (`P`/`E`/`density`), §16.3 CDF / quantile / median / entropy, §16.4 variance / covariance / correlation / moments, §16.5 conditional probability + domains, §16.6 symbolic probability classes + delayed evaluation, §16.7 sampling vs exact symbolic statistics, §16.8 continuous/discrete/finite/multivariate/matrix distributions, §16.9 independence + product spaces, §16.10 SymPy stats vs SciPy stats decision matrix, §16.11 deployment recipes, §16.12 anti-patterns, §16.13 testing matrix, §16.14 minimal statistics harness |
| **17** | 17872 | Plotting, visualization, and interactive workflows | §17.0 visualization model (symbolic → numeric sampling → backend render), §17.1 basic 2D `plot`, §17.2 2D parametric (`plot_parametric`), §17.3 3D plotting (surfaces / parametric lines / parametric surfaces), §17.4 implicit/contour/region (`plot_implicit`), §17.5 `Plot` object lifecycle, §17.6 backends + matplotlib integration, §17.7 `PlotGrid` + layout, §17.8 ASCII/text plotting, §17.9 plotting expressions vs numerical functions, §17.10 interactive printing + notebooks, §17.11 visualization best practices for exact symbolic, §17.12 deployment recipes, §17.13 anti-patterns, §17.14 testing matrix, §17.15 minimal plotting/interactive harness |
| **18** | 18994 | Printing, parsing, external representation | §18.0 external-representation taxonomy, §18.1 string + structural reps (`str`/`repr`/`srepr`/`sstr`/`StrPrinter`), §18.2 pretty printing (`pprint`/`pretty`), §18.3 LaTeX / MathML / Dot / notebook rendering, §18.4 printer internals + custom printing, §18.5 code printers (target-language projection: C / C++ / Fortran / Python / Julia / JavaScript / Rust / Octave / Mathematica / Maple / etc.), §18.6 parsing strings (`sympify`/`parse_expr`/`parse_latex`/`parse_mathematica`/`parse_maxima`/`parse_autolev`), §18.7 avoiding string manipulation of expressions, §18.8 serialization strategies (`pickle`/JSON/`srepr`), §18.9 custom object → SymPy conversion, §18.10 assignment / `Piecewise` / `Indexed` / matrices in code printers, §18.11 agent deployment recipes, §18.12 anti-patterns, §18.13 testing matrix, §18.14 minimal printing/parsing harness |
| **19** | 20459 | Numeric computation bridge: `subs`, `evalf`, `lambdify`, `ufuncify`, `autowrap` | §19.0 numeric-bridge mental model, §19.1 path-selection matrix, §19.2 simple numeric evaluation (`.subs` + `.evalf`/`N`), §19.3 `lambdify` namespace translation, §19.4 backend semantics (`math`/`mpmath`/`numpy`/`scipy`/`numexpr`/`tensorflow`/`jax`/`cupy`), §19.5 namespace boundary (do not mix SymPy and numeric backends), §19.6 argument structures + matrix + return shapes, §19.7 `_imp_`/`implemented_function`/custom functions, §19.8 large-expression lambdification (`cse` + `docstring_limit`), §19.9 NumPy vectorization, §19.10 GPU/accelerator paths (CuPy/JAX/TensorFlow), §19.11 `ufuncify` compiled NumPy ufunc generation, §19.12 `autowrap` compiled callable, §19.13 `binary_function` (compiled-binary-as-SymPy-Function), §19.14 codegen vs autowrap vs printers, §19.15 pre-deployment symbolic preparation, §19.16 deployment profiles, §19.17 anti-patterns, §19.18 testing + benchmarking matrix, §19.19 minimal numeric-bridge harness |
| **20** | 21705 | Code generation and deployment of symbolic results | §20.0 codegen mental model, §20.1 codegen stack map, §20.2 pre-codegen expression preparation, §20.3 `cse` (common subexpression elimination), §20.4 code printers (C / C++ / Fortran / Python / Julia / NumPy / TensorFlow / etc.), §20.5 `codegen` (compilable source + header generation), §20.6 `autowrap` (compile + import callable binaries), §20.7 `ufuncify` (compiled NumPy elementwise kernels), §20.8 `binary_function`, §20.9 matrix code generation, §20.10 indexed expressions + generated loops, §20.11 approximation + rewriting for efficient generated code, §20.12 generated-code testing, §20.13 deployment targets, §20.14 anti-patterns, §20.15 testing matrix, §20.16 minimal code-generation harness |
| **21** | 23071 | Performance engineering and scalability | §21.0 performance mental model, §21.1 expression swell, §21.2 `count_ops` cost proxy + rewrite gate, §21.3 `simplify()` cost + targeted simplification, §21.4 avoid repeated simplification in loops, §21.5 CSE + rewrite optimization, §21.6 caching + memoization, §21.7 choosing `Expr` vs `Poly` vs `Matrix` vs `DomainMatrix`, §21.8 assumptions reduce ambiguity + output size, §21.9 numeric acceleration (`lambdify`/`ufuncify`/JAX/CuPy), §21.10 benchmarking symbolic workflows, §21.11 memory risks for large expression trees, §21.12 pipeline architecture (derive once, execute many), §21.13 optimization patterns, §21.14 anti-patterns, §21.15 testing + regression matrix, §21.16 minimal performance/scalability harness |
| **22** | 24244 | Best practices and common pitfalls | §22.0 operating contract, §22.1 define symbols explicitly, §22.2 centralize assumptions + symbol identity, §22.3 use exact numbers by default, §22.4 avoid `math` module for symbolic work, §22.5 separate symbolic + numeric code, §22.6 handle `is_*` as three-valued logic, §22.7 distinguish fuzzy booleans from symbolic booleans, §22.8 avoid Python boolean operators on symbolic booleans, §22.9 equality discipline (`=`/`==`/`Eq`/`.equals`), §22.10 avoid string-driven workflows, §22.11 treat parsing as a security boundary, §22.12 prefer targeted transformations, §22.13 avoid unsafe `force=True` transformations, §22.14 avoid symbolic sorting/comparison unless ordering defined, §22.15 recommended reusable API patterns, §22.16 pitfall matrix, §22.17 LLM-agent guardrail checklist, §22.18 minimal best-practices harness |
| **23** | 25067 | Testing, validation, and QA for SymPy-based systems | §23.0 QA mental model, §23.1 core test categories, §23.2 structural equality tests, §23.3 mathematical equivalence tests, §23.4 assumption + fuzzy-boolean tests, §23.5 solver-output validation, §23.6 numeric regression tests, §23.7 randomized numerical testing, §23.8 property-based testing with assumptions, §23.9 generated-code validation, §23.10 branch cuts / singularities / assumptions / domains, §23.11 snapshot tests for LaTeX/codegen/external artifacts, §23.12 performance regression, §23.13 reproducibility across SymPy versions, §23.14 CI layout for SymPy-based projects, §23.15 anti-patterns, §23.16 minimal QA harness |
| **24** | 26369 | Interoperability with the Python scientific stack | §24.0 domain rule, §24.1 NumPy interop, §24.2 SciPy interop, §24.3 mpmath interop, §24.4 pandas interop, §24.5 xarray interop, §24.6 JAX interop, §24.7 CuPy interop, §24.8 matplotlib interop, §24.9 C/Fortran tooling (`codegen` / `autowrap` / `ufuncify` / F2PY / Cython), §24.10 end-to-end scientific-stack patterns, §24.11 interop anti-patterns, §24.12 deployment decision matrix, §24.13 testing matrix, §24.14 minimal interoperability harness |
| **25** | 27580 | Extending SymPy | §25.0 extension-surface map, §25.1 extension decision matrix, §25.2 undefined symbolic functions, §25.3 Python helper vs symbolic `Function`, §25.4 custom `Function` subclass (full lifecycle), §25.5 assumptions handlers for custom functions, §25.6 custom `Basic`/`Expr` subclasses, §25.7 canonicalization / immutability / hash stability, §25.8 custom printers, §25.9 custom simplification + rewrite methods, §25.10 adding calculus + numeric evaluation support, §25.11 custom domains + polynomial extensions, §25.12 contribution workflow / tests / docs / deprecations, §25.13 anti-patterns, §25.14 extension QA checklist, §25.15 minimal extension harness |

> **Note on the missing §1.** The doc folds installation + runtime into §0 and skips §1 as a chapter heading. Do not cite "symypy §1" anywhere. The numbered `# 1) Symbol declaration` etc. on lines 96-116 are code comments inside §0.3's canonical pipeline, not chapter markers.

---

## Cross-chapter topic matrix

When a topic spans multiple chapters, this is the routing table. Legend: ✅ authoritative, 🔁 cross-cut/summary, — not covered.

### Symbol creation, assumptions, and identity

| Topic | Authoritative | Cross-references |
|-------|---------------|------------------|
| `Symbol`, `symbols`, `Dummy`, `Wild`, `Function` constructors | **§2.3** ✅ | §3.5 (identity hazards), §11.3 (undefined symbolic functions), §22.1 (define explicitly) |
| Assumptions at construction (`positive=True` etc.) | **§2.4** ✅ | §3.1 (full assumption system), §22.2 (centralize) |
| `is_*` query attributes | **§3.1.2-§3.1.3** ✅ | §3.9 (other `is_*` properties not all assumptions), §22.6 (three-valued logic) |
| `Q`/`ask`/`assuming`/`refine` | **§3.6-§3.7** ✅ | §3.11 (current practical position) |
| Symbol identity / same-name hazards | **§3.5** ✅ | §22.2 |

### Expression construction, structure, traversal

| Topic | Authoritative | Cross-references |
|-------|---------------|------------------|
| Operator-driven expression construction | **§2.5** ✅ | §22.1, §22.10 |
| `Basic` / `Expr` / `Atom` / `Number` / `Function` hierarchy | **§2.7** ✅ | — |
| `.func` / `.args` / `.atoms` / `.free_symbols` / traversal | **§2.9** ✅ | §4.8 (`srepr`/`preorder_traversal`/`bottom_up`/`count_ops`) |
| Structural `==` vs `Eq` vs `.equals` | **§2.8** ✅ | §0.6, §22.9 |
| Immutability + hashability | **§2.10** ✅ | §25.7 (custom-class hash stability) |
| Evaluation control (`evaluate=False` / `UnevaluatedExpr` / unevaluated classes) | **§2.11** ✅ | §4.3.1 (`.doit`) |

### Manipulation primitives

| Topic | Authoritative | Cross-references |
|-------|---------------|------------------|
| `.subs` (semantic) vs `.xreplace` (structural) vs `.replace` (pattern/predicate) | **§4.2** ✅ | §22.12, §19.2 (subs for numeric eval) |
| `.doit`, `.evalf`, `N` | **§4.3** ✅ | §6.3 (evalf precision), §7.7 (unevaluated calculus) |
| `expand` family | **§4.4** ✅ | §5.4-§5.10 (targeted simplification) |
| `collect` / `factor` / `cancel` / `together` / `apart` | **§4.5** ✅ | §5.4 (rational simplification), §9.5 (`Poly`-level factor/GCD) |
| Pattern matching with `Wild` | **§4.7** ✅ | §25.9 (custom rewrite methods) |
| Traversal + cost (`srepr`/`preorder`/`bottom_up`/`count_ops`) | **§4.8** ✅ | §21.2-§21.5 (cost-driven optimization) |

### Simplification

| Topic | Authoritative | Cross-references |
|-------|---------------|------------------|
| `simplify()` heuristic | **§5.2** ✅ | §21.3 (cost), §22.12 (prefer targeted) |
| Targeted simplifiers (`trigsimp`/`powsimp`/`logcombine`/`radsimp`/`combsimp`/`hyperexpand`) | **§5.4-§5.10** ✅ | §22.12 |
| Rational/polynomial canonical forms | **§5.4** ✅ | §9 (`Poly` substrate) |
| Function rewriting (`.rewrite`) | **§5.10** ✅ | §11.5, §25.9 |
| `cse` (common subexpression elimination) | **§5.14** ✅ | §19.8 (lambdify CSE), §20.3 (codegen CSE), §21.5 |
| Pipeline profiles | **§5.13** ✅ | — |
| Cost measurement (`count_ops` / custom measure) | **§5.12** ✅ | §21.2 |

### Numbers, precision, exact arithmetic

| Topic | Authoritative | Cross-references |
|-------|---------------|------------------|
| `Integer` / `Rational` / `Float` / `AlgebraicNumber` | **§6.1** ✅ | §9.9 (algebraic numbers + number fields) |
| `pi` / `E` / `I` / `oo` / `zoo` / `nan` | **§6.1** ✅ | — |
| Exact arithmetic + float leakage | **§6.2** ✅ | §22.3 (use exact by default), §22.4 (avoid `math`) |
| `evalf` precision control + `chop` / `strict` | **§6.3** ✅ | §4.3.2 |
| `nsimplify` (approximate → exact recovery) | **§6.5** ✅ | — |
| mpmath integration | **§6.6** ✅ | §24.3 |
| gmpy2 performance dependency | **§6.7** ✅ | §9.12 (polynomial domain perf), §21.7 |
| `float()` / `complex()` / `nfloat` boundaries | **§6.8** ✅ | §19.2-§19.4 (full numeric bridge) |

### Calculus

| Topic | Authoritative | Cross-references |
|-------|---------------|------------------|
| `diff` / `Derivative` / `idiff` | **§7.1** ✅ | §11.6 (`fdiff` for custom functions), §25.10 |
| `integrate` / `Integral` / `conds` / transforms | **§7.2** ✅ | — |
| `limit` / `Limit` / Gruntz | **§7.3** ✅ | — |
| `series` / `Order` / `O` / leading term | **§7.4** ✅ | §11.6 (`_eval_nseries`) |
| Finite differences | **§7.5** ✅ | — |
| `residue` / `singularities` / `continuous_domain` | **§7.6** ✅ | §23.10 (branch cuts) |
| Symbolic-derive → deploy workflow | **§7.8** ✅ | §19, §20 (numeric/codegen bridges) |

### Solving

| Topic | Authoritative | Cross-references |
|-------|---------------|------------------|
| `solve` (broad legacy) | **§8.2-§8.3** ✅ | §8.0 selection map |
| `solveset` (set-oriented univariate) | **§8.4** ✅ | §12.6 (domain-aware solving with sets) |
| `linsolve` (linear systems) | **§8.5** ✅ | §10.5 (matrix `solve`) |
| `nonlinsolve` (nonlinear systems) | **§8.7** ✅ | §9.6-§9.7 (Groebner + polynomial systems) |
| `nsolve` (numerical) | **§8.8** ✅ | §19 (numeric bridge), §8.0 routing |
| `dsolve` (ODEs) | **§8.9** ✅ | §15.3-§15.4 (Kane/Lagrange-derived ODEs) |
| `pdsolve` (PDEs) | **§8.10** ✅ | — |
| `reduce_inequalities` | **§8.11** ✅ | §12.8 (inequality reduction workflows) |
| Diophantine equations | **§8.12** ✅ | §13.10 |
| Polynomial roots / `RootOf` | **§8.13** ✅ | §9.8 |

### Polynomials, domains, exact algebra

| Topic | Authoritative | Cross-references |
|-------|---------------|------------------|
| `Expr` vs `Poly` | **§9.1** ✅ | §21.7 (perf), §5.4 |
| Polynomial domains (`ZZ`/`QQ`/`RR`/`CC`/`FF_p`/extensions) | **§9.2-§9.3** ✅ | §13.12 (finite fields) |
| Factoring/GCD/resultants/discriminants | **§9.5** ✅ | §4.5 (`Expr`-level factor) |
| Groebner bases + elimination | **§9.6** ✅ | §8.7 (nonlinsolve) |
| `RootOf` / algebraic roots | **§9.8** ✅ | §8.13 |
| Algebraic numbers + number fields | **§9.9** ✅ | §6.1 |
| `DomainMatrix` | **§9.10** ✅ | §10.7 (`MatrixExpr`), §21.7 |
| AGCA (ideals/modules/quotient rings) | **§9.11** ✅ | — |

### Matrices, tensors, vectors, arrays

| Topic | Authoritative | Cross-references |
|-------|---------------|------------------|
| `Matrix` dense/sparse, mutable/immutable | **§10.1** ✅ | §2.7.5 (matrix object caveat — not `Expr`) |
| Construction + shape discipline | **§10.2** ✅ | — |
| Determinant/inverse/rank/eigen | **§10.4** ✅ | — |
| `MatrixExpr` (abstract symbolic) | **§10.7** ✅ | §21.7 |
| N-dim arrays + array expressions | **§10.8-§10.9** ✅ | — |
| `IndexedBase`/Einstein notation | **§10.10** ✅ | §20.10 (indexed in codegen) |
| Abstract tensors + canonicalization | **§10.11** ✅ | §15 (physics tensors) |
| `sympy.vector` (coords + vector calculus) | **§10.12** ✅ | §15.1 (physics vector frames) |
| Matrix code generation | **§10.x + §20.9** ✅ | §19.6 (matrix return shapes via lambdify) |

### Functions

| Topic | Authoritative | Cross-references |
|-------|---------------|------------------|
| Elementary functions | **§11.1** ✅ | — |
| Special functions | **§11.2** ✅ | §16.8 (distribution PDFs/CDFs) |
| Undefined symbolic functions (`Function('f')`) | **§11.3** ✅ | §7.1 (diff of undefined), §2.3.5 |
| Function assumptions + evaluation | **§11.4** ✅ | §25.5 (custom assumptions handlers) |
| `.rewrite` for functions | **§11.5** ✅ | §5.10 |
| Custom `Function` subclass | **§11.6** ✅ | §25.4-§25.10 (full extension lifecycle) |
| `_imp_` / `implemented_function` | **§11.7** ✅ | §19.7 (lambdify of custom functions) |

### Sets, logic, booleans

| Topic | Authoritative | Cross-references |
|-------|---------------|------------------|
| Symbolic booleans (`And`/`Or`/`Not`/`ITE`) | **§12.1** ✅ | §22.7-§22.8 |
| Fuzzy booleans (three-valued logic) | **§12.3** ✅ | §3.2 |
| Relational objects | **§12.2** ✅ | §0.6, §22.9 |
| Sets (`Interval`/`FiniteSet`/`Union`/`Intersection`/`Complement`/`ConditionSet`/`ImageSet`/`Range`) | **§12.4** ✅ | §8.4 (`solveset` returns sets) |
| Set ↔ logic conversion | **§12.5** ✅ | — |
| Domain-aware solving | **§12.6** ✅ | §8.4 |
| Boolean simplification + SAT | **§12.7** ✅ | — |
| Inequality reduction | **§12.8** ✅ | §8.11 |

### Discrete math, number theory, cryptography

| Topic | Authoritative | Cross-references |
|-------|---------------|------------------|
| Combinatorial functions | **§13.1** ✅ | §16.1 (distribution support) |
| Partitions | **§13.2** ✅ | — |
| Permutations + groups | **§13.3-§13.4** ✅ | §14.6 (Lie algebra) |
| Polyhedra + symmetry | **§13.5** ✅ | §14.1 (geometry) |
| Number theory (primes/factor/divisors/totient/mobius) | **§13.7** ✅ | — |
| Modular arithmetic + residues | **§13.8** ✅ | §13.12 (finite fields) |
| Continued fractions | **§13.9** ✅ | — |
| Diophantine | **§13.10** ✅ | §8.12 |
| Cryptography (`sympy.crypto`) | **§13.11** ✅ | — |
| Finite fields + algebraic domains | **§13.12** ✅ | §9.2-§9.3 |

### Geometry, differential geometry, specialized

| Topic | Authoritative | Cross-references |
|-------|---------------|------------------|
| 2D/3D geometry entities | **§14.1-§14.2** ✅ | §14.3 (production posture) |
| Differential geometry | **§14.4** ✅ | §15.10 (quantum), §15.12 |
| Holonomic functions | **§14.5** ✅ | — |
| Lie algebra | **§14.6** ✅ | §13.4 |
| Category theory | **§14.7** ✅ | — |

### Physics

| Topic | Authoritative | Cross-references |
|-------|---------------|------------------|
| Vector physics (frames/dyadics/kinematics) | **§15.1** ✅ | §10.12 |
| Mechanics (particles/rigid bodies/inertias) | **§15.2** ✅ | — |
| Kane's method | **§15.3** ✅ | §8.9 (resulting ODEs) |
| Lagrange's method | **§15.4** ✅ | §8.9 |
| Joints / `System` / actuators / linearization | **§15.5** ✅ | — |
| Control systems | **§15.6** ✅ | — |
| Units / dimensions / `UnitSystem` | **§15.7** ✅ | — |
| Optics | **§15.8** ✅ | — |
| Continuum mechanics | **§15.9** ✅ | — |
| Quantum mechanics | **§15.10** ✅ | §10.11 |
| Biomechanics | **§15.11** ✅ | — |
| HEP / Pauli / hydrogen / oscillator / Wigner | **§15.12** ✅ | — |

### Statistics + probability

| Topic | Authoritative | Cross-references |
|-------|---------------|------------------|
| `sympy.stats` symbolic probability IR | **§16.0-§16.1** ✅ | — |
| `P`/`E`/`density`/CDF/quantile | **§16.2-§16.3** ✅ | — |
| Variance/covariance/correlation | **§16.4** ✅ | — |
| Conditional probability + domains | **§16.5** ✅ | §12.4 |
| Delayed evaluation | **§16.6** ✅ | §2.11 |
| Sampling vs symbolic | **§16.7** ✅ | — |
| Distributions (continuous/discrete/finite/multivariate/matrix) | **§16.8** ✅ | §11.2 |
| SymPy stats vs SciPy stats | **§16.10** ✅ | §24.2 |

### Plotting + visualization

| Topic | Authoritative | Cross-references |
|-------|---------------|------------------|
| 2D `plot`, parametric, 3D, implicit | **§17.1-§17.4** ✅ | — |
| `Plot` lifecycle | **§17.5** ✅ | — |
| Backends + matplotlib | **§17.6** ✅ | §24.8 |
| Plot expressions vs numerical functions | **§17.9** ✅ | §19 |
| Interactive printing + notebooks | **§17.10** ✅ | §18.3 |

### Printing, parsing, external representation

| Topic | Authoritative | Cross-references |
|-------|---------------|------------------|
| `str` / `srepr` / `sstr` / `pretty` / `pprint` | **§18.1-§18.2** ✅ | — |
| LaTeX / MathML / Dot / notebook rendering | **§18.3** ✅ | — |
| Custom printer internals | **§18.4** ✅ | §25.8 |
| Code printers (C/C++/Fortran/Python/Julia/JS/Rust/Octave/Mathematica/Maple) | **§18.5** ✅ | §20.4 |
| `sympify` / `parse_expr` / `parse_latex` / `parse_mathematica` / `parse_maxima` / `parse_autolev` | **§18.6** ✅ | §22.10-§22.11 |
| Avoiding string manipulation | **§18.7** ✅ | §22.10 |
| Serialization (`pickle` / JSON / `srepr`) | **§18.8** ✅ | §23.11 |

### Numeric bridge (symbolic → numeric callable)

| Topic | Authoritative | Cross-references |
|-------|---------------|------------------|
| `.subs` + `.evalf`/`N` for direct evaluation | **§19.2** ✅ | §4.3.2, §6.3 |
| `lambdify` namespace translation | **§19.3** ✅ | §6.8, §11.7 |
| Backends (`math`/`mpmath`/`numpy`/`scipy`/`numexpr`/`tensorflow`/`jax`/`cupy`) | **§19.4** ✅ | §24 |
| Namespace boundary (don't mix SymPy + numeric backends) | **§19.5** ✅ | §22.5 |
| Matrix / array return shapes | **§19.6** ✅ | §10.x |
| `_imp_` / `implemented_function` | **§19.7** ✅ | §11.7 |
| CSE + `docstring_limit` for large expressions | **§19.8** ✅ | §5.14, §20.3 |
| NumPy vectorization | **§19.9** ✅ | §24.1 |
| GPU/accelerator (CuPy / JAX / TensorFlow) | **§19.10** ✅ | §24.6-§24.7 |
| `ufuncify` (compiled NumPy ufunc) | **§19.11** ✅ | §20.7 |
| `autowrap` (compiled callable) | **§19.12** ✅ | §20.6 |
| `binary_function` (compiled-binary-as-SymPy-Function) | **§19.13** ✅ | §20.8 |

### Code generation

| Topic | Authoritative | Cross-references |
|-------|---------------|------------------|
| Pre-codegen expression preparation | **§20.2** ✅ | §5.15, §11.7 |
| `cse` (common subexpression elimination) | **§20.3** ✅ | §5.14, §19.8 |
| Code printers (per-language) | **§20.4** ✅ | §18.5 |
| `codegen` (compilable source + header) | **§20.5** ✅ | — |
| `autowrap` / `ufuncify` / `binary_function` | **§20.6-§20.8** ✅ | §19.11-§19.13 |
| Matrix codegen | **§20.9** ✅ | §10 |
| Indexed expressions + generated loops | **§20.10** ✅ | §10.10 |
| Approximation + rewriting for efficient code | **§20.11** ✅ | §5.13 (codegen-prep profile) |

### Performance + scalability

| Topic | Authoritative | Cross-references |
|-------|---------------|------------------|
| Expression swell | **§21.1** ✅ | §5.12 |
| `count_ops` as rewrite gate | **§21.2** ✅ | §5.12 |
| `simplify` cost + targeted simplification | **§21.3-§21.4** ✅ | §5.2 |
| CSE + rewrite optimization | **§21.5** ✅ | §5.14, §19.8, §20.3 |
| Caching + memoization | **§21.6** ✅ | — |
| Substrate choice (`Expr` vs `Poly` vs `Matrix` vs `DomainMatrix`) | **§21.7** ✅ | §9.10 |
| Assumptions reduce output size | **§21.8** ✅ | §3 |
| Numeric acceleration | **§21.9** ✅ | §19 |
| Benchmarking | **§21.10** ✅ | §23.12 |
| Memory risks | **§21.11** ✅ | — |
| "Derive once, execute many" pipeline | **§21.12** ✅ | §0.10 deployment archetypes |

### Best practices, testing, interop, extensions

| Topic | Authoritative | Cross-references |
|-------|---------------|------------------|
| Best-practices catalog (define symbols / centralize assumptions / exact-by-default / etc.) | **§22.1-§22.15** ✅ | spans entire doc |
| LLM-agent guardrail checklist | **§22.17** ✅ | §0.12 |
| Structural + mathematical equality tests | **§23.2-§23.3** ✅ | §2.8 |
| Solver-output validation | **§23.5** ✅ | §8 |
| Property-based testing with assumptions | **§23.8** ✅ | §3 |
| Generated-code validation | **§23.9** ✅ | §20 |
| Snapshot tests for LaTeX/codegen | **§23.11** ✅ | §18 |
| Performance regression | **§23.12** ✅ | §21.10 |
| Reproducibility across SymPy versions | **§23.13** ✅ | §0.0 version anchor |
| CI layout | **§23.14** ✅ | — |
| NumPy / SciPy / mpmath / pandas / xarray / JAX / CuPy / matplotlib | **§24.1-§24.8** ✅ | §19 |
| C / Fortran / F2PY / Cython tooling | **§24.9** ✅ | §20 |
| Undefined functions vs custom `Function` | **§25.2-§25.4** ✅ | §11.3, §11.6 |
| Custom `Function` subclass full lifecycle | **§25.4-§25.10** ✅ | §11.6 |
| Custom `Basic`/`Expr` subclasses | **§25.6** ✅ | — |
| Custom printers | **§25.8** ✅ | §18.4 |
| Custom simplification + rewrite | **§25.9** ✅ | §5, §11.5 |
| Custom domains + polynomial extensions | **§25.11** ✅ | §9.2 |

---

## Operating rules

These are non-negotiable disciplines when working with SymPy. Each is grounded in a section of the deep dive.

1. **SymPy is symbolic-first; the numeric crossing is explicit.** Numeric evaluation happens only at the bridge: `.subs(...).evalf()`, `lambdify(...)`, `ufuncify`, or `autowrap`. Within the symbolic layer, never mix in NumPy arrays, `math.sin`, or raw Python floats — they corrupt exact arithmetic and break assumptions. (§0.2, §19.5, §22.4-§22.5)

2. **Exact arithmetic by default.** Use `Integer`, `Rational`, `S.Half`, `AlgebraicNumber`, `pi`, `E`, `I`, `oo`; never `0.5`, `1/3`, or `math.pi` in symbolic code. A single Python `0.5` silently flips downstream simplification to floating-point and breaks `factor`/`cancel`/`simplify` correctness. Convert decimals at the boundary with `Rational(1, 2)` or `nsimplify(...)`. (§6.2, §22.3)

3. **Symbols are immutable; structural `==` is not mathematical equivalence.** `x = Symbol('x')` is a value-type identity. Two `Symbol('x')` constructed independently compare equal iff their name + assumptions hash matches. `cos(x)**2 + sin(x)**2 == 1` returns `False`. Use `Eq(lhs, rhs)` for symbolic equations, `.equals(other)` for an attempted mathematical-equivalence test, or `simplify(lhs - rhs) == 0` after canonicalization. (§0.6, §2.8, §22.9)

4. **Three-valued fuzzy logic.** `is_*` predicates return `True` / `False` / `None`. Never branch on `x.is_positive` as if it were boolean — write fuzzy-safe branches that handle `None` explicitly. (§3.2, §22.6)

5. **`.subs` is semantic, `.xreplace` is structural — choose deliberately.** `expr.subs(x, y)` may simplify mathematical subexpressions during substitution; `expr.xreplace({x: y})` does not. Use `subs` when you want post-substitution simplification, `xreplace` when fidelity to the original expression tree matters (caching, source-faithful rewriting). `.replace` adds query/pattern/predicate matching with its own deployment rules. (§4.2, §22.12)

6. **`simplify()` is a heuristic and expensive; targeted simplifiers are nearly always faster and more correct.** `simplify` runs ~10 normalization passes with a cost model. For known structure, call `trigsimp`, `powsimp`, `logcombine`, `radsimp`, `combsimp`, `hyperexpand`, `factor`, `cancel`, or `together` directly. Reserve `simplify(expr, measure=...)` for unknown-shape input or one-shot human-facing output. (§5.2, §5.4-§5.10, §21.3, §22.12)

7. **`lambdify` is the canonical symbolic → numeric callable bridge — pick the backend deliberately.** `lambdify(args, expr, modules=...)` chooses between `math` (scalar), `mpmath` (arbitrary precision), `numpy` (vectorized, default for many backends), `scipy` (special functions), `numexpr`, `tensorflow`, `jax`, `cupy`. The wrong backend corrupts vectorization, parallelism, or numerical semantics. Validate via round-trip tests. (§19.3-§19.4, §23.6)

8. **Strings are NOT expression IR.** Build expressions with `Symbol(...)` / `symbols(...)` / Python operators. Do not parse-then-edit-as-string; use `.func`/`.args` for structural inspection and `.xreplace`/`.replace`/`.subs` for transformation. (§2.6, §22.10)

9. **`parse_expr` (and friends) is a security boundary.** `sympify`/`parse_expr`/`parse_latex` evaluate input through Python's parser — never feed untrusted input without an explicit sandboxed transformation. (§18.6, §22.11)

10. **Mind the matrix layer.** `Matrix` (mutable dense), `ImmutableMatrix`, `SparseMatrix`, `MatrixSymbol`, `MatrixExpr`, `DomainMatrix` are related but not interchangeable. Matrix objects are deliberately **outside** the `Expr` hierarchy — algebraic operations apply componentwise, not as symbolic-matrix algebra (use `MatrixExpr` for that). `DomainMatrix` is the high-performance exact backend. (§2.7.5, §10.0, §10.7, §10.13, §21.7)

11. **`Float(s, n)` does not magically add precision.** `Float("1.234", 50)` pads with zeros to 50 digits — it does not make 1.234 more accurate. Derive symbolically first, then `evalf(50)`. (§6.4)

12. **Solver function selection is structural, not interchangeable.** `solve` is the legacy broad solver with heuristic return shapes; `solveset` is the set-oriented univariate replacement; `linsolve` for linear systems; `nonlinsolve` for nonlinear; `nsolve` for numeric; `dsolve` for ODEs; `pdsolve` for PDEs; `reduce_inequalities` for inequalities. Pick by problem class (§8.0 selection map), normalize return shapes explicitly (§8.14), and validate (§8.18, §23.5). (§8 throughout)

13. **`Expr` vs `Poly` is a deliberate substrate choice.** Polynomial-heavy work (factor, GCD, Groebner, resultants, modular arithmetic) is orders of magnitude faster in `Poly` over a typed domain (`ZZ`/`QQ`/`FF_p`/algebraic extension) than as raw `Expr`. Wrap once with `Poly(expr, *gens, domain=...)`; unwrap with `.as_expr()` at the boundary. (§9.1, §9.2, §21.7)

14. **Derive once, deploy many.** The canonical pipeline is: declare symbols → build expression → simplify → specialize via `subs`/`xreplace` → produce a numeric callable via `lambdify` (or codegen for native compilation) → call the callable many times in production. Do not call `simplify` inside hot loops. (§0.10, §21.12)

15. **Extending SymPy goes through `Function` subclasses, not monkey-patching.** Custom symbolic functions implement `eval` (auto-eval rules), `fdiff` (derivative), `_eval_*` hooks (numeric eval / nseries / rewrite / printing), and assumption handlers — see §25.4 for the full lifecycle. Custom `Basic`/`Expr` subclasses get printers and simplification rules via `__init_subclass__`/registry hooks (§25.6, §25.8-§25.9). Maintain immutability and stable `__hash__` (§25.7). (§11.6, §25 throughout)

16. **Equality discipline at API boundaries.** Inputs that may be strings or float-laden go through `sympify`/`S(...)` once at the boundary; downstream code assumes `Basic` objects. Boolean returns from user-facing API should be `Eq(...)` (symbolic) or Python `bool` (decided) — never a raw `Relational` mixed with `bool` in the same return type. (§22.9, §22.10, §22.15)

---

## Decision trees

### "Which chapter do I open first?"

```
Question is about symbols / assumptions / equality / tree structure?
  -> §2 (object model) for construction + traversal
  -> §3 (assumptions) for predicates + fuzzy logic + refine
  -> §0.6 + §2.8 for equality semantics

Question is about manipulating an existing expression (substitute / expand / factor)?
  -> §4 (manipulation primitives) for the toolkit
  -> §5 (simplification) for canonicalization strategy

Question is about exact arithmetic / precision / Float / numeric literals?
  -> §6 (numbers)

Question is about calculus (diff / integrate / limit / series)?
  -> §7

Question is about solving (equations / systems / inequalities / ODE / PDE / roots)?
  -> §8

Question is about polynomial algebra (factor / GCD / Groebner / RootOf / algebraic extensions)?
  -> §9

Question is about matrices / tensors / arrays / vectors?
  -> §10

Question is about elementary / special / undefined / custom symbolic functions?
  -> §11

Question is about sets / logic / booleans / relations?
  -> §12

Question is about combinatorics / number theory / cryptography?
  -> §13

Question is about geometry / differential geometry / Lie / holonomic / category theory?
  -> §14

Question is about a physics module (mechanics / control / units / optics / quantum / etc.)?
  -> §15

Question is about probability / random variables / symbolic statistics?
  -> §16

Question is about plotting?
  -> §17

Question is about printing / parsing / LaTeX / code printers / serialization?
  -> §18

Question is about producing a numeric callable from a symbolic expression?
  -> §19 (lambdify + ufuncify + autowrap + backend semantics)

Question is about generating C / Fortran / Python / Julia source from symbolic expressions?
  -> §20 (codegen)

Question is about making a SymPy workflow faster or scaling to large expressions?
  -> §21

Question is about best practices / common pitfalls / API design / agent guardrails?
  -> §22 + §0.12

Question is about testing SymPy-based code?
  -> §23

Question is about NumPy / SciPy / mpmath / JAX / CuPy / pandas / xarray / matplotlib / Cython interop?
  -> §24

Question is about adding new symbolic functions / classes / printers / simplification rules?
  -> §25
```

### "How do I get from a symbolic expression to a numeric value or callable?"

```
Single point evaluation, exact (Rational/AlgebraicNumber input)?
  expr.subs(point).simplify()                                         (§4.2, §4.3)

Single point evaluation, arbitrary precision float?
  expr.subs(point).evalf(50)                                          (§6.3)
  # Always include `chop=True` to remove numerical noise.

Many points, scalar Python floats?
  f = lambdify(args, expr, modules="math")                            (§19.3, §19.4)

Many points, NumPy arrays (vectorized)?
  f = lambdify(args, expr, modules="numpy")                           (§19.4, §19.9)

Many points with special functions (gamma, bessel, etc.)?
  f = lambdify(args, expr, modules=["numpy", "scipy"])                (§19.4)

Many points with arbitrary precision?
  f = lambdify(args, expr, modules="mpmath")                          (§19.4)

GPU / autodiff?
  f = lambdify(args, expr, modules="jax")    # or "cupy"/"tensorflow"  (§19.4, §19.10)

Massive expression, want CSE-shared subexpressions in the callable?
  f = lambdify(args, expr, cse=True)                                  (§19.8, §5.14)

Compiled-once NumPy ufunc?
  f = ufuncify(args, expr)                                            (§19.11, §20.7)

Compiled callable with full source generation?
  bf = autowrap(expr, args=args, language="C")                        (§19.12, §20.6)

Want generated C / Fortran source as a file?
  [(c_name, c_code), (h_name, h_code)] = codegen((name, expr), "C")   (§20.5)

Need to inject a Python-side callable as a SymPy Function?
  Custom Function with `_imp_` or `implemented_function`              (§11.7, §19.7)
```

### "Which solver function for which problem?"

```
Univariate algebraic equation, want set-typed answer?           solveset(eq, var)          (§8.4)
Univariate / multivariate algebraic equation, legacy shape?     solve(eq, *vars)           (§8.2-§8.3)
Linear system Ax = b (symbolic)?                                linsolve([eqns], *vars)    (§8.5)
Linear system from a Matrix?                                    A.solve(b)                 (§10.5)
Nonlinear system, exact?                                        nonlinsolve([eqs], *vars)  (§8.7)
Nonlinear system, numeric (good starting point)?                nsolve([eqs], *vars, x0)   (§8.8)
ODE?                                                            dsolve(diffeq, f(x))       (§8.9)
PDE?                                                            pdsolve(pde, u)            (§8.10)
Inequalities?                                                   reduce_inequalities(ineqs) (§8.11)
Diophantine?                                                    diophantine(eq)            (§8.12, §13.10)
Polynomial roots (exact, including RootOf)?                     roots(poly) / Poly.all_roots()/RootOf  (§8.13, §9.8)
Groebner basis / elimination?                                   groebner([polys])          (§9.6)
```

### "Which simplification primitive?"

```
General-purpose, unknown structure, one-shot output?            simplify(expr [, measure=count_ops])   (§5.2)
Rational expression, want canonical form?                        cancel(expr)                          (§5.4)
Rational expression, want factored numerator + denominator?      factor(expr)                          (§4.5, §5.4)
Rational expression, partial-fraction decomposition?             apart(expr, var)                      (§4.5)
Common denominator?                                              together(expr)                        (§4.5)
Polynomial expand?                                               expand(expr)                          (§4.4)
Trig combine / expand?                                           trigsimp / expand_trig                (§5.5)
Power combine / expand?                                          powsimp / powdenest                   (§5.6)
Log combine / expand?                                            logcombine / expand_log               (§5.7)
Radical denest / simplify?                                       sqrtdenest / radsimp                  (§5.8)
Combinatorial / gamma?                                           combsimp                              (§5.9)
Hypergeometric → elementary?                                     hyperexpand                           (§5.10)
Rewrite via target function?                                     expr.rewrite(target)                  (§5.10, §11.5)
Common subexpression elimination (codegen prep)?                 cse([exprs])                          (§5.14, §20.3)
```

### "Symbolic vs numeric — which library?"

```
Need exact symbolic transformation (proof, simplification, derivation, identity)?
  -> SymPy                                                            (§0.1, §0.4)

Need to derive a formula once and use it many times in a numerical inner loop?
  -> SymPy to derive + simplify, lambdify (or codegen) once, call many times
                                                                       (§0.10, §21.12)

Need vectorized numerical computation over large arrays?
  -> NumPy (use SymPy only for derivation)                             (§0.2, §24.1)

Need autodiff or GPU?
  -> JAX / PyTorch / TensorFlow (use SymPy for derivation; lambdify or
     manual transcription into autodiff framework)                     (§19.10, §24.6)

Need arbitrary-precision floating-point arithmetic only?
  -> mpmath directly (SymPy uses it under the hood)                    (§6.6, §24.3)

Need MILP / MINLP / LP / NLP solver?
  -> NOT SymPy — see the pyomo-scip-ipopt-ref skill. SymPy can derive
     formulas that are then transcribed into Pyomo expressions.

Need nonsmooth (abs / max / min / piecewise) reformulation for a smooth solver?
  -> SymPy refine / rewrite (§3.7, §5.10) for the symbolic side; downstream
     solver-aware transcription handled by the optimizer adapter.
```

### "I have a SymPy Function I want to extend (assumptions / derivative / numeric / printing)"

```
Just need an unspecified symbol-like function (no semantics)?
  f = Function('f')                                                    (§11.3)

Need to attach a numeric implementation for lambdify?
  implemented_function('f', lambda *args: ...)
  or class MyFn(Function): _imp_ = staticmethod(lambda ...)            (§11.7, §19.7)

Need exact algebra (eval / assumptions / printing / diff / rewrite)?
  class MyFn(Function):
      @classmethod
      def eval(cls, *args): ...               # auto-evaluate rules    (§11.6, §25.4)
      def fdiff(self, argindex=1): ...        # derivative              (§7.1, §25.10)
      def _eval_evalf(self, prec): ...        # numeric                 (§25.10)
      def _eval_rewrite(self, rule, args, **kwargs): ...                (§25.9)
      def _latex(self, printer): ...          # printer                 (§25.8)
      # assumption handlers via _eval_is_*                              (§25.5)

Need a custom Basic/Expr subclass (not a function)?
  See §25.6 for full subclass requirements (immutability, hash, args,
  printers, simplification hooks).
```

---

## Known gotchas

| Gotcha | Detail | Reference |
|--------|--------|-----------|
| **SymPy `==` is structural, not mathematical** | `expr1 == expr2` checks AST structure. `cos(x)**2 + sin(x)**2 == 1` is `False`. Use `Eq(lhs, rhs)` for symbolic equations, `.equals(other)` for an attempted equivalence test, or `simplify(lhs - rhs) == 0` after canonicalization. | §0.6, §2.8, §22.9 |
| **Float contamination corrupts exact algorithms** | `factor(x**2 - 0.5)` returns approximate factors because `0.5` injects `Float`. Use `Rational(1, 2)` or `nsimplify(...)` at the boundary. | §6.2, §6.10, §22.3 |
| **`subs` is semantic, `xreplace` is structural** | `.subs(x, y)` may simplify mathematical subexpressions during substitution; `.xreplace({x: y})` does not. Choose deliberately. | §4.2, §22.12 |
| **`Float(s, n)` does not retroactively add precision** | `Float("1.234", 50)` pads with zeros to 50 digits — it does not make 1.234 more accurate. Derive symbolically first, then `evalf(50)`. | §6.4 |
| **`is_*` is fuzzy three-valued** | `Symbol('x').is_positive` is `None` (no assumption), not `False`. Never branch on `is_*` as a bool — always handle `None`. | §3.2, §22.6 |
| **Two `Symbol('x')` constructed independently** | They are equal **iff** their name + assumption set hash matches. `Symbol('x', positive=True) != Symbol('x')`. Centralize symbol construction in a registry. | §3.5, §22.2 |
| **`simplify` runs many strategies + can blow up cost** | `simplify(x**100 + 1)` may attempt expensive factorizations. Use a `measure=count_ops` cap or targeted simplifiers. | §5.2, §5.12, §21.3 |
| **Boolean operators on symbolic** | `x > 0 and y > 0` raises `TypeError` because relational objects aren't Python booleans. Use `And(x > 0, y > 0)`. | §22.8, §12.1 |
| **`solve` return shape is heuristic** | `solve(eq, x)` returns a list, dict, or set depending on input shape and number of variables. Normalize via the §8.14 protocol or prefer `solveset`. | §8.2-§8.3, §8.14 |
| **`solveset` returns sets, not solution lists** | `solveset(x**2 - 1, x) == FiniteSet(-1, 1)`. Iterate the set or call `.args` to get elements; don't treat as a list. | §8.4, §12.4 |
| **`Matrix` is not `Expr`** | Algebraic operators (`+`/`*`) on `Matrix` operate componentwise. `Matrix` objects sit outside the `Expr` hierarchy. Use `MatrixExpr` / `MatrixSymbol` for symbolic-matrix algebra. | §2.7.5, §10.0, §10.7 |
| **`Matrix(...)` is mutable; `ImmutableMatrix(...)` is hashable** | Mutable matrices cannot live inside expressions (no hash). Use `ImmutableMatrix` (or `Matrix(...).as_immutable()`) when the matrix participates in a symbolic expression. | §10.1 |
| **`Poly` and `Expr` are different substrates** | `Poly(expr, x, domain=QQ)` operations are orders of magnitude faster than `Expr.factor()` for polynomial-heavy work. Always wrap once, unwrap at the boundary. | §9.1, §21.7 |
| **`DomainMatrix` requires a typed domain** | Created with `DomainMatrix.from_list(rows, shape, domain=QQ)`. Operations preserve the domain; converting to `Matrix` at the boundary via `.to_Matrix()`. | §9.10, §10.7 |
| **`lambdify(args, expr)` default modules choice depends on expression** | If `expr` contains `gamma`, `besselj`, etc., the default `modules` may pull in NumPy + SciPy implicitly. Always set `modules=` explicitly for reproducibility. | §19.3-§19.4 |
| **`lambdify` and Python keywords** | `lambdify(['if', 'else'], expr)` raises; SymPy symbols whose names collide with Python keywords break the generated source. Rename or use `Dummy(...)`. | §19.3, §2.3.3 |
| **`lambdify` namespace boundary** | The generated callable lives in the numeric namespace; SymPy `Symbol`s passed in are coerced to floats. Never pass a `Matrix` of `Symbol`s to a NumPy-mode lambdified function expecting numeric input. | §19.5, §19.6 |
| **`UnevaluatedExpr` does not propagate through all operations** | It blocks the next auto-simplification step at its position but inner / outer evaluation still happens. For full evaluation suppression, use unevaluated symbolic classes (`Add(... evaluate=False)`). | §2.11.3, §2.11.4 |
| **`assuming(*facts)` only affects new `ask` queries inside the context** | It does **not** retroactively change the assumptions on existing symbols. Use `Symbol(name, **assumptions)` or `refine(expr, Q.predicate(symbol))` for structural assumptions. | §3.6.3, §3.7 |
| **`refine` is assumption-specific** | `refine(Abs(x), Q.positive(x))` gives `x`; without the assumption it stays `Abs(x)`. The assumption argument is required. | §3.7 |
| **`sympify` is a security boundary** | `sympify("__import__('os').system('rm -rf /')")` does **not** execute arbitrary code thanks to SymPy's safe parser — but untrusted input should still be validated, sandboxed, or routed through `parse_expr(transformations=...)`. | §18.6, §22.11 |
| **`parse_latex` requires the `antlr4-python3-runtime` package** | Otherwise raises `ImportError` at first use. Pin the dep if you parse LaTeX in production. | §18.6 |
| **`series` / `O` truncate silently** | `(1 + x).series(x, 0, 3) == 1 + x + O(x**3)`. The `O(...)` term is structural; arithmetic with `O` follows order-of-magnitude rules, not exact algebra. Strip with `.removeO()`. | §7.4 |
| **`integrate` may return `Integral(...)` unchanged** | When SymPy cannot find a closed form, it returns an unevaluated `Integral`. Check via `isinstance(result, Integral)`. Use `.evalf()` for numeric, or supply `conds=` / `meijerg=True` to attempt other algorithms. | §7.2, §7.7 |
| **`dsolve` return shape is per-equation** | Single ODE → `Eq(f(x), ...)`; system → list of `Eq`. Some ODEs return only existence (`hint='all'` returns dict of attempted hints). Normalize before downstream use. | §8.9 |
| **`integrate` arbitrary constants are named `C1`, `C2`, ...** | They are `Symbol` objects; collisions with user `Symbol('C1')` are possible. Use `dsolve(..., simplify=False, ics={...})` to apply initial conditions early. | §8.9 |
| **Random sampling vs symbolic stats** | `density(X)` gives the symbolic PDF; `sample(X, size=...)` requires a backend (NumPy or SciPy). Sampling does not preserve symbolic exactness; use only for downstream Monte-Carlo. | §16.7 |
| **`Poly` operations dispatch on domain** | `Poly(x**2 + 1, x, domain=QQ).factor_list()` does NOT factor over `i`; use `domain=QQ.algebraic_field(I)` or `extension=I`. | §9.2, §9.5 |
| **`cse` may reorder evaluation** | The replacements list is topologically sorted; in pathological cases an `Integer(1) / Integer(2)` substring may be shared in unintuitive ways. Validate generated code via round-trip evaluation. | §5.14, §19.8, §20.3 |
| **Plotting an expression with infinite range** | `plot(x**2)` samples a default range `(-10, 10)`; `plot(1/x)` triggers `RuntimeWarning` at the discontinuity. Pass `(symbol, low, high)` explicitly. | §17.1 |
| **Section 1 is missing from symypy.md** | The doc folds installation + runtime into §0; the chapter sequence is §0, §2, §3, §4, ... §25. The numbered code-comment headers `# 1)` ... `# 7)` inside §0.3 (lines 96-116) are pipeline steps in a code example, not chapter markers. | doc structure |

---

## Glossary

| Term | Authoritative definition |
|------|--------------------------|
| **Symbolic-first** | §0.1, §0.2 |
| **Stack boundary (SymPy vs NumPy / SciPy / mpmath / JAX / Pyomo)** | §0.2 |
| **Canonical pipeline (declare → construct → transform → specialize → evaluate → deploy)** | §0.3 |
| **Exact-by-default philosophy** | §0.4 |
| **Expression tree model** | §0.5, §2.7, §2.9 |
| **Structural vs mathematical equality** | §0.6, §2.8 |
| **Deployment archetypes (interactive / library / batch / NumPy runtime / compiled kernel)** | §0.10 |
| **`Symbol` / `symbols` / `Dummy` / `Wild` / `Function`** | §2.3 |
| **Operator-driven construction (`+`, `*`, `**`, `==`, etc.)** | §2.5 |
| **`Basic` / `Expr` / `Atom` / `Number` / `Function`** | §2.7 |
| **`Eq(lhs, rhs)` vs `==` vs `.equals(...)`** | §2.8 |
| **`.func`, `.args`, `.atoms`, `.free_symbols`, traversals** | §2.9 |
| **Immutability + hashability** | §2.10, §25.7 |
| **`evaluate=False` / `UnevaluatedExpr` / unevaluated symbolic classes** | §2.11 |
| **Old (core) assumptions: declaration via `Symbol(name, **assumptions)`, query via `is_*`** | §3.1 |
| **Three-valued fuzzy logic (`True` / `False` / `None`)** | §3.2 |
| **`Q` / `ask` / `assuming` / `refine` (new assumptions surface)** | §3.6, §3.7 |
| **Same-name symbol identity hazard** | §3.5 |
| **`.subs` (semantic) vs `.xreplace` (structural) vs `.replace` (pattern/predicate)** | §4.2 |
| **`.doit(**hints)` / `.evalf(prec)` / `N(expr, prec)`** | §4.3 |
| **`expand` / `expand_trig` / `expand_log` / `expand_func` / `expand_complex`** | §4.4 |
| **`collect` / `factor` / `cancel` / `together` / `apart` / `ratsimp`** | §4.5, §5.4 |
| **`.match(pattern)` / `Wild` / replacement rules** | §4.7 |
| **`srepr` / `preorder_traversal` / `postorder_traversal` / `bottom_up` / `count_ops`** | §4.8 |
| **`simplify(expr, measure=...)` heuristic** | §5.2 |
| **`trigsimp` / `powsimp` / `logcombine` / `radsimp` / `combsimp` / `hyperexpand`** | §5.4-§5.10 |
| **`.rewrite(target)` family** | §5.10, §11.5 |
| **`cse` (common subexpression elimination)** | §5.14, §20.3 |
| **`count_ops` cost / custom measure / weighted cost** | §5.12, §21.2 |
| **`Integer` / `Rational` / `Float` / `AlgebraicNumber`** | §6.1 |
| **`pi` / `E` / `I` / `oo` / `zoo` / `nan`** | §6.1 |
| **Float leakage and `nsimplify` recovery** | §6.2, §6.5 |
| **`evalf(prec)` / `.n(prec)` / `N(...)` / `chop` / `strict` / `maxn`** | §6.3 |
| **Precision vs accuracy** | §6.4 |
| **mpmath (arbitrary-precision floating-point)** | §6.6, §24.3 |
| **gmpy2 (integer + polynomial performance)** | §6.7 |
| **`float()` / `complex()` / `nfloat` boundaries** | §6.8 |
| **`diff` / `Derivative` / `idiff`** | §7.1 |
| **`integrate` / `Integral` / `conds` / integration transforms** | §7.2 |
| **`limit` / `Limit` / Gruntz algorithm** | §7.3 |
| **`series` / `Order` / `O` / leading term** | §7.4 |
| **`Derivative.as_finite_difference` / `differentiate_finite` / `finite_diff_weights`** | §7.5 |
| **`residue` / `singularities` / `continuous_domain`** | §7.6 |
| **`solve` (broad) vs `solveset` (set-typed)** | §8.2-§8.4 |
| **`linsolve` / `nonlinsolve` / `nsolve`** | §8.5, §8.7-§8.8 |
| **`dsolve` (ODE) / `pdsolve` (PDE) / `reduce_inequalities`** | §8.9-§8.11 |
| **`diophantine` / polynomial roots / `RootOf`** | §8.12-§8.13 |
| **`Expr` vs `Poly`** | §9.1, §21.7 |
| **Polynomial domains (`ZZ` / `QQ` / `RR` / `CC` / `FF_p` / algebraic extensions)** | §9.2 |
| **`factor_list` / `gcd` / `resultant` / `discriminant`** | §9.5 |
| **`groebner([polys], *gens, order=...)`** | §9.6 |
| **`Poly.all_roots()` / `RootOf` / algebraic-root isolation** | §9.8 |
| **Algebraic numbers + number fields** | §9.9 |
| **`DomainMatrix`** | §9.10, §10.7 |
| **AGCA (ideals / modules / quotient rings)** | §9.11 |
| **`Matrix` (mutable) / `ImmutableMatrix` / `SparseMatrix`** | §10.1 |
| **`MatrixSymbol` / `MatrixExpr` (abstract symbolic matrix algebra)** | §10.7 |
| **N-dim arrays / array expressions** | §10.8-§10.9 |
| **`IndexedBase` / Einstein notation** | §10.10 |
| **Abstract tensors + canonicalization** | §10.11 |
| **`sympy.vector` (coordinate systems + vector calculus)** | §10.12 |
| **Elementary functions** | §11.1 |
| **Special functions (gamma / bessel / hypergeometric / etc.)** | §11.2 |
| **Undefined symbolic functions (`Function('f')`)** | §11.3 |
| **Custom `Function` subclass (`eval` / `fdiff` / `_eval_*` / printers)** | §11.6, §25.4 |
| **`_imp_` / `implemented_function` (numeric backing of a Function)** | §11.7, §19.7 |
| **Symbolic booleans (`And` / `Or` / `Not` / `Implies` / `Xor` / `Equivalent` / `ITE`)** | §12.1 |
| **Relational objects (`Eq` / `Ne` / `Lt` / `Le` / `Gt` / `Ge`)** | §12.2 |
| **Fuzzy booleans vs symbolic booleans** | §12.3 |
| **Sets (`Interval` / `FiniteSet` / `Union` / `Intersection` / `Complement` / `ConditionSet` / `ImageSet` / `Range`)** | §12.4 |
| **Set-logic conversion** | §12.5 |
| **`simplify_logic` / `to_cnf` / `to_dnf` / `satisfiable`** | §12.7 |
| **`reduce_inequalities`** | §12.8 |
| **`binomial` / `factorial` / `Catalan` / `bell` / `stirling` / `harmonic`** | §13.1 |
| **`isprime` / `factorint` / `divisors` / `totient` / `mobius`** | §13.7 |
| **Permutations / permutation groups** | §13.3-§13.4 |
| **`sympy.crypto`** | §13.11 |
| **Finite fields (`FF_p`) / algebraic domains** | §13.12 |
| **2D/3D geometry entities (`Point` / `Line` / `Segment` / `Polygon` / `Circle` / `Plane`)** | §14.1 |
| **`sympy.diffgeom` (manifolds / patches / tensors)** | §14.4 |
| **`sympy.holonomic` (D-finite functions)** | §14.5 |
| **Lie algebra / category theory modules** | §14.6-§14.7 |
| **`sympy.physics.vector` / `sympy.physics.mechanics`** | §15.1-§15.2 |
| **Kane's method / Lagrange's method** | §15.3-§15.4 |
| **`sympy.physics.control`** | §15.6 |
| **`sympy.physics.units` (`Quantity` / `UnitSystem`)** | §15.7 |
| **`sympy.physics.quantum`** | §15.10 |
| **`sympy.stats` (`P` / `E` / `density` / distributions)** | §16.1-§16.8 |
| **CDF / quantile / median / entropy** | §16.3 |
| **Independence + product spaces** | §16.9 |
| **`plot` / `plot_parametric` / `plot_implicit`** | §17.1-§17.4 |
| **`Plot` lifecycle / backends / `PlotGrid`** | §17.5-§17.7 |
| **`str` / `srepr` / `sstr` / `pprint` / `pretty`** | §18.1-§18.2 |
| **LaTeX / MathML / Dot / IPython rich rendering** | §18.3 |
| **Code printers (C / C++ / Fortran / Python / Julia / JS / Rust / Octave / Mathematica / Maple)** | §18.5, §20.4 |
| **`sympify` / `parse_expr` / `parse_latex` / `parse_mathematica` / `parse_maxima` / `parse_autolev`** | §18.6 |
| **Custom printer (subclassing `Printer` / `_print_*` methods)** | §18.4, §25.8 |
| **`pickle` / JSON / `srepr` serialization** | §18.8 |
| **`lambdify(args, expr, modules=...)`** | §19.3, §19.4 |
| **lambdify backends (`math` / `mpmath` / `numpy` / `scipy` / `numexpr` / `tensorflow` / `jax` / `cupy`)** | §19.4 |
| **`ufuncify` (compiled NumPy ufunc)** | §19.11, §20.7 |
| **`autowrap` (compiled callable from symbolic)** | §19.12, §20.6 |
| **`binary_function` (compiled binary wrapped as SymPy `Function`)** | §19.13, §20.8 |
| **`codegen((name, expr), language, prefix=...)`** | §20.5 |
| **Pre-codegen expression preparation** | §20.2 |
| **Generated-code testing** | §20.12, §23.9 |
| **Expression swell** | §21.1 |
| **Substrate choice (`Expr` / `Poly` / `Matrix` / `DomainMatrix`)** | §21.7 |
| **"Derive once, execute many" pipeline architecture** | §21.12 |
| **Best-practice catalog (§22.1-§22.15) + agent guardrail checklist (§22.17)** | §22 |
| **CI layout for SymPy-based projects** | §23.14 |
| **Reproducibility across SymPy versions** | §23.13 |
| **NumPy / SciPy / mpmath / pandas / xarray / JAX / CuPy / matplotlib interop** | §24.1-§24.8 |
| **C / Fortran / F2PY / Cython tooling** | §24.9 |
| **Custom `Function` subclass extension lifecycle** | §11.6, §25.4-§25.10 |
| **Custom `Basic` / `Expr` subclasses** | §25.6 |
| **Custom canonicalization + hash stability** | §25.7 |

---

## Related skills

* **`pyomo-scip-ipopt-ref`** — for runtime numerical optimization. SymPy is used here as a **derivation aid** that produces formulas later transcribed into Pyomo expressions; the two libraries are **not** the same expression substrate (see that skill's operating rules on the Pyomo-vs-SymPy boundary).
* **`smartref-code-intel-ref`** — for structural code search and refactoring inside this repo.
* **`fastapi-nicegui-ref`** — for the web layer.
* **`attrs-cattrs-ref`** — for declarative class definition + boundary serialization.
