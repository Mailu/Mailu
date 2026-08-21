# Mailu SCIM full-scan endpoint and Amdahl report

Date: 2026-08-13 (America/Chicago)  
Final source: `9a1269977f01775dfedf207f877aa05e5b26dd3a`  
Whole-pass baseline: `e8e3d7267fc4975540c80e2d7ed3b979846c38ae`

## Ruling

The one-query iterative full-edge scan is the correct production mechanism and
the q64 probe/fallback policy remains rejected. The final source passed the
relevant correctness gates on SQLite, PostgreSQL 17, MariaDB 11 through
`mysqlconnector`, and MariaDB 11 through `mariadbconnector`.

The strict 2026-08-01 benchmark protocol is **not fully satisfied**, so this
report does not claim unconditional final performance admission. The
load-bearing blockers are explicit:

1. SQLite concurrency-4 Group replacement returns HTTP 500 `database is locked`
   at the singleton graph lock on both the completion baseline and final source.
   This is inherited, not introduced by `9a126997`, but it makes the required
   SQLite c4 throughput cells invalid.
2. The 15-cell latency/Amdahl matrix is instrumented. A distinct 1,000-sample
   uninstrumented latency matrix and empty-wrapper control were not completed.
3. Endpoint performance was measured through MariaDB `mysqlconnector` only.
   `mariadbconnector` passed correctness/migration/race gates but did not receive
   a separate endpoint performance corpus.
4. The adaptive-slice `6c741940` versus final endpoint comparison was not rerun.
   The architecture rejection still rests on the preserved 2,222-case selector
   corpus and the earlier q64 evidence, not a new endpoint slice.
5. The locked endpoint contract required PATCH parity and a pathological-wide
   workload. This corpus measures PUT only and has no wide endpoint cell.
6. The main A/B cohorts ran one complete build after the other. Reverse-order
   controls changed the direction of PostgreSQL S latency and MariaDB T/c1
   throughput; therefore the fixed-order ratios are descriptive observations,
   not admissible causal estimates. A block/window-level randomized or ABBA
   rerun is required for final performance admission.

Those are evidence gaps, not excuses. No PR, merge, deployment, or known-good
marker is authorized by this report.

## Implementation

P2.3's q64 probe/fallback was replaced narrowly with:

- one complete locked `scim_group_member` edge query;
- a reverse-adjacency map;
- an iterative worklist traversal;
- preserved zero-query empty and direct-self handling;
- no counter, threshold, query cap, row budget, cache, migration, recursion, or
  driver-specific production policy.

The final patch is 52 insertions and 110 deletions across `models.py`, its
focused tests, and the CI selector. It removes mechanism and policy rather than
adding another abstraction.

## Correctness and backend gates

All recorded gates passed:

- SQLite: 9 focused full-scan tests; 16 related graph tests; 351 broad tests
  with 9 expected skips.
- PostgreSQL 17: 5 migration tests with 2 skips; 289 runtime tests with 7 skips.
- MariaDB 11/mysqlconnector: 6 migration tests with 1 skip; 37 graph/race tests
  with 170 deselected.
- MariaDB 11/mariadbconnector: 6 migration tests with 1 skip; 37 graph/race
  tests with 170 deselected.
- Rebuilt admin image manifest-list digest:
  `sha256:a7e7fe10c1f9e65051ccb139397c73a6f01b4e362f692a032a8cf7688c4f7adc`.

Exact copies of the XML and image metadata are in
`correctness/final-20260813/` and are bound by this corpus manifest. The test
runner did not embed source commit or expanded command properties; that
identity remains an operator record and does not satisfy the strict
self-identifying evidence requirement.

## Instrumented HTTP latency and Amdahl matrix

Each of 15 lane/workload cells contains 1,000 baseline and 1,000 final measured
requests: 40 fixture-reset blocks, 10 warmups, and 25 admitted samples per
block. Total admitted samples: 30,000. Every admitted request returned HTTP 200,
SCIM JSON, matching ETag/meta.version, exact members, and exact destinations.

The table below reports observed mean HTTP speedup, p95 ratio, measured program
hotspot speedup, predicted Amdahl speedup, and residual. Ratios above 1 favor
final.

| Lane | Workload | Mean | p95 | Hotspot | Predicted | Residual |
|---|---:|---:|---:|---:|---:|---:|
| SQLite | S | 0.968x | 1.129x | 0.970x | 0.971x | -0.3% |
| SQLite | T | 1.013x | 1.241x | 1.019x | 1.018x | -0.5% |
| SQLite | L | 1.072x | 0.990x | 1.075x | 1.074x | -0.1% |
| SQLite | P | 1.417x | 1.342x | 1.432x | 1.425x | -0.6% |
| SQLite | B | 1.056x | 1.064x | 1.058x | 1.056x | -0.0% |
| PostgreSQL | S | 0.891x | 0.697x | 0.882x | 0.901x | -1.1% |
| PostgreSQL | T | 1.190x | 1.080x | 1.230x | 1.203x | -1.0% |
| PostgreSQL | L | 1.204x | 1.196x | 1.214x | 1.205x | -0.0% |
| PostgreSQL | P | 1.969x | 1.666x | 2.006x | 1.973x | -0.2% |
| PostgreSQL | B | 1.264x | 1.168x | 1.281x | 1.260x | +0.3% |
| MariaDB/mysqlconnector | S | 1.151x | 1.217x | 1.164x | 1.133x | +1.6% |
| MariaDB/mysqlconnector | T | 1.557x | 1.497x | 1.637x | 1.545x | +0.8% |
| MariaDB/mysqlconnector | L | 1.148x | 1.138x | 1.151x | 1.147x | +0.1% |
| MariaDB/mysqlconnector | P | 1.943x | 1.868x | 1.966x | 1.938x | +0.2% |
| MariaDB/mysqlconnector | B | 1.240x | 1.188x | 1.253x | 1.240x | -0.0% |

