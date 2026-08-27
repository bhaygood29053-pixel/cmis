# X1 Oracle V2 Timestamp-Unit Promotion — 2026-08-27

Status: **timestamp unit verified / freshness and price authority not promoted**

Tracker: **#293**

Governance mechanism: **#288 / #290**

Live evidence baseline: **#283 / #285**

Parent Oracle V2 evaluation: **#272**

## Operator decision

The operator explicitly directed:

```text
timestamp_unit_verified = true
```

CMIS does not implement that instruction as an unconditional flag flip.

It implements it as approval to apply the deterministic timestamp-unit
governance contract to a narrowly scoped, evidence-bound production policy.

The flag may become true only if the live recollected evidence satisfies every
governance gate.

## Accepted promotion policy

```text
max_difference_ms = 1604
minimum_sample_count = 25
minimum_distinct_relay_count = 5
temporal_coverage_mode = single_bounded_window
require_deployed_binary_equivalence = false
```

These are explicit accepted policy values, not hidden defaults.

### Correlation ceiling provenance

`max_difference_ms=1604` is the exact maximum raw candidate Unix-ms
correlation difference observed in the accepted fixed-head live evidence run:

```text
workflow_run = 33037942117
artifact_id = 9632727323
artifact_sha256 =
7dd0c340490aaf738299a0900722cbd0d515b2062038de30585f99359c2e90e0
head_sha = bbb6f8e7c69cb41e3f966f2d791ad0c6c01b8e90
```

This ceiling is evidence-bound.

It is **not**:

- an upstream Oracle guarantee;
- an X1 network guarantee;
- a generic CMIS default;
- a freshness threshold;
- a recommendation for other providers.

A newly recollected sample at **1605 ms** fails promotion under this policy.

### Sample sufficiency provenance

`minimum_sample_count=25` preserves the full accepted bounded sample set from
the fixed-head live evidence.

CMIS does not weaken that baseline to make promotion easier.

Duplicate transaction signatures cannot increase this count.

### Relay coverage provenance

`minimum_distinct_relay_count=5` requires all five Oracle V2 relay slots to be
represented in the accepted evidence set.

This is coverage of same-system relay redundancy.

It is **not** source-independence evidence.

### Temporal coverage provenance

The accepted mode is:

```text
single_bounded_window
```

This is an explicit operator decision that one bounded historical transaction
window is sufficient to establish **timestamp unit semantics only**.

It does not establish current freshness.

### Deployed binary/source equivalence decision

The policy explicitly sets:

```text
require_deployed_binary_equivalence = false
```

The rationale is narrow:

- exact expected Oracle program/state;
- exact Anchor batch instruction shape;
- exact batch signed-message shape;
- Ed25519 message/signature/current-key/pre-instruction binding;
- successful transaction history;
- matching transaction/history/block-time evidence;
- deterministic Unix-ms correlation evidence;

are accepted as sufficient to establish timestamp-unit semantics.

The underlying fact remains:

```text
deployed_binary_source_equivalence_verified = false
```

unless independently proved later.

## Live promotion gate

The promotion workflow recollects a fresh bounded view of the accepted
historical evidence through the existing read-only probe.

It then evaluates that raw evidence using:

`evaluate_oracle_v2_timestamp_unit_promotion`

The workflow fails unless:

```text
status = ok
timestamp_unit_verified = true
all_governance_gates_passed = true
```

and all downstream authority fields remain false.

## Mandatory downstream boundary

A successful timestamp-unit promotion does **not** imply any of the following:

```text
freshness_verified = false
price_correctness_verified = false
source_independence_verified = false
current_price_use_authorized = false
cmis_provider_promoted = false
public_service_promoted = false
scout_reliance_promoted = false
execution_authorized = false
```

## Live promotion result

The branch-scoped live promotion workflow completed successfully:

```text
workflow_run = 33038921907
artifact_id = 9633092384
artifact_sha256 =
32ec5e8d46326900d881da4162177b29b68b829e1ca82337db22f6a5bd94ad07

policy_sha256 =
0a91fbc4a6d4b8befe728419e661e9eea4ad189a48b746a2ea7f18c5f86d05ab

evidence_sha256 =
984f3208ae17043880407cdc85964e87ee42cee54d50c322ac065d0fb135c135
```

The live governance summary was:

```text
unique_signature_count = 25
distinct_relay_count = 5
minimum_recomputed_difference_ms = 576
maximum_recomputed_difference_ms = 1604
```

Every promotion gate passed:

```text
source_identity = true
sample_integrity = true
all_samples_within_explicit_tolerance = true
minimum_sample_count = true
minimum_distinct_relay_count = true
temporal_coverage = true
deployed_binary_equivalence_requirement = true
```

The resulting verified fact is:

```text
timestamp_unit_verified = true
```

The binary-equivalence gate is true because the accepted policy explicitly does
not require deployed binary/source equivalence for timestamp semantics. The
underlying binary-equivalence fact itself remains unverified.

All downstream authority fields remained false in the same live artifact.

## What this promotion authorizes

Only this fact:

```text
Oracle V2 raw batch timestamps may be interpreted as Unix milliseconds
under the accepted evidence-bound X1 block-time correlation policy.
```

That verified timestamp-unit evidence may then be supplied to the already
accepted Oracle V2 freshness classifier.

## What comes next

After live promotion passes, the next gate is **current-slot freshness policy
application**.

That later step must still use explicit operator-owned values and provenance for:

- `max_age_ms`;
- `max_future_skew_ms`;
- `minimum_eligible_slots`.

No Oracle V2 current price becomes CMIS-authoritative merely because the
timestamp unit is verified.
