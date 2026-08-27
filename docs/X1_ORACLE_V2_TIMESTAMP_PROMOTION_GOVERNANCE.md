# X1 Oracle V2 Timestamp-Unit Promotion Governance

Status: **deterministic governance mechanism / no production promotion policy selected**

Tracker: **#288**

Parent Oracle V2 evaluation: **#272**

Timestamp/freshness policy: **#277 / #280**

Live timestamp evidence: **#283 / #285**

## Purpose

This contract defines how CMIS may convert already-collected Oracle V2
timestamp-correlation evidence into:

```text
timestamp_unit_verified = true
```

It does not define the production numerical values that must be used.

The policy remains fail-closed until those values and their provenance are
explicitly supplied.

## Current evidence baseline

The accepted live evidence path has demonstrated, for one bounded run:

- 25 accepted batch samples from 25 requested history rows;
- all five relay indexes represented;
- exact Oracle program and state binding;
- exact Anchor `batch_submit_prices` decoding;
- exact batch signed-message decoding;
- Ed25519 message/signature/current-key/pre-instruction binding;
- X1 history / transaction / `getBlockTime` agreement;
- candidate Unix-ms differences observed from **576 ms through 1604 ms**.

These observations do not themselves choose a production tolerance or
sample-sufficiency rule.

## No hidden promotion defaults

CMIS supplies no default values for:

- `max_difference_ms`;
- `minimum_sample_count`;
- `minimum_distinct_relay_count`;
- `minimum_evidence_span_ms`.

All numerical values require explicit provenance.

The contract also requires an explicit decision about whether deployed
binary/source equivalence is required for timestamp-unit promotion.

## Policy shape

A complete policy has the form:

```json
{
  "max_difference_ms": "<explicit non-negative integer>",
  "max_difference_provenance": "<why this tolerance is accepted>",

  "minimum_sample_count": "<explicit positive integer>",
  "minimum_sample_count_provenance": "<why this count is sufficient>",

  "minimum_distinct_relay_count": "<explicit integer 1..5>",
  "minimum_distinct_relay_count_provenance": "<why this coverage is sufficient>",

  "temporal_coverage_mode": "minimum_span_ms | single_bounded_window",
  "minimum_evidence_span_ms": "<required only for minimum_span_ms>",
  "temporal_coverage_provenance": "<why this temporal rule is accepted>",

  "require_deployed_binary_equivalence": "<explicit boolean>",
  "binary_equivalence_requirement_provenance": "<why binary equivalence is or is not required>"
}
```

No omitted numerical field is filled by CMIS.

## Temporal coverage modes

### `minimum_span_ms`

The policy specifies an explicit minimum evidence span.

CMIS computes the span only from verified X1 block times:

```text
verified_block_time_span_ms =
    (max(verified_block_time_seconds)
     - min(verified_block_time_seconds)) * 1000
```

The gate passes when:

```text
verified_block_time_span_ms >= minimum_evidence_span_ms
```

The raw candidate Oracle timestamp is not used to establish temporal coverage
because the unit itself is the fact under evaluation.

### `single_bounded_window`

This is an explicit governance decision that one bounded evidence window is
sufficient.

No hidden `minimum_evidence_span_ms` is permitted in this mode.

The policy still must satisfy the explicit sample-count and relay-coverage
requirements.

## Evidence identity gate

The evidence bundle must identify exactly:

```text
service = x1_oracle_v2_timestamp_unit_probe
chain = x1
repository = jacklevin74/oracle-v2
pinned_commit = 97177f772689e44ca4eed9bb95be32ffdf0c5e66
program_id = 9mPmjK8NxJadYDiHiYAQH4WFCnKJr7ZV8ria63ZkMtv2
state_pda = 8XZBqbKhFXHqNGzxV3Tt6gEs9r8ZrNghsRg7zBwLMGJf
status = evidence_collected
```

A mismatched deployment, source snapshot, service, or chain fails closed.

## Oracle signing-key gate

The evidence bundle must preserve the hash of the current configured Oracle
public key read from the verified Oracle state account.

Every accepted sample must independently preserve:

- the configured Oracle public-key hash;
- the Ed25519 public-key hash;
- `ed25519_pubkey_matches_current_state = true`;
- `ed25519_signature_matches_batch_argument = true`;
- `ed25519_precedes_oracle_instruction = true`.

The configured key hash and Ed25519 key hash must equal the bundle's verified
current Oracle-key hash.

Historical key continuity remains separate:

```text
historical_key_continuity_verified
```

is preserved from evidence and is never inferred by this governance step.

## Per-sample correlation

For every integrity-valid sample CMIS recomputes:

```text
difference_ms =
    abs(timestamp_raw - verified_block_time_seconds * 1000)
```

Caller-provided aggregate minimum/maximum values are not trusted for promotion.

If a sample contains a reported
`candidate_unix_ms_difference_ms`, it must equal the recomputed value or the
evidence fails integrity validation.

The correlation gate requires:

```text
difference_ms <= max_difference_ms
```

for **every included accepted sample**.

One sample outside the explicit tolerance blocks timestamp-unit verification.

## Sample sufficiency

CMIS computes sample sufficiency from unique transaction signatures.

Duplicate signatures:

- do not increase the unique sample count;
- fail the evidence-integrity gate.

The policy passes the count gate only when:

```text
unique_signature_count >= minimum_sample_count
```

Caller-supplied aggregate claims such as
`decoded_verified_batch_samples` do not control this calculation.

## Relay coverage

CMIS computes distinct relay indexes from integrity-valid sample records.

The gate passes only when:

```text
distinct_relay_count >= minimum_distinct_relay_count
```

Relay coverage is therefore evidence-derived, not caller-declared.

## Deployed binary/source equivalence

The policy must explicitly set:

```text
require_deployed_binary_equivalence = true | false
```

with provenance.

If `true`, the evidence bundle and every accepted sample must carry verified
binary/source-equivalence evidence.

If `false`, the gate passes without changing the underlying fact:

```text
deployed_binary_source_equivalence_verified = false
```

when that fact has not otherwise been proved.

This prevents CMIS from silently treating binary equivalence as either required
or unnecessary.

## Promotion decision

The timestamp unit may become verified only when every gate is true:

```text
source_identity
sample_integrity
all_samples_within_explicit_tolerance
minimum_sample_count
minimum_distinct_relay_count
temporal_coverage
deployed_binary_equivalence_requirement
```

Only then:

```text
timestamp_unit_verified = true
```

The governance result emits an evidence object compatible with the existing
Oracle V2 freshness policy:

```json
{
  "timestamp_unit": "unix_ms",
  "method": "x1_block_time_correlation",
  "verified": true,
  "provenance": "..."
}
```

Policy and evidence SHA-256 digests are included so later Evidence Receipts can
preserve the exact governance inputs.

## What timestamp-unit verification does not prove

Even a successful timestamp-unit governance decision keeps all of these
separate and false unless independently verified:

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

Timestamp-unit verification therefore authorizes only the interpretation of the
Oracle timestamp field under the accepted governance contract.

It does not authorize Oracle V2 as a current market-price source.

## Test fixtures are not production policy

Deterministic tests use concrete values to exercise exact boundary behavior.

Those values are not:

- production thresholds;
- CMIS recommendations;
- upstream guarantees;
- hidden defaults.

## Next acceptance step

After this mechanism is reviewed and merged, a separate governance decision must
supply the actual production policy values and provenance.

Only then should the accepted live evidence be re-evaluated and, if every gate
passes, `timestamp_unit_verified` may change from false to true.

Freshness/current-price promotion remains a later gate.
