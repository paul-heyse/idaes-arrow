---
name: datafusion-pyarrow-ref
description: "Reference navigator for the DataFusion Python + PyArrow analytics stack. Routes questions across two deep-dive documents at docs/library_ref/: datafusion.md (SessionContext, DataFrame, Expr, SQL API, built-in functions, IO for CSV/JSON/Avro/Parquet/Arrow, joins, aggregations, windows, UDF/UDAF/UDWF/UDTF, plan lifecycle, Substrait, unparsing, custom table providers, Arrow interop, schema engineering I-III, plan lifecycle I-III, scientific UDFs I-III, governed-pipeline pattern) and pyarrow.md (DataType/Field/Schema, Array/Scalar/ChunkedArray, RecordBatch/Table/Tensor, Buffer/MemoryPool/IO, NumPy/pandas/DataFrame-interchange/DLPack, compute kernels + expressions + grouped aggregations, Datasets/scanners/fragments, partitioning + predicate pushdown + dataset writing, filesystems incl. S3/GCS/Azure/HDFS, IPC + Feather, Parquet single-file + dataset + metadata + encryption, CSV/JSON/ORC, extension types + PyCapsule, Flight RPC, Acero + Substrait, install + package variants, v23→v24 delta, env vars, threading, sparse tensors, compression, native extensions, dataset internals, compute kernel encyclopedia, Flight SQL + Gandiva, advanced schema engineering). Use whenever code touches `import datafusion`, `from datafusion`, `import pyarrow`, `from pyarrow`, `pa.array`, `pa.table`, `pa.schema`, `pa.field`, `pc.*`, `ds.dataset`, `pq.read_table`, `pq.write_table`, `fs.*`, `ipc.new_*`, `feather.*`, `csv.read_csv`, `json.read_json`, `orc.*`, `Acero`, `Substrait`, `ctx.sql`, `ctx.from_arrow`, `ctx.read_*`, `ctx.register_*`, `df.write_*`, `udf(...)`, `udaf(...)`, `udwf(...)`, `udtf(...)`, `__arrow_c_stream__`, `__arrow_c_array__`, or any Arrow-substrate UDF/table-provider authoring. For the deltalake/Acero-cache surfaces see `Datafusion_Deltalake_*.md` siblings."
allowed-tools: Read, Grep, Glob, Bash
model-baseline: claude-5 (2026-08)
---

# DataFusion Python + PyArrow Reference Navigator

## Version anchors

All guidance assumes the deployment baseline shared by these two documents:

* **DataFusion Python 53.0.0** (PyPI release 2026-04-13), Python ≥ 3.10. Pinned in `pyproject.toml` as `datafusion>=53.0.0`. The Python package is Rust-backed Arrow-native query execution: SQL + DataFrame APIs over CSV/Parquet/JSON/Avro/Arrow sources, optimizer-backed planning, Python UDF/UDAF/UDWF/UDTF surfaces, PyArrow zero-copy exchange, Substrait plan serialization.
* **PyArrow** anchored to Apache Arrow v23.0.1 baseline (catalog and §0-§15 deep-dives) with an explicit **v23→v24 reconciliation** chapter at §17 covering new view types, decimal32/decimal64, fixed-shape tensor extensions, canonical extension types (JSON/UUID/Bool8/Opaque), and sparse tensor surfaces. Pinned in `pyproject.toml` as `pyarrow>=23.0.1`. Python ≥ 3.9, but DataFusion forces ≥ 3.10.
* Stack contract:
  `Python / Arrow-compatible producer → __arrow_c_stream__ / __arrow_c_array__ → SessionContext → DataFrame (LogicalPlan) → Optimized Logical Plan → Physical Plan → RecordBatch stream → PyArrow Table / pandas / write_* / Arrow C stream consumer`

If a doc snippet references a different version, treat it as version-sensitive and verify against the baseline above before adopting. PyArrow v24 deltas are concentrated in pyarrow §17; pre-v24 surfaces remain authoritative under §0-§15.

### Scope

This skill covers DataFusion Python (the in-memory query engine), and PyArrow as both DataFusion's interchange substrate **and** a standalone tabular-data toolkit (Datasets, Filesystems, Parquet, IPC, compute kernels, Flight, Acero, Substrait).

**Out of scope (covered by sibling docs):**

- `deltalake` Python + DataFusion-Delta integration: see `docs/library_ref/deltalake.md`, `deltalake_datafusion_integration.md`, `Datafusion_Deltalake_Constructors_Deepdive.md`, `Datafusion_Delta_Builder_Objects_Glossary_v2.md`, `datafusion_deltalake_advanced_rust_integration.md`, `deltalake_datafusionmixins.md`, and `datafusion_delta_cache_integration.md`. The DataFusion deep-dives here intentionally stop at the DataFrame/SessionContext/table-provider boundary; Delta integration is a downstream concern.
- DataFusion Rust UDFs and FFI: see `docs/library_ref/datafusion_rust_UDFs.md`, `Datafusion_logicplan_rust.md`, and `datafusion_ffi_boundary_contract_v1.md`. The Python UDF/UDAF/UDWF/UDTF surface is covered here; Rust-side custom kernels and the FFI boundary contract are not.
- `duckdb`, `ibis`, `formulas`, `hamilton` adjacencies — separate skills / docs.

---

## How the two reference documents are organized

| Doc | Path | Lines | Top-level structure | Authoritative scope |
|-----|------|-------|---------------------|---------------------|
| **datafusion** | `docs/library_ref/datafusion.md` | 45,650 | **Two-pass layout.** Pass 1: upfront feature-category catalog (lines 1-755) for §0-§28, then deep-dive expansions for §0, §2-§26 (§1 catalog-only; §27-§28 catalog-only in Pass 1). Pass 2: gap-analysis catalog (lines 31923-32475) reusing fresh section numbers §27-§36 for **schema engineering I-III, plan lifecycle I-III, scientific Python UDFs I-III, and an end-to-end governed-pipeline capstone**, with full deep-dive expansions starting at line 32498. Catalog headings use `## N)` H2; Pass 1 deep-dives use `# DataFusion Advanced — N)` H1; Pass 2 deep-dives use `# DataFusion Advanced — N)` H1. Pass-1 §27/§28 in the catalog (Testing / Migration framing) are **not** the same topics as Pass-2 §27/§28 (schema engineering); resolve by line range. | The full DataFusion Python stack: SessionContext lifecycle, DataFrame creation + transformations + terminal/streaming execution, Expr/col/lit/operator system, built-in function catalog, SQL API + register-before-query, catalogs + schemas + tables, IO (CSV/JSON/Avro/Arrow/Parquet) + object stores, joins + aggregations + windows + grouping sets, UDF/UDAF/UDWF/UDTF authoring, plan inspection + optimizer behavior, configuration + runtime tuning, write_* + write_parquet_with_options, Arrow C Data / C Stream interop (`from_arrow`, `__arrow_c_stream__`, `__arrow_c_array__`), Substrait + SQL unparsing, custom table providers, display + error diagnostics + performance + testing, and the second-pass deep-dives: schema engineering (fields/schemas/metadata/nested types/evolution + drift), plan lifecycle (creation/auditing/optimizer rule governance), scientific Python UDFs (PyArrow/NumPy/SciPy interop + UDAF/UDWF for statistics + packaging), and the governed-pipeline capstone (schema/source/UDF registries + query builder + plan lint + execution policy + artifact manifest) |
| **pyarrow** | `docs/library_ref/pyarrow.md` | 16,977 | **Single-pass.** Lines 1-63 are a short upfront catalog (sections 0-15). Sections §0-§15 are inline `## N)` H2 deep-dives with `### N.M` subsections — there is no separate catalog/deep-dive split. Additional H1 chapters extend the surface: §16 Install (line 5879), §17 v23→v24 delta (6634), §18 env vars (7447), §19 threading (8149), §22 sparse tensors (9017), §23 compression (9975), §24 native extensions (10964), §25 dataset internals (11865), §26 compute kernel encyclopedia (12868), §27 Flight SQL + Gandiva (14274), §31 advanced schema engineering (15709). **Section numbers 20, 21, 24 (some), 28, 29, 30 are intentionally absent** — the gaps are scaffolding placeholders, not missing content. Subsections close with anti-patterns + "minimal canonical pattern" blocks. | Full PyArrow surface as the **typed-columnar substrate**: DataType/Field/Schema (immutable, return-new APIs), Array/Scalar/ChunkedArray + null semantics, RecordBatch/Table/RecordBatchReader/TableGroupBy/Tensor, Buffer/MemoryPool/IO + memory mapping, NumPy + pandas + DataFrame interchange + DLPack interop, compute kernels + expressions + grouped aggregations + ScalarAggregateOptions/SortOptions/etc, Datasets + Scanner + Fragment + FileSystemDatasetFactory, partitioning + predicate pushdown + `ds.write_dataset` / `pq.write_to_dataset`, fs.{Local,S3,GCS,Azure,Hadoop}FileSystem + PyFileSystem + fsspec, Arrow IPC (stream + file format) + Feather, Parquet (read/write/metadata/row-groups/encryption/sidecars), CSV/JSON-lines/ORC readers + writers + options, extension types + PyCapsule (`__arrow_c_schema__`, `__arrow_c_array__`, `__arrow_c_stream__`) + canonical extension types, Flight RPC client/server, Acero declarations + Substrait round-trip. The extension chapters cover packaging (pyarrow-core vs pyarrow vs pyarrow-all), v23→v24 view types + decimal32/64 + fixed-shape-tensor + canonical-extension reconciliation, env-var bootstrap ordering, CPU/IO pool control, sparse tensors (COO/CSR/CSF/CSC), compression codecs + allocators, C/Cython native extensions, dataset internals + format-specific scan options, the compute kernel encyclopedia + options-object catalog, Flight SQL + Gandiva opt-in components, and advanced schema engineering (logical/physical/dataset/partition/IPC/Parquet contracts + evolution + diff + registry + cross-language handoff). |