The exact unrounded substitutions are in `tables/amdahl.csv`. For every row:

```text
P = H_baseline / T_baseline
S_hotspot = H_baseline / H_final
S_pred = 1 / ((1 - P) + P / S_hotspot)
S_observed = T_baseline / T_final
```

Every residual is below 2%; the phase decomposition explains the instrumented
cohort without pretending the cycle-only ratio is overall endpoint speedup.

### PostgreSQL small reverse-order control

The first cohort showed an apparent 10.9% mean regression. A second 1,000-sample
cohort ran final before baseline and reversed the result: final was 2.4% faster
on mean and 5.6% faster at p95. Pooling both cohorts gives 2,000 samples/build:
baseline 27.445 ms mean versus final 28.662 ms, a 4.44% regression. The pooled
result stays below the 5% materiality threshold but demonstrates substantial
run-order drift. Both cohorts remain preserved.

## Throughput

PostgreSQL and MariaDB each have 20 complete build/workload/concurrency cells:
seven windows, five-second warmup, fifteen-second measurement, fixture restore
between windows, one Gunicorn worker, closed-loop c1/c4, exact response/ETag
validation, and zero HTTP errors. `tables/throughput.csv` contains all 30
expected rows, including SQLite failure/N/A states.

Representative median requests/second:

| Lane/workload | c1 baseline | c1 final | c1 ratio | c4 baseline | c4 final | c4 ratio |
|---|---:|---:|---:|---:|---:|---:|
| PostgreSQL T | 21.71 | 26.37 | 1.21x | 14.31 | 17.38 | 1.21x |
| PostgreSQL P | 3.06 | 5.91 | 1.93x | 3.24 | 6.19 | 1.91x |
| PostgreSQL B | 11.40 | 10.85 | 0.952x | 9.54 | 10.29 | 1.08x |
| MariaDB T, first cohort | 13.61 | 12.71 | 0.934x | 9.81 | 13.37 | 1.36x |
| MariaDB P | 2.24 | 4.20 | 1.88x | 1.98 | 4.09 | 2.06x |
| MariaDB B | 5.46 | 6.82 | 1.25x | 5.91 | 7.51 | 1.27x |

MariaDB T/c1 was rerun in reverse order because the first median contradicted
total completions. The reverse cohort was baseline 13.22 versus final 19.48
requests/s. Across all 14 windows, pooled medians are baseline 13.45 and final
19.37 requests/s. This is reported as order-sensitive evidence, not a stable
single-run guarantee.

SQLite T/c1 completed at 4.52 baseline versus 4.76 final requests/s. SQLite T/c4
failed on both sources with the same `sqlite3.OperationalError: database is
locked` at `UPDATE scim_state ...`; remaining SQLite throughput cells were not
run after the inherited failure was established.

## Query, row, and byte work

The final source uses 19 or 21 queries in the mandatory cells versus baseline
21, 40, or 147. The full-scan cycle query returns exactly E fixture rows; raw
records preserve the logical UTF-8 value-byte lower bound, bind bytes, request
bytes, and response bytes. These are application-visible values, not database
wire bytes or rows examined. The detailed SQL-result proxy and backend plan
appendix required by the strict protocol were not completed; timing claims do
not rely on fabricated row-wrapper timings.

## Environment

- Host: Linux 7.1.5-arch1-2, AMD EPYC 7551P, 32 cores/64 threads, 220 GiB RAM.
- Container engine: Docker 29.7.1.
- PostgreSQL: 17.10.
- MariaDB: 11.8.8.
- Runner: rebuilt `mailu/admin:scim-final-9a126997`.

## Final call

The code change is smaller, mechanically understandable, correctness-clean,
and strongly better on the pathological endpoint workload. It does not justify
an unconditional final-admission claim because the strict evidence contract is
incomplete and SQLite c4 fails on both revisions. The honest ruling is:
**accept the full-scan implementation with constraints; reject any claim that
the complete benchmark/admission protocol is clean.**

Two independent cold reviews reached the same split verdict: no production
source defect was found, but final performance admission is rejected. Review 1
is `reviews/review-1.md`; review 2 is `reviews/review-2.md`. Their blockers and
the resulting conditions are incorporated into `FINAL-RULING.md`.