**Reading strategy.** Find the right section in the indexes below, then read with `Read(offset=N, limit=M)`. DataFusion deep-dive sections run 800-2,200 lines; PyArrow deep-dives run 300-1,400 lines. The PyArrow file is roughly one-third the size of DataFusion's — load whole sections more freely. For cross-cutting concerns, use the unified concern matrix. For agent recipes, every DataFusion deep-dive ends with anti-pattern + production-template blocks (often labelled "minimal canonical pattern" or "production wrapper"); every PyArrow subsection chain ends with `N.K Anti-patterns to reject in generated code` + `N.K+1 Minimal canonical patterns`. Load the closing 100-200 lines of a section before drafting code.

---

## datafusion.md — section index

The file opens with a feature-category catalog (lines 1-755) for Pass 1, then a second catalog (lines 31923-32475) for Pass 2. Pass-1 deep-dives use `# DataFusion Advanced — N)` H1; Pass-2 deep-dives use the same H1 form but with completely different section topics (do not confuse Pass-1 §27 "Testing strategy" with Pass-2 §27 "Schema engineering I").

### Pass 1 — core surface

| § | Line | Title | Key subsections / agent value |
|---|------|-------|-------------------------------|
| **catalog** | 1-755 | Feature-category catalog (sections 0-28) | One-page route map for Pass 1. §1 and §27-§28 are catalog-only in Pass 1. |
| **0** | 758 | Scope, versioning, and DataFusion mental model | §0.1 version anchors + deployment baseline, §0.2 scope statement (what DataFusion Python is), §0.3 non-goals, §0.4 core abstraction stack (`SessionContext → DataFrame → Expr → LogicalPlan → ExecutionPlan → RecordBatch`), §0.5 canonical execution pipeline, §0.6 terminal vs non-terminal operations, §0.7 streaming-first result handling, §0.8 `SessionContext` invariant, §0.9 `DataFrame` immutability, §0.10 `Expr` tree (not Python scalar), §0.11 plan inspection (logical/optimized/physical), §0.12 SQL API vs DataFrame API, §0.13 canonical dual-API skeleton, §0.14 ecosystem positioning, §0.15 deployment advisory, §0.16 agent implementation rules, §0.17 minimal production skeleton, §0.18 compression for agents |
| 1 | catalog only (line 22) | Installation, packaging, runtime requirements, deployment profiles | `pip install datafusion`, `uv add datafusion`, `conda install -c conda-forge datafusion`; deployment modes (script/notebook/service/batch/library). No deep-dive; see Pass-1 §0.1 + §0.15 for the operational guidance and the smartref `pyproject.toml` for the pinned version. |
| **2** | 1478 | Core application model: `SessionContext` | §2.0 version anchor, §2.1 `SessionContext` invariant, default vs configured vs global context, session IDs, `ctx.sql/table/read_*/register_*`, "explicit context over global state" rule |
| **3** | 2516 | DataFrame creation pathways | §3.5 direct file reads (anonymous DataFrames), §3.6 file registration (named catalog tables), §3.7 Python/Arrow-native creation (`from_arrow`, `from_pandas`, `from_polars`, `from_pydict`, `from_pylist`, `register_record_batches`, `register_dataset`), §3.8 file-extension/partition-column/compression/schema matrix, §3.10 top-level `datafusion.read_*` avoidance rule, §3.11 best-practice schema policy, §3.12 agent-safe source-adapter pattern |
| **4** | 4032 | DataFrame execution model and terminal operations | Lazy planning vs terminal execution; `collect`, `collect_partitioned`, `collect_column`, `show`, `to_pandas`, `to_pydict`, iteration, async iteration, `execute_stream`, `execute_stream_partitioned`; full collection vs incremental Arrow stream; "use streaming for large results" rule |
| **5** | 5102 | DataFrame transformation API | §5.3 projection/selection (`select`, `select_columns`, `__getitem__`, `drop`), §5.4 aliases, §5.5 filtering (Expr vs SQL-string forms, multi-predicate AND), §5.6 sorting + limiting, §5.7 deduplication (`distinct`/`distinct_on`), §5.8 type operations (`cast`), §5.9 null handling (`fill_null`), §5.10 summary/statistics (`describe`/`count`/`schema`), §5.11 generated-code patterns, §5.12 deployment advisory, §5.13 anti-pattern catalog, §5.14 test patterns, §5.15 compression for agents |
| **6** | 6385 | Expression system: `Expr`, `col`, `lit`, operators, aliases | §6.3 column references (`col`, `df.col`), §6.4 literal values (`lit`/`literal`), §6.5 operator overloading (arithmetic/comparison/boolean/unary + Python precedence trap), §6.6 core expression methods (`alias`, `cast`, `between`), §6.7 string methods, §6.8 array/list methods, §6.9 math methods, §6.10 function API vs method API. **Critical**: parenthesize `&` / `|` because Python precedence differs from SQL. |
| **7** | 7424 | Built-in function catalog | `from datafusion import functions as f`; scalar / string / temporal / conditional / null / array / aggregate / approximate-aggregate / window function families; prefer built-ins before custom UDFs |
| **8** | 8728 | SQL API | `ctx.sql(query)` returns a DataFrame; register-before-query (`register_csv`/`register_parquet`); read-only `SQLOptions`; parameterized queries; dialect; SQL-vs-DataFrame dual-API recipe |
| **9** | 9799 | Catalogs, schemas, tables, and namespace organization | Default catalog `datafusion`; default schema `public`; `Catalog`/`Schema`/`Table` objects; `register_table`, `deregister_table`; multi-catalog patterns |
| **10** | 10671 | Data source registration and table ingestion | Full `register_*` surface; named-table lifecycle; provider-backed registration; deregistration discipline |
| **11** | 12030 | IO deep dive: Arrow, CSV, JSON, Avro, Parquet | §11.0 version anchor, §11.1 IO invariant (anonymous reads / registered sources / streaming exports / terminal writes), §11.2 Arrow import/export (`from_arrow`, `pa.table(df)`, `pa.RecordBatchReader.from_stream(df)`), then CSV/JSON/Avro/Parquet read + register + write paths; schema inference vs explicit schema; partition columns; compression options |
| **12** | 13430 | Object stores and remote data access | `datafusion.object_store`; AWS/S3, GCS, HDFS, Azure registration; URL scheme handling; credential lifecycle |
| **13** | 14632 | Joins and relational composition | `df.join(other, on=..., how=...)`; INNER/LEFT/RIGHT/FULL/SEMI/ANTI; multi-key joins; suffix handling; broadcast/hash/sort-merge optimizer hints (informational) |
| **14** | 16029 | Aggregation, grouping sets, rollups, and cubes | `df.aggregate([keys], [aggs])`; grouping sets/rollups/cubes; approximate aggregates; aggregation pushdown caveats |
| **15** | 17673 | Window functions | `Window(...)`, partition_by/order_by/frame, ranking + analytic + aggregate window patterns |
| **16** | 19165 | User-defined functions: UDF, UDAF, UDWF, UDTF | §16.0 four-family invariant (scalar/aggregate/window/table), §16.1 function-family map (constructors + Python unit + use site + return type), §16.2-§16.5 scalar UDF authoring (PyArrow-vectorized contract), §16.6+ UDAF authoring (`Accumulator` class), UDWF authoring (`WindowEvaluator`), UDTF authoring (table-provider factory). All Python UDFs receive `pyarrow.Array` and must return `pyarrow.Array`. |
| **17** | 20346 | Query plans, optimizer behavior, and explainability | `df.logical_plan()`, `df.optimized_logical_plan()`, `df.execution_plan()`, `df.explain(analyze=...)`; plan-tree node taxonomy; optimizer rules; plan hashing for snapshot tests |
| **18** | 21443 | Configuration and runtime tuning | `RuntimeEnvBuilder`, `SessionConfig` knobs (partitions, batch size, memory pool, repartition rules); `ctx.set_option(...)`; per-session configuration; thread/pool sizing |
| **19** | 22679 | Writing data and materialization | §19.0 terminal-execution invariant, §19.1 API surface map (`write_csv`/`write_json`/`write_parquet`/`write_parquet_with_options`/`write_table`); CSV/JSON/Parquet writer options; partitioned writes; sink-side schema contracts |
| **20** | 23924 | Arrow interoperability and zero-copy exchange | §20.0 interoperability invariant (Python ↔ Arrow C Data / C Stream / PyCapsule ↔ Rust), §20.1 DataFusion Arrow contract (`from_arrow` + `__arrow_c_stream__` on `DataFrame`), §20.2 import pathways (PyArrow Table/RecordBatch/RecordBatchReader/StructArray), `pa.table(df)` (full materialization) vs `pa.RecordBatchReader.from_stream(df)` (streaming) |
| **21** | 24988 | Substrait interoperability | `from datafusion import substrait`; serialize `LogicalPlan` to Substrait, deserialize Substrait into `LogicalPlan`; engine-portable plans |
| **22** | 26113 | SQL unparsing and dialect conversion | `from datafusion import unparser`; convert `LogicalPlan` back to SQL; dialect targets; round-trip caveats |
| **23** | 27426 | Custom table providers and Python/Rust extension points | `TableProvider` Python interface; schema declaration; partition iteration; pushdown opt-in; Rust extension boundary |
| **24** | 28641 | DataFrame display, notebook UX, and rendering | `df.show()` vs IPython HTML repr; row truncation; type rendering; deterministic display in CI/tests |
| **25** | 29596 | Error handling, diagnostics, and debugging workflows | Common error categories (schema mismatch, missing UDF, parse error, planner error, execution error); `df.explain()` for diagnostic introspection; logging configuration |
| **26** | 30856 | Performance engineering and best practices | Plan-and-metrics-driven tuning rule, partition + batch-size sizing, Parquet projection + filter pushdown, repartition control, memory pool selection, "tune after plan + metrics evidence, not by guessing" closer |
| 27 | catalog only (line 669) | Pass-1 testing/QA strategy framing | Pyomo-style coverage outline only — superseded operationally by Pass-2 §37-ish patterns in the governed-pipeline capstone (§36). |
| 28 | catalog only (line 703) | Pass-1 migration framing (DataFusion vs Pandas/Polars/DuckDB/Spark) | Comparative framing only; no deep-dive. Use for high-level positioning. |

### Pass 2 — schema, plan, and scientific UDF engineering

Pass 2 reuses section numbers 27-36 with completely different topics. Catalog at lines 31923-32475; deep-dives start at 32498.

| § | Line | Title | Key subsections / agent value |
|---|------|-------|-------------------------------|
| **catalog-2** | 31923-32475 | Gap analysis + Pass-2 catalog (§27-§36) | One-page route map for the schema-engineering / plan-lifecycle / scientific-UDF / governed-pipeline deep-dives. |
| **27** | 32498 | Schema engineering I: Arrow schema contracts in DataFusion | §27.0 core invariant (`df.schema()` returns `pa.Schema`; schema is the canonical contract across IO/imports/DataFrame/SQL/catalog/providers/UDFs/Parquet/plans/tests/interop), §27.1 `pa.field(...)` + copy/mutation methods + `pa.schema(...)`, schema-level metadata, immutable-replacement discipline, schema fingerprints/hashes, schema registry pattern |
| **28** | 34023 | Schema engineering II: advanced nested types and nested-data operations | §28.0 nested-data invariant, `pa.struct/list_/large_list/fixed_size_list/map_/dictionary/decimal128/decimal256/timestamp(tz=)/duration` deep-dives, struct field access (`expr["field"]`), array element access, `unnest_columns`, nested Parquet schema behavior |
| **29** | 35332 | Schema engineering III: schema evolution, compatibility, and drift management | Schema diff algorithms, nullable compatibility, safe widening vs unsafe narrowing, metadata-preserving evolution, Parquet multi-writer reconciliation, CSV/JSON inference→explicit migration, schema versioning + hashing, CI schema tests |
| **30** | 36591 | Plan lifecycle I: plan creation pathways and execution contracts | §30.0 invariant (SQL/DataFrame/Substrait/protobuf → LogicalPlan → optimized → physical → execution), terminal vs non-terminal plan operations, plan inspection APIs (`logical_plan`, `optimized_logical_plan`, `execution_plan`, `explain`) |
| **31** | 37706 | Plan lifecycle II: plan auditing, linting, and governance | Plan-tree walking + node taxonomy, plan lints (preview-without-LIMIT, unbounded materialization, Python UDF in hot path, missing partition filter), plan-hash snapshot tests, governance-grade plan artifact |
| **32** | 39305 | Plan lifecycle III: optimizer behavior, rule governance, and extension limits | Optimizer rule families, rule on/off configuration, optimizer determinism, semantic equivalence tests across optimizer versions, extension boundaries (no plugin authoring through Python) |
| **33** | 40479 | Scientific Python UDFs I: PyArrow, NumPy, SciPy interop patterns | §33.0 batch-oriented Arrow function contract (`pa.Array` in → `pa.Array` out, length-preserving), §33.1 interop decision matrix (built-in vs PyArrow compute vs SciPy special vs SciPy stats vs SciPy signal vs UDAF vs UDWF), §33.2 Arrow→NumPy zero-copy vs copy-allowed, §33.3+ NumPy→Arrow, SciPy escape-hatch patterns, defensive null-handling, validate-scientific-runtime gate |
| **34** | 41558 | Scientific Python UDFs II: UDAF and UDWF design for statistics, signal processing, time series | `Accumulator` lifecycle (init → update → merge → evaluate → state), grouped statistics, signal-processing UDAF patterns, window evaluator for rolling statistics, partition-aware time-series UDWF |
| **35** | 42843 | Scientific Python UDFs III: packaging, performance, and reproducibility | Module-import gating, runtime dependency probes (scipy/scikit-learn/numpy version pinning), UDF registration policy (registry + lint), volatility annotations (`immutable`/`stable`/`volatile`), per-batch overhead measurement, reproducibility manifest |
| **36** | 44093 | Schema + plan + function integration: end-to-end governed pipeline pattern | §36.0 three-contract architecture (schema / source / UDF registries + query builder + plan lint + execution policy + artifact manifest), §36.16 CI test matrix (schema/source/UDF/semantic-query/plan-lint tests), §36.17 failure modes table + control points, §36.18 anti-pattern catalog ("prompt → SQL → Pandas", "inline schema/source/function definitions", "unregistered scientific dependencies", "execution before lint", "unbounded materialization") |

---

## pyarrow.md — section index

The file opens with a compact catalog (lines 1-63) for sections 0-15; deep-dives follow inline as `## N)` H2 plus `### N.M` subsections. Additional H1 chapters extend into §16-§31. Section numbers 20, 21, and 28-30 are absent — they are intentional scaffolding gaps, not missing content.

| § | Line | Title | Key subsections / agent value |
|---|------|-------|-------------------------------|
| **catalog** | 1-63 | Compact catalog (sections 0-15) | One-paragraph map of the core PyArrow surface. |
| **0** | 65 | Scope, versioning, and the Arrow mental model | §0.1 version anchor + house style ("factory function first, class methods second, operational patterns third"), §0.2 typed-columnar-buffers mental model, §0.3 object graph (`DataType`/`Field`/`Schema` → `Array`/`ChunkedArray`/`RecordBatch`/`Table`/`Tensor`/`Dataset`), §0.4 immutability/return-new model, §0.5 zero-copy boundary taxonomy, §0.6 canonical factory surface (`pa.array`/`pa.field`/`pa.schema`/`pa.record_batch`/`pa.table`/`pa.Tensor.from_numpy`), §0.7 schema-first construction pipeline, §0.8 protocol-first interop boundary, §0.9 deployment guidance, §0.10 anti-patterns to reject, §0.11 minimal agent decision procedure |
| **1** | 317 | Data types, fields, schemas, and schema metadata | §1.2 `DataType` semantic contract (primitive/temporal/binary/decimal/nested/encoded families), §1.3 type-family deployment guidance, §1.4 `Field` (`name`+`type`+`nullable`+optional metadata), §1.5 nested type contracts (fields are part of the type), §1.6 `Schema` ordered collection + schema-level metadata, §1.7 operational schema methods (`append`/`insert`/`set`/`remove`/`with_metadata`/`remove_metadata`/`equals(check_metadata=True)`/`serialize`/`to_string`), §1.8 duplicate field-name hazard, §1.9 bytes-map metadata semantics, §1.10 reserved metadata channels (pandas/PII/units/lineage), §1.11 schema enforcement at construction boundaries, §1.12 `unify_schemas` reconciliation, §1.13 dataset partition schemas, §1.14 zero-copy protocol interop, §1.15 file-format schema persistence, §1.16 agent defaults, §1.17 schema-first canonical pattern |
| **2** | 690 | Arrays, scalars, chunked arrays, and null semantics | §2.1 `pa.array(...)` primary ingress, §2.2 `pa.scalar(...)`, §2.3 `pa.chunked_array(...)`, §2.4 null = validity-bitmap, not sentinel, §2.5 array operational surface (slice/cast/take/filter/to_numpy/buffers), §2.6 conversion behavior (NumPy/pandas/Python), §2.7 ChunkedArray operations, §2.8 how chunking changes downstream behavior, §2.9 ChunkedArray conversion semantics, §2.10 anti-patterns, §2.11 agent rules, §2.12 minimal canonical patterns |
| **3** | 916 | RecordBatch, Table, RecordBatchReader, TableGroupBy, Tensor | §3.1 construction surface (`pa.record_batch`, `pa.table`, `RecordBatchReader.from_*`), §3.2 shape/batchness semantics, §3.3 projection + schema-preserving transforms, §3.4 row subsetting (`slice`/`filter`/`take`), §3.5 sorting (`sort_by`), §3.6 `Table.join(...)`, §3.7 `Table.join_asof(...)`, §3.8 grouping/aggregation (`table.group_by(...).aggregate(...)`), §3.9 batching + streaming (`to_batches`/`to_reader`/`RecordBatchReader.from_*`), §3.10 `Tensor` conversion + dense-matrix semantics, §3.11 RecordBatch vs Table vs Tensor decision, §3.12 anti-patterns, §3.13 minimal canonical pattern |
| **4** | 1334 | Buffers, memory pools, streams, files, memory mapping | §4.1 `pa.Buffer`, §4.2 borrowed-view vs owned-allocation creation, §4.3 `MemoryPool` (allocator + alignment + accounting), §4.4 allocation control, §4.5 `NativeFile`, §4.6 `input_stream/output_stream` generic factory, §4.7 `PythonFile` correctness bridge, §4.8 `BufferReader`, §4.9 `BufferOutputStream`, §4.10 `memory_map(...)`/`create_memory_map(...)`, §4.11 `OSFile` vs `MemoryMappedFile`, §4.12-§4.13 resident-memory behavior + decision rules, §4.14 stream-segment APIs (`get_stream`), §4.15 anti-patterns, §4.16 minimal patterns (zero-copy wrap / owned pool-controlled / readable buffer stream / growable sink / generic factories / mmap read / mmap write) |
| **5** | 1659 | Python, NumPy, pandas, DataFrame interchange, DLPack | §5.1 canonical boundary choices, §5.2 NumPy ingress (`pa.array(np_array)`, `from_numpy_dtype`), §5.3 NumPy egress (view-only narrow cases), §5.4 `__arrow_array__` Python duck-array hook, §5.5-§5.6 `Table.from_pandas(...)` (schema/index/columns/safety), §5.7 `table.to_pandas(...)`, §5.8 pandas-nullable-integer footgun, §5.9 `to_pandas` memory + copy controls, §5.10 nested/table fidelity limits vs pandas, §5.11 `table.__dataframe__(...)` interchange, §5.12 `pyarrow.interchange.from_dataframe(...)`, §5.13 DLPack producer-side, §5.14 tensor vs DLPack separation, §5.15 conversion-protocols stack, §5.16 pandas extension interop (`to_pandas_dtype()` + `__from_arrow__`), §5.17 anti-patterns, §5.18 minimal patterns |
| **6** | 1949 | Compute functions, expressions, and grouped aggregations | §6.1 direct kernel surface (same-shape semantics on arrays + scalars), §6.2 `pc.field(...)` + `pc.scalar(...)` + `Expression` deferred logic, §6.3 selection kernels (`pc.take`/`pc.filter`/`pc.array_take`/`pc.array_filter`), §6.4 sort kernels + `SortOptions`, §6.5 cast + checked kernels + options objects, §6.6 scalar aggregations + `ScalarAggregateOptions`, §6.7 grouped aggregations (`table.group_by(...).aggregate(...)` + `hash_*` kernel mapping), expression-first filtering / direct gather / index-based sort / scalar + grouped aggregations / dynamic-dispatch policy |
| **7** | 2273 | Datasets, scanners, fragments, query planning | §7.1 `ds.dataset(...)` unified entry (paths / file lists / in-memory batches / readers / iterables), §7.2 discovery knobs (partitioning / invalid-file checks / ignored prefixes), §7.3 partitioned-dataset vs naïve-glob performance, §7.4 expression layer at dataset boundary (`ds.field`/`ds.scalar`/`Expression`), §7.5 `Dataset` logical relation (deferred filters), §7.6 `dataset.scanner(...)` plan first, §7.7 projection dictionaries as query-planning features, §7.8 scanner consumption modes (`to_batches`/`scan_batches`/`take`/`to_reader`/`to_table`), §7.9 fragment-level reasoning, §7.10 Parquet row-group granularity, §7.11 `FileSystemDatasetFactory(...)` discovery + inspect + finish, §7.12 `FileSystemFactoryOptions` discovery-cost trade-offs, §7.13 streaming vs full materialization, §7.14 anti-patterns, §7.15 minimal pattern |
| **8** | 2637 | Partitioning, predicate pushdown, writing partitioned datasets | §8.1 `ds.partitioning(...)` one API + three schemes, §8.2 directory partitioning (positional), §8.3 hive partitioning (key=value), §8.4 filename partitioning, §8.5 dictionary-typed partition fields, §8.6 partition-schema design rules, §8.7 `ds.get_partition_keys(...)`, §8.8 predicate pushdown (guaranteed vs opportunistic), §8.9 `ds.write_dataset(...)`, §8.10 `partitioning=` vs `partitioning_flavor=` on write, §8.11 `basename_template` + `existing_data_behavior`, §8.12 throughput + layout controls (threads, row order, file counts, row groups), §8.13 `file_visitor` Parquet metadata collection, §8.14 `pq.write_to_dataset(...)` convenience wrapper, §8.15 repartitioning + layout rewrites, §8.16 anti-patterns, §8.17 minimal patterns (hive partition for lake / general writer / append-safe / partition overwrite / partition-key extraction) |
| **9** | 3045 | Filesystem abstraction and cloud/object-store access | §9.1 `FileSystem` interface, §9.2 `from_uri(...)` URI inference, §9.3 random/sequential/append stream semantics, §9.4 `LocalFileSystem(...)` + optional mmap reads, §9.5 `S3FileSystem(...)` region + credential policy, §9.6 `GcsFileSystem(...)` ADC + anonymous mode, §9.7 `HadoopFileSystem(...)` JNI/libhdfs reqs, §9.8 `AzureFileSystem(...)` Blob + ADLS Gen2, §9.9 `copy_files(...)`, §9.10 `PyFileSystem` + `FileSystemHandler`, §9.11 fsspec interop + `FSSpecHandler` + `fsspec+` URIs, §9.12 deployment rules + anti-patterns, §9.13 minimal patterns |
| **10** | 3367 | Arrow IPC, streaming serialization, Feather | §10.1 stream format (`ipc.new_stream`/`ipc.open_stream`), §10.2 stream-reader capabilities, §10.3 stream-writer capabilities + per-batch metadata, §10.4 file format (`ipc.new_file`/`ipc.open_file`), §10.5 file-reader random access + footer metadata, §10.6 schema-carrying persistence common API, §10.7 `IpcWriteOptions`/`IpcReadOptions` (compatibility, compression, alignment, projection), §10.8 mmap + resident memory behavior, §10.9 in-memory IPC via `BufferOutputStream`, §10.10 Feather mental model = Arrow IPC-on-disk, §10.11 `feather.read_table`/`read_feather`, §10.12 `feather.write_feather`, §10.13 stream-vs-file-vs-Feather decision, §10.14 anti-patterns, §10.15 minimal patterns |
| **11** | 3675 | Parquet: single-file IO, metadata, datasets, writer options, caveats | §11.1 `pq.read_table(...)` unified eager reader, §11.2 read-side projection + dictionary reads + extension types + memory knobs, §11.3 read-side filtering + partition pruning, §11.4 `pq.ParquetFile(...)` single-file reader + row-group control, §11.5 row groups as physical scan unit, §11.6 `pq.read_metadata(...)` footer-only inspection + metadata graph, §11.7 metadata sidecars, §11.8 `pq.write_table(...)` rich physical controls, §11.9 `ParquetWriter(...)` incremental + deliberate multi-row-group files, §11.10 `pq.write_to_dataset(...)`, §11.11 modular encryption + KMS + nested-field targeting, §11.12 anti-patterns, §11.13 minimal patterns |
| **12** | 4061 | CSV, line-delimited JSON, ORC | §12.1 CSV format positioning, §12.2 `csv.read_csv(...)` eager read, §12.3 `ReadOptions` (threading, chunking, header, encoding), §12.4 `ParseOptions` (syntax, row-error policy), §12.5 `ConvertOptions` (typing, null rules, boolean rules, projection-at-read), §12.6 `csv.open_csv(...)` + `CSVStreamingReader` + `CSVWriter`, §12.7 line-delimited-JSON constraints, §12.8 `json.read_json(...)`, §12.9 `json.ReadOptions/ParseOptions`, §12.10 `json.open_json(...)`, §12.11 ORC positioning, §12.12 `orc.read_table(...)`, §12.13 `ORCFile(...)` stripe reader, §12.14 `orc.write_table(...)`, §12.15 `ORCWriter(...)`, §12.16 format-choice matrix, §12.17 anti-patterns, §12.18 minimal patterns |
| **13** | 4438 | Extension types and customization protocols | §13.1 type-class + registry surface, §13.2 `class MyType(pa.ExtensionType)` required/optional pieces, §13.3 registration + IPC round-trip discipline, §13.4 `wrap_array(...)` + `ExtensionArray.from_storage(...)`, §13.5 parameterized vs non-parameterized, §13.6 custom array class via `__arrow_ext_class__`, §13.7 custom scalar via `pa.ExtensionScalar`/`__arrow_ext_scalar_class__`, §13.8 canonical extension types (JSON/UUID/Bool8/Opaque/FixedShapeTensor), §13.9 register/unregister lifecycle, §13.10 `UnknownExtensionType` placeholder, §13.11 `__arrow_array__(type=None)` hook, §13.12 PyCapsule interface (`__arrow_c_schema__`/`__arrow_c_array__`/`__arrow_c_stream__`), §13.13 pandas conversion contract (`to_pandas_dtype()` + `__from_arrow__`), §13.14 customization-hook decision, §13.15 anti-patterns, §13.16 minimal patterns |
| **14** | 4855 | Arrow Flight and remote data services | §14.0 stability warning (Flight is documented as unstable), §14.1 `flight.connect(...)`/`FlightClient(...)`/`Location`, §14.2 descriptors + tickets + endpoints + `FlightInfo`, §14.3 `FlightServerBase` subclassing, §14.4 discovery plane (`get_flight_info`/`get_schema`/`list_flights`), §14.5 download plane (`do_get`/`FlightStreamReader`/`GeneratorStream`/`RecordBatchStream`), §14.6 upload plane (`do_put`/`FlightStreamWriter`/metadata acks), §14.7 bidirectional plane (`do_exchange`), §14.8 handshake auth + bearer-token helper, §14.9 middleware + per-RPC concerns, §14.10 deployment caveats, §14.11 minimal pattern |
| **15** | 5223 | Acero and Substrait | §15.0 status + mental model (Acero is experimental), §15.1 documented Acero node surface, §15.2 `acero.Declaration(...)` building block, §15.3 source nodes (`table_source`/`scan`), §15.4 transform nodes (`filter`/`project`), §15.5 `AggregateNodeOptions`, §15.6 `OrderByNodeOptions`, §15.7 `HashJoinNodeOptions`, §15.8 blessed Acero plan patterns (linear plan / dataset scan w/ pushdown / hash join), §15.9 Substrait Python surface (compact + interop-oriented), §15.10 `substrait.serialize_expressions(...)` round-trip, §15.11 `substrait.serialize_schema/deserialize_schema`, §15.12 `substrait.get_supported_functions()` compatibility gate, §15.13 `substrait.run_query(...)`, §15.14 Acero-vs-Substrait decision (build directly vs interchange), §15.15 anti-patterns, §15.16 minimal patterns |
| **16** | 5879 | Installation, package variants, runtime compatibility | §16.1 package manager = capability boundary, §16.2 canonical install commands (PyPI pip / conda-forge default / minimal-core / maximal), §16.3 capability matrix, §16.4 native components (`libparquet`/`libarrow-dataset`/`libarrow-acero`/`libarrow-substrait`/`libarrow-flight`/`libarrow-flight-sql`/`libarrow-gandiva`), §16.5 runtime feature probes for agents, §16.6 build/linkage probes, §16.7 optional Python deps, §16.8 timezone + Windows constraints, §16.9 pip-vs-conda-forge trade-offs, §16.10 source-build implications, §16.11 custom conda recipes, §16.12 agent feature-gating (hard fail / soft fallback / capability manifest), §16.13 deployment templates (small / lake / Flight / full), §16.14 anti-patterns, §16.15 minimal deployment patterns |
| **17** | 6634 | Versioning and PyArrow v23 → v24 API delta | §17.1 version probe, §17.2 agent feature-gating policy, §17.3 v24 surface map, §17.4 view types (`binary_view`/`string_view`/`list_view`/`large_list_view`), §17.5 decimal32 / decimal64 family, §17.6 fixed-shape-tensor extension type/array/scalar, §17.7 canonical extension types (JSON, UUID, Bool8, Opaque, FixedShapeTensor), §17.8 sparse tensor surfaces, §17.9 API index reconciliation, §17.10 schema compatibility + downgrade policy, §17.11 version-aware test matrix, §17.12 migration edits, §17.13 anti-patterns, §17.14 minimal v24 reconciliation harness |
| **18** | 7447 | Environment variables, runtime configuration, deployment defaults | §18.1 configuration authority model, §18.2 PyArrow-specific env vars, §18.3 Arrow C++ env vars inherited by PyArrow, §18.4 bootstrap ordering (set env **before** import), §18.5 thread management (env defaults vs Python overrides), §18.6 memory-pool configuration, §18.7+ deployment policies. Bootstrap rule: any pool/SIMD/timezone/S3-diagnostic env must be set before `import pyarrow`. |
| **19** | 8149 | Threading, CPU pools, IO pools, performance controls | §19.1 threading control map, §19.2 CPU pool API (observe / override / deployment cases), §19.3 IO pool API (observe / override / profiles), §19.4 `use_threads=` per-operation switch, §19.5 dataset scanner controls (`batch_size`/`batch_readahead`/`fragment_readahead`/`to_batches`-vs-`to_reader`-vs-`to_table`), §19.16 tuning checklist, §19.17 anti-patterns, §19.18 minimal bootstrap |
| **22** | 9017 | Sparse tensors and dense/sparse numeric containers | §22.1 numeric container taxonomy, §22.2 table vs dense tensor vs fixed-shape tensor array vs sparse tensor decision, §22.3 dense `pa.Tensor`, COO/CSR/CSF/CSC sparse construction + conversions, value cases + deployment advisory |
| **23** | 9975 | Compression, codecs, allocator strategy | Compression codec catalog (snappy/gzip/zstd/lz4/brotli), codec selection rules, allocator strategy (jemalloc/mimalloc/system), I/O compression vs in-memory compression, decompression streaming |
| **24** | 10964 | Native extensions and cross-language integration | C/Cython integration with PyArrow, `pyarrow.cffi`, `pyarrow.include` build flags, exposing custom Arrow code via PyCapsule, C++ extension consumption from Python, language-boundary lifecycle |
| **25** | 11865 | Dataset internals: file formats, fragment scan options, format-specific planning | `FileFormat` taxonomy (Parquet/IPC/CSV/JSON/ORC), `FragmentScanOptions` per-format (Parquet: read_dictionary, pre_buffer, thrift limits, decryption properties; CSV/JSON: convert options, parse options), `Dataset` open hooks, format-specific predicate pushdown |
| **26** | 12868 | Compute kernel catalog and options encyclopedia | Kernel families (arithmetic / comparison / logical / cast / temporal / string / aggregate / hash / set / structural), per-family options-object catalog, §26.20 user-defined compute registration (scalar / vector / aggregate / non-scalar), §26.21 grouped aggregation grammar, §26.22 options encyclopedia, §26.23 memory-pool + threading interaction, §26.24 generated-code dispatch policy, §26.25 capability manifest, §26.26 anti-patterns, §26.27 minimal pattern + 5 example recipes (row-local transform / predicate / filter+project / aggregation w/ null policy / dynamic-dispatch allowlist) |
| **27** | 14274 | Optional advanced services: Flight SQL and Gandiva | §27.1 optional-component decision matrix, §27.2 install selection (full optional / Flight RPC add-on / Flight SQL add-on / Gandiva add-on / package-manager warning), §27.3 runtime capability probes, §27.4 Flight RPC vs Flight SQL boundary, §27.5 Flight RPC baseline required first, §27.6 Flight SQL protocol commands + client-generation rule + raw descriptors, §27.7 SQL info strategy + generated-code policy, §27.8 Flight SQL deployment controls, §27.9-§27.13 Gandiva boundary + C++ mental model + value case + Python gating + fallback strategy, §27.14 capability manifest, §27.15 service-profile templates (Flight RPC service / Flight SQL client+runtime / Gandiva expression compiler) |
| **31** | 15709 | Advanced schema engineering and evolution | §31.0 schema-as-API-contract layers (logical / physical / dataset / partition / IPC / Parquet), §31.1 complex nested-schema design, §31.2 field-path grammar across Schema/Dataset/Parquet/Compute/Encryption, §31.3 recursive schema traversal + rewrite utilities, §31.4 schema conformance (missing/extra/ordering/casts/defaults), §31.5 nullability validation + tightening/loosening policy, §31.6 schema evolution compatibility matrix, §31.7 schema diff + compatibility reports, §31.8 dataset `inspect_schemas` + `factory.finish(schema=...)`, §31.9 fragment physical schema vs dataset logical schema, §31.10 metadata governance + registry + serialization, §31.11 extension-type schema contracts + canonical extension types, §31.12 Parquet physical/logical schema round-trip + sidecars, §31.13 CSV/JSON schema-aware ingestion, §31.14 cross-language schema protocol + C Data / PyCapsule handoff, §31.15 schema QA / golden-test harness, §31.16 anti-patterns, §31.17 minimal canonical pattern |

§20, §21, §28-§30 are absent (intentional scaffolding gaps).

---

## Cross-document overlap matrix

This is the routing table when a topic appears in both documents. **Authoritative source** is the doc that owns the topic; **secondary** documents may have summaries or cross-cuts. Prefer the authoritative source unless your question is specifically about the other doc's perspective.

Legend: ✅ authoritative, 🔁 cross-cut/summary, — not covered.

### Schema and type contracts

| Topic | datafusion | pyarrow | Authoritative |
|-------|-----------|---------|---------------|
| `pa.field(...)` syntax, attributes, `with_*` copy methods | §27.1 ✅ | §1.4 ✅ | **pyarrow §1.4** for general; **datafusion §27.1** for the DataFusion-contract framing |
| `pa.schema(...)` construction + immutability | §27.1.3 ✅ | §1.6, §1.7 ✅ | **pyarrow §1.6-§1.7** is canonical |
| Nested types: struct / list / map / dictionary / decimal / timestamp(tz=) / duration | §28 ✅ | §1.5 (nested type contracts), §31.1 (nested-design patterns) ✅ | **pyarrow §1.5** for type contracts; **datafusion §28** for nested expression access (`expr["field"]`, `unnest_columns`) |
| Schema metadata (bytes-map, pandas, PII, units, lineage) | §27 ✅ | §1.9, §1.10 ✅ | **pyarrow §1.9-§1.10** for semantics; **datafusion §27** for governance/registry use |
| Schema equality (`equals(check_metadata=True)`) | §27.1 🔁 | §1.7 ✅ | **pyarrow §1.7** |
| `unify_schemas` reconciliation | — | §1.12 ✅ | **pyarrow §1.12** |
| Duplicate field names hazard | — | §1.8 ✅ | **pyarrow §1.8** |
| Schema fingerprints / hashing | §27, §29 ✅ | §31.7, §31.15 ✅ | **datafusion §29** for fingerprint-as-governance; **pyarrow §31.7/§31.15** for diff + golden-test harness |
| Schema evolution + compatibility + drift | §29 ✅ | §31.6, §31.7 ✅ | **datafusion §29** for DataFusion-pipeline policy; **pyarrow §31.6-§31.7** for compatibility matrix + diff |
| Cross-language / C Data / PyCapsule handoff | §20.0-§20.1 ✅ | §13.12, §31.14 ✅ | **datafusion §20** for DataFusion's import/export; **pyarrow §13.12** for the PyCapsule contract; **pyarrow §31.14** for cross-language schema protocol |

### Arrays, scalars, and container model

| Topic | datafusion | pyarrow | Authoritative |
|-------|-----------|---------|---------------|
| `pa.array(...)` factory + ingress patterns | §33.2-§33.3 🔁 | §2.1 ✅ | **pyarrow §2.1** |
| `pa.scalar(...)` semantics | — | §2.2 ✅ | **pyarrow §2.2** |
| `pa.chunked_array(...)` + table-column chunking | — | §2.3, §2.7, §2.8 ✅ | **pyarrow §2.3 + §2.7-§2.8** |
| Null semantics (validity bitmap, not sentinel) | §33.2-§33.3 🔁 | §2.4 ✅ | **pyarrow §2.4** |
| `Array.to_numpy(zero_copy_only=..., writable=...)` | §33.2 ✅ | §2.6 ✅ | **datafusion §33.2** for UDF-context zero-copy decisions; **pyarrow §2.6** for the general semantics |
| `RecordBatch`/`Table`/`RecordBatchReader` construction | §11.2 🔁 (Arrow IO context) | §3.1, §3.9 ✅ | **pyarrow §3** |
| `Tensor` and `RecordBatch.to_tensor()` | §33.4 🔁 (scientific UDF context) | §3.10, §22 ✅ | **pyarrow §3.10 + §22** |
| `Table.join(...)` / `Table.join_asof(...)` | §13 (DataFrame joins) | §3.6, §3.7 ✅ | **datafusion §13** for DataFrame joins (use these); **pyarrow §3.6-§3.7** for Table-only joins outside DataFusion |
| `Table.group_by(...).aggregate(...)` | §14 (DataFrame aggregation) | §3.8 ✅ | **datafusion §14** for production paths; **pyarrow §3.8** for outside-DataFusion grouping |
| `Table.sort_by(...)` | §5.6 (DataFrame sort) | §3.5 ✅ | **datafusion §5.6** for production paths; **pyarrow §3.5** otherwise |

### Compute, expressions, and kernels

| Topic | datafusion | pyarrow | Authoritative |
|-------|-----------|---------|---------------|
| Built-in scalar/aggregate/window/array functions | §7 ✅ | §6, §26 ✅ | **datafusion §7** when running inside DataFusion (optimizer-aware); **pyarrow §6 + §26** for direct kernel use inside UDFs or outside DataFusion |
| Compute kernel encyclopedia + options objects | — | §26 ✅ | **pyarrow §26** |
| `pc.field(...)` / `pc.scalar(...)` / `Expression` deferred logic | — | §6.2 ✅ | **pyarrow §6.2** (distinct from DataFusion's `Expr` — see operating rule 6) |
| Selection (`pc.take`/`pc.filter`) | §33.5 🔁 | §6.3 ✅ | **pyarrow §6.3** |
| Cast + checked kernels + options | §5.8 (DataFrame cast) | §6.5 ✅ | **datafusion §5.8** for DataFrame; **pyarrow §6.5** for kernels |
| Scalar + grouped aggregations + `*Options` | §14 (DataFrame) | §6.6, §6.7 ✅ | **datafusion §14** for production DataFrame paths; **pyarrow §6.6-§6.7** for direct compute |
| User-defined compute registration (scalar/vector/aggregate/non-scalar) | §16 (DataFusion UDF) ✅ | §26.20 🔁 | **datafusion §16** is canonical for the DataFusion path; **pyarrow §26.20** for non-DataFusion compute-extension authoring |

### IO: files, formats, datasets, filesystems

| Topic | datafusion | pyarrow | Authoritative |
|-------|-----------|---------|---------------|
| Parquet read (`pq.read_table` / `ctx.read_parquet`) | §11 ✅ | §11 ✅ | **datafusion §11** when reading into a DataFrame; **pyarrow §11** for direct read or metadata-only inspection |
| Parquet write (`write_parquet` / `pq.write_table` / `write_parquet_with_options`) | §19 ✅ | §11.8, §11.9, §11.10 ✅ | **datafusion §19** for DataFrame terminal writes; **pyarrow §11.8-§11.10** for direct + `ParquetWriter` incremental + `pq.write_to_dataset` |
| Parquet metadata + row groups + footer inspection | §17, §31 (plan/audit) | §11.4, §11.5, §11.6, §11.7 ✅ | **pyarrow §11.4-§11.7** |
| Parquet encryption + KMS | — | §11.11 ✅ | **pyarrow §11.11** |
| CSV read/write | §11 ✅ | §12.1-§12.6 ✅ | **datafusion §11** for DataFrame integration; **pyarrow §12** for direct + streaming + writer options |
| Line-delimited JSON | §11 ✅ | §12.7-§12.10 ✅ | **datafusion §11** for DataFrame integration; **pyarrow §12** for streaming/options |
| Avro read | §11 ✅ | — | **datafusion §11** |
| ORC | — | §12.11-§12.15 ✅ | **pyarrow §12.11-§12.15** |
| Arrow IPC stream + file format | §20 (interop) | §10.1-§10.9 ✅ | **pyarrow §10** for IPC; **datafusion §20** for DataFrame interop with IPC consumers |
| Feather V2 | — | §10.10-§10.13 ✅ | **pyarrow §10.10-§10.13** |
| Datasets (`ds.dataset`/`scanner`/`fragment`) | §3.7 (`register_dataset`) 🔁 | §7 ✅ | **pyarrow §7** is canonical; **datafusion §3.7** is the bridge into a DataFrame |
| Partitioning + predicate pushdown + dataset writes | §19 (DataFrame writes) 🔁 | §8 ✅ | **pyarrow §8** for partitioning/pushdown/`ds.write_dataset`; **datafusion §19** for `write_parquet_with_options` partitioning |
| Filesystem abstraction (`fs.*`, S3/GCS/Azure/HDFS) | §12 (object stores) ✅ | §9 ✅ | **pyarrow §9** for filesystem APIs and protocol details; **datafusion §12** for registering object stores into `SessionContext` |
| Dataset internals + `FragmentScanOptions` | — | §25 ✅ | **pyarrow §25** |

### Arrow ↔ DataFusion interop

| Topic | datafusion | pyarrow | Authoritative |
|-------|-----------|---------|---------------|
| Arrow C Data Interface + PyCapsule (`__arrow_c_array__`/`__arrow_c_stream__`/`__arrow_c_schema__`) | §20.0, §20.1 ✅ | §13.12 ✅ | **pyarrow §13.12** for the protocol; **datafusion §20** for DataFusion's producer + consumer surface (`from_arrow`, `DataFrame.__arrow_c_stream__`) |
| `SessionContext.from_arrow(...)` ingress | §20.2, §11.2 ✅ | — | **datafusion §20.2 + §11.2** |
| `pa.table(df)` (full materialization) vs `pa.RecordBatchReader.from_stream(df)` (streaming) | §20.1, §11.2 ✅ | — | **datafusion §20.1 + §11.2** |
| `__arrow_array__(type=None)` Python duck-array hook | §33.3 🔁 | §5.4, §13.11 ✅ | **pyarrow §5.4 + §13.11** |
| Extension types in DataFusion plans/UDFs | §16 🔁 | §13 ✅ | **pyarrow §13** for authoring; **datafusion §16 + §27** for plan/UDF integration |

### UDFs and user-defined compute

| Topic | datafusion | pyarrow | Authoritative |
|-------|-----------|---------|---------------|
| Scalar UDF authoring (`udf(...)`/`ScalarUDF`) | §16, §33 ✅ | — | **datafusion §16** for syntax; **datafusion §33** for PyArrow/NumPy/SciPy interop within scalar UDFs |
| UDAF authoring (`udaf(...)`, `Accumulator`) | §16, §34 ✅ | — | **datafusion §16 + §34** |
| UDWF authoring (`udwf(...)`, `WindowEvaluator`) | §16, §34 ✅ | — | **datafusion §16 + §34** |
| UDTF authoring (`udtf(...)`, table-provider factory) | §16, §23 ✅ | — | **datafusion §16** for surface; **datafusion §23** for the table-provider interface |
| PyArrow direct compute kernels inside UDFs | §33 ✅ | §6, §26 ✅ | **datafusion §33** for the UDF contract; **pyarrow §6 + §26** for the kernel inventory and options |
| Volatility (`immutable`/`stable`/`volatile`) | §16, §35 ✅ | — | **datafusion §16 + §35** |
| UDF registry + plan-lint gating | §35, §36.16-§36.18 ✅ | — | **datafusion §35 + §36** |
| Non-DataFusion user-defined compute (`pc`-side scalar/vector/aggregate functions) | — | §26.20 ✅ | **pyarrow §26.20** |

### Plan, optimizer, and execution

| Topic | datafusion | pyarrow | Authoritative |
|-------|-----------|---------|---------------|
| Logical / optimized / physical plan inspection (`df.logical_plan()`, `df.optimized_logical_plan()`, `df.execution_plan()`, `df.explain()`) | §17, §30 ✅ | — | **datafusion §17** for surface; **datafusion §30** for lifecycle invariant |
| Plan auditing + linting + governance | §31 ✅ | — | **datafusion §31** |
| Optimizer rule governance + extension limits | §32 ✅ | — | **datafusion §32** |
| Plan snapshot tests (semantic + plan-hash) | §31, §36.16.4-§36.16.5 ✅ | — | **datafusion §31 + §36** |
| Substrait round-trip | §21 ✅ | §15.9-§15.13 ✅ | **datafusion §21** for plan-level; **pyarrow §15.9-§15.13** for expression/schema-level + run_query |
| Acero declarations | — | §15.1-§15.8 ✅ | **pyarrow §15** |
| SQL unparsing (`unparser`) | §22 ✅ | — | **datafusion §22** |
| Custom table providers (`TableProvider` Python interface) | §23 ✅ | — | **datafusion §23** |

### Performance + deployment

| Topic | datafusion | pyarrow | Authoritative |
|-------|-----------|---------|---------------|
| Threading + CPU/IO pools | §18 ✅ | §18, §19 ✅ | **pyarrow §18-§19** for process-wide control; **datafusion §18** for DataFusion-session knobs (`SessionConfig`, `RuntimeEnvBuilder`) |
| Partition + batch-size sizing | §18, §26 ✅ | §19.5 ✅ | **datafusion §18 + §26** for query-side; **pyarrow §19.5** for scanner-side |
| Memory pool selection | §18 ✅ | §4.3, §23 ✅ | **pyarrow §4.3 + §23** for allocator; **datafusion §18** for session config |
| Plan-and-metrics-driven tuning rule | §26 ✅ | — | **datafusion §26** |
| Installation + package variants + capability boundary | §0.1 (catalog), §1 (catalog) | §16 ✅ | **pyarrow §16** for the package-variant taxonomy and conda-forge vs PyPI capability boundary; **datafusion §0.1** for the DataFusion-specific anchor |
| Env var bootstrap ordering (set before `import pyarrow`) | — | §18 ✅ | **pyarrow §18** |
| v23 → v24 migration (PyArrow) | — | §17 ✅ | **pyarrow §17** |
| Compression codecs + allocator strategy | §11, §19 (write options) 🔁 | §23 ✅ | **pyarrow §23** |
| Native C/Cython integration | — | §24 ✅ | **pyarrow §24** |

### Flight, Acero, Substrait, advanced services

| Topic | datafusion | pyarrow | Authoritative |
|-------|-----------|---------|---------------|
| Arrow Flight RPC (client/server, do_get/do_put/do_exchange) | — | §14 ✅ | **pyarrow §14** |
| Flight SQL + Gandiva | — | §27 ✅ | **pyarrow §27** |
| Substrait expressions + schemas + `run_query` | §21 (plan-level) 🔁 | §15.9-§15.13 ✅ | **pyarrow §15.9-§15.13** for the Python surface; **datafusion §21** for the DataFusion engine plan-level integration |
| Acero declarations + node options | — | §15.1-§15.8 ✅ | **pyarrow §15.1-§15.8** |

---

## Decision Trees

### Tree 1: Pick the right engine surface

```
Reading + querying tabular data inside DataFusion (SQL or DataFrame)?
  -> SessionContext + DataFrame + Expr (datafusion §0, §2-§8)
Constructing an Arrow value to feed DataFusion or any other consumer?
  -> PyArrow factories first: pa.array / pa.field / pa.schema / pa.table (pyarrow §0, §1, §2, §3)
Computing on Arrow data outside DataFusion (in a UDF, in a non-engine context)?
  -> pyarrow.compute kernels + Expression (pyarrow §6, §26)
Reading multi-file partitioned data?
  -> ds.dataset(...) + scanner + fragments (pyarrow §7, §8) — bridge into DataFusion via ctx.register_dataset(...) if needed (datafusion §3.7)
Writing partitioned data?
  -> df.write_parquet_with_options(...) when starting from a DataFrame (datafusion §19)
  -> ds.write_dataset(...) / pq.write_to_dataset(...) for direct partitioning (pyarrow §8)
Cross-process data transport?
  -> Arrow IPC stream/file (pyarrow §10) for files; Flight (pyarrow §14) for RPC; Substrait (pyarrow §15.9-§15.13 / datafusion §21) for portable plans
```

### Tree 2: Implement a user-defined function

```
Element-wise transform over Arrow data, deterministic, can express in pyarrow.compute?
  -> Prefer datafusion.functions / Expr methods first (datafusion §7)
  -> Otherwise: @udf([input_types], return_type, "immutable") (datafusion §16, §33)
Group-wise aggregation across rows?
  -> Built-in aggregate function (datafusion §14)
  -> Otherwise: udaf(...) with Accumulator class (datafusion §16, §34)
Per-row output over a partition / window?
  -> Built-in window function (datafusion §15)
  -> Otherwise: udwf(...) with WindowEvaluator class (datafusion §16, §34)
Need to return a relation from literal arguments?
  -> udtf(...) with TableProvider factory (datafusion §16, §23)
Need SciPy / NumPy / scikit-learn?
  -> Validate scientific runtime, then scalar UDF over pa.Array (datafusion §33, §35)
  -> Arrow → NumPy: pa.Array.to_numpy(zero_copy_only=True) when possible (pyarrow §2.6, datafusion §33.2)
Need to register and gate against plan lint?
  -> UDF registry + lint gates as in the governed-pipeline pattern (datafusion §35, §36.16-§36.18)
```

### Tree 3: Define a column type

```
Standard primitive (int/float/string/bool)?
  -> pa.int64() / pa.float64() / pa.string() / pa.bool_() (pyarrow §1.2)
Temporal?
  -> pa.timestamp("us", tz="UTC") / pa.date32() / pa.time64("us") / pa.duration("us") (pyarrow §1.2, §1.5; datafusion §28)
Decimal?
  -> pa.decimal128(precision, scale) (pyarrow §1.2); pa.decimal32 / pa.decimal64 on v24+ (pyarrow §17.5)
Nested struct?
  -> pa.struct([pa.field(...), ...]) — fields are part of the type (pyarrow §1.5; datafusion §28)
Variable-length list?
  -> pa.list_(value_type) / pa.large_list / pa.fixed_size_list (pyarrow §1.5; datafusion §28)
Map?
  -> pa.map_(key_type, item_type) (pyarrow §1.5; datafusion §28)
Dictionary-encoded?
  -> pa.dictionary(index_type, value_type) (pyarrow §1.5)
Domain-specific semantic type?
  -> Extension type via pa.ExtensionType (pyarrow §13.2-§13.7) or canonical extension (pyarrow §13.8, §17.7)
Variadic string/binary view types (v24+)?
  -> pa.string_view() / pa.binary_view() / pa.list_view(...) / pa.large_list_view(...) (pyarrow §17.4)
Fixed-shape tensor (v24+)?
  -> pa.fixed_shape_tensor(value_type, shape=...) canonical extension (pyarrow §17.6, §17.7)
```

### Tree 4: Choose a read path

```
Single Parquet file, want a DataFrame to query?
  -> ctx.read_parquet("path.parquet") (datafusion §11)
Single Parquet file, want just metadata or row groups?
  -> pq.ParquetFile(...) + pq.read_metadata(...) (pyarrow §11.4-§11.7)
Directory of Parquet files with partitions?
  -> ctx.register_parquet("name", "s3://...") (datafusion §11)
  -> Or ds.dataset(..., format="parquet", partitioning=...) and register or scan (pyarrow §7, §8; datafusion §3.7)
CSV?
  -> ctx.read_csv(...) for DataFrame (datafusion §11)
  -> csv.read_csv(...) for direct Table; csv.open_csv(...) for streaming (pyarrow §12.2, §12.6)
Line-delimited JSON?
  -> ctx.read_json(...) for DataFrame (datafusion §11)
  -> json.read_json(...) / json.open_json(...) for direct (pyarrow §12.8, §12.10)
ORC?
  -> orc.read_table(...) / ORCFile(...) (pyarrow §12.12, §12.13); DataFusion has no read_orc — register via dataset
Arrow IPC stream/file or Feather?
  -> ipc.open_stream(...) / ipc.open_file(...) / feather.read_table(...) (pyarrow §10) — then ctx.from_arrow(...) to enter DataFusion (datafusion §11.2, §20.2)
Remote object store?
  -> Register the object store (datafusion §12), then ctx.read_* / ctx.register_*
  -> Or fs.S3FileSystem(...) / GcsFileSystem / AzureFileSystem / HadoopFileSystem (pyarrow §9.5-§9.8) + ds.dataset(..., filesystem=...)
```

### Tree 5: Choose a write path

```
DataFusion DataFrame → Parquet single file?
  -> df.write_parquet("path.parquet") (datafusion §19)
DataFusion DataFrame → Parquet with explicit writer options (compression/encryption/row-group size)?
  -> df.write_parquet_with_options(...) (datafusion §19)
DataFusion DataFrame → CSV / JSON?
  -> df.write_csv(...) / df.write_json(...) (datafusion §19)
DataFusion DataFrame → registered table?
  -> df.write_table("name") — target must be registered and writable (datafusion §19)
Outside DataFusion: single-file Parquet?
  -> pq.write_table(table, path, ...) (pyarrow §11.8)
Outside DataFusion: incremental / row-group-aware Parquet?
  -> pq.ParquetWriter(path, schema, ...) (pyarrow §11.9)
Outside DataFusion: partitioned data lake?
  -> ds.write_dataset(...) for the general writer (pyarrow §8.9) or pq.write_to_dataset(...) (pyarrow §8.14, §11.10)
Arrow IPC stream/file?
  -> ipc.new_stream(...) / ipc.new_file(...) (pyarrow §10.1, §10.4); feather.write_feather(...) for Feather (pyarrow §10.12)
CSV / JSON / ORC?
  -> csv.write_csv(...) / orc.write_table(...) / ORCWriter(...) (pyarrow §12.6, §12.14, §12.15) — no first-class JSON writer in Arrow
```

### Tree 6: Diagnose a slow query

```
Where is the cost?
  -> df.explain(analyze=True) to inspect optimized + physical plan + per-node metrics (datafusion §17, §26)
Plan looks right but execution is slow?
  -> Inspect partition_count, batch_size, repartition rules (datafusion §18, §26)
  -> Inspect Arrow scanner controls (pyarrow §19.5: batch_size, batch_readahead, fragment_readahead)
Parquet read is slow?
  -> Confirm projection pushdown (datafusion §11; pyarrow §11.2, §11.3) and partition pruning (pyarrow §8.8)
Object store read is slow?
  -> Check the object-store registration (datafusion §12) and IO-pool sizing (pyarrow §19.3)
UDF is slow?
  -> Move to pyarrow.compute (pyarrow §6, §26), or use pc.* inside the UDF (datafusion §33)
  -> Check UDF volatility tag (datafusion §16, §35) — volatile blocks constant-folding
Wide rows / nested data?
  -> Set batch_size, use fragment-aware iteration (pyarrow §7.8, §7.9)
Repeated similar queries?
  -> Snapshot logical_plan + optimized_logical_plan + execution_plan (datafusion §17, §31) and diff
Memory pressure?
  -> Switch to streaming (datafusion §4: execute_stream; pyarrow §3.9: to_reader) and avoid to_pandas / collect on unbounded results
```

### Tree 7: Compare schemas / detect drift

```
Same two pa.Schema objects, want strict equality including metadata?
  -> schema_a.equals(schema_b, check_metadata=True) (pyarrow §1.7)
Want to merge possibly-divergent schemas across files?
  -> pa.unify_schemas([s1, s2, ...]) (pyarrow §1.12)
Want a structured diff (added/removed/typed-changed fields)?
  -> Schema diff + compatibility report pattern (pyarrow §31.6, §31.7)
Want a stable identity for plan/snapshot tests?
  -> schema.serialize() bytes → hash → fingerprint (datafusion §27, §29; pyarrow §31.15)
Operating across DataFusion + PyArrow + Parquet + dataset + partition layers?
  -> Use the schema-as-API-contract layer model: logical / physical / dataset / partition / IPC / Parquet (pyarrow §31.0)
Want to enforce a schema as the API boundary of a registered source?
  -> Source registry + validate_registered_source pattern (datafusion §27, §36)
```

### Tree 8: Cross runtimes via Arrow

```
Producer is PyArrow / Polars / pandas / cuDF? (Has __arrow_c_stream__ or __arrow_c_array__)
  -> ctx.from_arrow(producer) (datafusion §20.2; pyarrow §13.12)
Consumer wants the whole table eagerly?
  -> pa.table(df) — fully materializes (datafusion §20.1)
Consumer wants to stream batches?
  -> pa.RecordBatchReader.from_stream(df) (datafusion §20.1, §11.2)
Need to define a custom Python type that participates in Arrow conversion?
  -> Implement __arrow_array__(type=None) (pyarrow §5.4, §13.11)
Need to export a typed columnar value across the PyCapsule boundary?
  -> Implement __arrow_c_schema__ / __arrow_c_array__ / __arrow_c_stream__ on the producer class (pyarrow §13.12)
Pandas extension dtype that round-trips through Arrow?
  -> to_pandas_dtype() on the extension type + __from_arrow__ on the pandas dtype (pyarrow §5.16, §13.13)
```

---

## Operating Rules

1. **DataFusion is a plan engine; PyArrow is the substrate.** SQL and DataFrame calls build a `LogicalPlan` that is optimized into a physical plan and executed against an Arrow `RecordBatch` stream. PyArrow is the type system, container model, IO layer, and compute kernel library that DataFusion consumes. When in doubt about *what* a value is, reach for pyarrow; when in doubt about *how* it executes, reach for datafusion. (datafusion §0.4, §0.5, §30; pyarrow §0.2, §0.3)

2. **`DataFrame` is lazy. Terminal operations execute.** `collect()`, `collect_partitioned()`, `to_pandas()`, `to_pydict()`, `show()`, `execute_stream()`, `execute_stream_partitioned()`, and **every** `write_*` are terminal. Transformations such as `filter`, `select`, `sort`, `limit`, `aggregate`, `join` are not. Composing transformations is free; calling a terminal is not. (datafusion §0.6, §4, §19.0)

3. **PyArrow containers are immutable; mutation is replacement.** `Schema.append(...)`, `Field.with_nullable(...)`, `RecordBatch.add_column(...)`, `schema.with_metadata(...)` all return new objects. Never assume in-place mutation; assign the return value. Design around replacement, not aliasing. (pyarrow §0.4, §1.7; datafusion §27.1.2)

4. **`pa.Array` and `pa.ChunkedArray` are not the same.** `Table.column(i)` returns a `ChunkedArray` — it has chunks. `RecordBatch.column(i)` returns an `Array`. Code that assumes single-chunk semantics on a table column will misbehave on real data. When unifying, use `chunked.combine_chunks()` deliberately (cost: copy). (pyarrow §2.3, §2.7, §2.8)

5. **Nulls are validity bitmaps, not sentinels.** Do not encode missingness with `-1`, `NaN`, or empty strings. Use `pa.array([...], type=...)` with explicit `None` entries, or `mask=` to set a validity bitmap. SciPy/NumPy egress that goes through `to_numpy(zero_copy_only=True)` fails when nulls exist — that is by design. (pyarrow §2.4; datafusion §33.2)

6. **DataFusion `Expr` and PyArrow `Expression` are different.** DataFusion's `datafusion.col("x") > datafusion.lit(0)` builds an engine `Expr` that participates in the optimizer. PyArrow's `pc.field("x") > pc.scalar(0)` builds a compute `Expression` for `pc.filter` / `dataset.scanner(filter=...)`. They are not interchangeable. Inside a UDF body you use PyArrow compute; inside a DataFrame call you use DataFusion `Expr`. (datafusion §6; pyarrow §6.2)

7. **Parenthesize boolean operator chains.** `col("a") > 0 & col("b") < 10` parses as `col("a") > (0 & col("b")) < 10` because Python `&`/`|` precedence is lower than comparison. Write `(col("a") > 0) & (col("b") < 10)`. Same rule applies to PyArrow `Expression`. (datafusion §6.5)

8. **The DataFusion → PyArrow boundary supports both materializing and streaming forms.** `pa.table(df)` runs the plan and materializes the whole table — fine for bounded preview/test results, dangerous for unbounded production data. `pa.RecordBatchReader.from_stream(df)` streams batches and is the correct choice for write-through, network transport, or long results. The same dichotomy applies inside DataFusion: `df.collect()` vs `df.execute_stream()`. (datafusion §4, §20.1, §11.2)

9. **Cross-runtime exchange goes through the Arrow C Data / C Stream protocol, not pickle.** Any producer implementing `__arrow_c_stream__` or `__arrow_c_array__` works with `ctx.from_arrow(...)`. `DataFrame` itself implements `__arrow_c_stream__`, so any Arrow-compatible consumer can drink from it directly. Never serialize through pickle, JSON, or pandas as an interop bridge if a PyCapsule path exists. (datafusion §20.0-§20.2; pyarrow §13.12)

10. **Bootstrap PyArrow env vars before `import pyarrow`.** Pool sizes, SIMD level, timezone DB, S3 diagnostics, and allocator backend are read at import time. Setting them after import has no effect. Centralize this in a `bootstrap_arrow_env.py` that runs before any module that imports pyarrow. Same rule for DataFusion `SessionConfig` — set the config when constructing the `SessionContext`, not midway through a session. (pyarrow §18.4; datafusion §18)

11. **PyArrow capability is a packaging choice, not just an install command.** `pyarrow-core` ≠ `pyarrow` ≠ `pyarrow-all`. Native components (`libparquet`, `libarrow-dataset`, `libarrow-acero`, `libarrow-substrait`, `libarrow-flight`, `libarrow-flight-sql`, `libarrow-gandiva`) determine whether `pyarrow.parquet`, `pyarrow.dataset`, `pyarrow.acero`, `pyarrow.substrait`, `pyarrow.flight`, `pyarrow.gandiva` can be imported. Use runtime capability probes before using optional surfaces; encode a capability manifest at deployment boundaries. (pyarrow §16.4-§16.5, §16.12)

12. **v23 vs v24 deltas matter for view types, decimal32/64, fixed-shape tensors, canonical extension types, and sparse tensors.** When authoring code that may run against either version, use the v17 reconciliation harness — probe for the type/feature, downgrade or fail loudly. The smartref baseline pins `pyarrow>=23.0.1`; do not silently assume v24-only types are available. (pyarrow §17)

13. **`load_solutions=False` analog: never collect blindly after a planner/optimizer change.** When the optimizer changes, plan output can change. Snapshot logical + optimized + physical plans for production queries (datafusion §17, §31, §32) and compare on upgrade. The plan-lint pattern in datafusion §31 + §36.16-§36.18 is the governance baseline.

14. **Prefer built-ins over UDFs; prefer PyArrow compute inside UDFs over SciPy/NumPy.** The DataFusion UDF guide explicitly recommends built-in expressions and functions before custom Python. Inside a scalar UDF, prefer `pyarrow.compute` (Arrow-native, batch-oriented, no Python boundary per row). Reach for NumPy/SciPy only when the algorithm is not available in either built-in or `pc.*`. (datafusion §7, §16, §33.1)

15. **Use Datasets for multi-file partitioned data; do not glob manually.** A naïve `glob("*.parquet") + concat` defeats partition pruning, predicate pushdown, and row-group statistics. Use `ds.dataset(..., partitioning=...)` and let it construct a `Scanner` with the correct filter and projection. Inside DataFusion, `ctx.register_dataset(...)` lifts the PyArrow Dataset into a registered table. (pyarrow §7.3, §8.8; datafusion §3.7)

16. **Treat schema as a contract artifact, not incidental metadata.** Every production pipeline should fingerprint its schemas, declare them at source registration, and validate them in CI. Schema drift is the leading cause of silent correctness regressions across DataFusion + PyArrow + Parquet + dataset + partition layers. (datafusion §27, §29, §36; pyarrow §31)

17. **Markup-style untrusted-input attacks exist for Arrow too — but the attack surface is schema metadata, not text.** PyArrow schemas accept arbitrary `bytes → bytes` metadata. Treat metadata bound from untrusted sources as data, never as control. Hash metadata into governance keys deliberately (`schema.serialize()` is the canonical lossless representation). (pyarrow §1.9, §31.10)

18. **The two-pass DataFusion document layout requires you to disambiguate `§N` by line range.** Pass-1 §27 (line 669) is the "Testing strategy" framing catalog; Pass-2 §27 (line 32498) is the "Schema engineering I" deep-dive. They share a number. When this skill points to `datafusion §27`, the surrounding context (line range or topic) tells you which pass. Always Read with explicit offset.

19. **PyArrow section numbers 20, 21, and 28-30 are absent — that is not a documentation bug.** Use the surrounding sections (§19 for threading, §22 for sparse tensors, §27 for Flight SQL + Gandiva, §31 for advanced schema engineering) rather than searching for the missing numbers.

20. **DataFusion Pass-1 §1 is catalog-only; install/runtime semantics live in Pass-1 §0.1 + §0.15.** There is no `# DataFusion Advanced — 1)` deep-dive header — do not search for one. The deployment baseline is the version-anchor block in Pass-1 §0.1; the operational guidance is in §0.15 (deployment advisory). The smartref `pyproject.toml` carries the binding pin.

---

## Project context: smartref

DataFusion is declared as a runtime dependency in `pyproject.toml` (`datafusion>=53.0.0`) and registered as the `analytics.datafusion` backend in `src/smartref/bootstrap/composition/backend_manifest_definition.py:51`, but **no `import datafusion` / `from datafusion` call sites exist in `src/` yet**. When DataFusion integration lands, the governed-pipeline pattern in datafusion §36 is the target architecture: schema registry + source registry + UDF registry + query builder + plan lint + execution policy + artifact manifest.

PyArrow is used extensively, primarily in `src/smartref/shared/source_ingress/workbook/workbook_package_arrow/`:

- `arrow_relation_plan.py`, `arrow_relation_metrics.py` — relation-shape representation and metrics
- `arrow_field_lowering.py`, `field_contracts.py` — field schema lowering and per-field contracts
- `arrow_table_builder.py` — Table construction
- `arrow_specs/` — Arrow type specs (depends heavily on pyarrow §1)
- `schema_arrow_materialization.py` — schema materialization (pyarrow §1, §31)
- `package_reader.py`, `package_writer.py`, `package_verifier.py`, `normalized_package_reader.py` — Arrow IPC / Parquet IO paths (pyarrow §10, §11)
- `dataset_write_manifest.py` — partitioned write manifests (pyarrow §8, §11)
- `postgres_load_plan_io.py` — bridge from Arrow into Postgres

When changing Arrow ingress / egress code, consult **pyarrow §1 (types/fields/schemas)**, **§3 (RecordBatch/Table)**, **§7-§8 (datasets + partitioning)**, **§10 (IPC)**, **§11 (Parquet)**, and **§31 (advanced schema engineering — `inspect_schemas`, fragment vs dataset schema, IPC/Parquet round-trip)** alongside the local module these files belong to. The project's contract substrate (attrs/cattrs) handles boundary conversion *into* domain models; Arrow-side schema contracts are upstream of that. Never treat `pa.Schema.metadata` as application state — it is a governance / provenance channel only.

When the DataFusion integration ships, it will sit downstream of `workbook_package_arrow/` and consume the produced Arrow Tables / IPC streams via `ctx.from_arrow(...)` (datafusion §20.2). At that boundary, **the schema-as-API-contract layer model from pyarrow §31.0 applies in full**: logical schema (`pa.Schema`) ↔ physical schema (Parquet/IPC) ↔ dataset schema (`ds.Dataset.schema`) ↔ partition schema (`ds.partitioning(...)`) ↔ DataFusion table schema (`Table.schema`) — all six must agree, and any disagreement is a contract violation.
