# X1 Oracle V2 Timestamp-Unit and Freshness Policy

Status: **accepted deterministic policy boundary / no provider promotion**

Tracker: GitHub Issue #277

Parent Oracle V2 evaluation: #272

Structural verification baseline: #274

## Decision

CMIS does **not** define a hidden production freshness threshold for Oracle V2.

The deterministic policy engine validates and applies explicit policy values, but the deployment/operator owns the numerical choices and their provenance.

The required policy fields are:

```json
{
  "max_age_ms": "<explicit positive integer>",
  "max_age_provenance": "<why this value was chosen>",
  "max_future_skew_ms": "<explicit non-negative integer>",
  "future_skew_provenance": "<why this value was chosen>",
  "minimum_eligible_slots": "<explicit integer 1..5>",
  "minimum_eligible_slots_provenance": "<why this value was chosen>"
}
```

There are no CMIS defaults for these values.

Numerical values used in unit tests are fixtures only and must not be promoted into production configuration.

## Why there is no CMIS default

The reviewed Oracle V2 source defines a relay loop and stores signed timestamps, but it does not publish a CMIS-grade maximum-age guarantee, allowable clock-skew guarantee, or minimum live relay count that can be safely converted into a universal production policy.

The on-chain program requires only:

- `timestamp > 0`;
- `price >= 0`.

It does not enforce:

- maximum timestamp age;
- monotonic timestamp progression;
- a maximum future offset;
- a minimum count of currently updated relay slots.

CMIS therefore must not manufacture these limits.

## Timestamp-unit verification

The live state layout contains raw signed integer timestamps. Structural verification alone does not prove their deployed unit.

The accepted deterministic verification method introduced by this policy is:

```text
x1_block_time_correlation
```

For a candidate raw timestamp and a verified X1 transaction/block time:

```text
block_time_ms = block_time_seconds * 1000
difference_ms = abs(timestamp_raw - block_time_ms)
verified = difference_ms <= explicit_max_difference_ms
```

The correlation tolerance is itself explicit input and must carry provenance. CMIS defines no default correlation tolerance.

The result is timestamp-unit evidence only. It does not prove:

- price freshness;
- price correctness;
- upstream Pyth/CEX provenance;
- independent market-source agreement.

Before later Oracle V2 provider promotion, the evidence review must determine how many successful correlation samples are sufficient to treat the deployed timestamp unit as verified. This policy module does not silently choose that promotion threshold.

## Authoritative observation clock

Freshness classification uses an internally supplied CMIS UTC observation time expressed as Unix milliseconds.

The deterministic policy function accepts `observed_at_ms` as an input so tests are reproducible. A future runtime/provider integration must inject this value from CMIS's internal clock. Request-level callers must not be allowed to replace the authoritative evaluation clock.

If the observation time is missing or invalid, the slot fails closed as `missing` or `invalid`.

## Slot classifications

The only policy classifications are:

- `fresh`
- `stale`
- `future`
- `invalid`
- `missing`
- `unit_unverified`

Classification order is deterministic.

### missing

Used when required slot or observation values are absent.

### invalid

Used when:

- price/timestamp/observation values are malformed;
- price is zero or negative;
- timestamp is zero or negative;
- timestamp unit is verified but the freshness policy is incomplete.

### unit_unverified

Used when the slot is structurally valid but accepted timestamp-unit evidence is unavailable.

A source-code comment, a relay-loop interval, or a positive timestamp is not sufficient by itself.

### future

For verified Unix-ms timestamps:

```text
future_offset_ms = timestamp_raw - observed_at_ms
```

A slot is `future` when:

```text
future_offset_ms > max_future_skew_ms
```

The future-skew threshold has no default.

A timestamp inside the explicitly accepted future-skew window is permitted to continue through freshness classification. Its effective age for maximum-age comparison is zero, while the signed age/future offset remains preserved in evidence.

### stale

For non-future timestamps:

```text
age_ms = observed_at_ms - timestamp_raw
```

A slot is `stale` when:

```text
age_ms > max_age_ms
```

### fresh

A slot is `fresh` only when all of the following are true:

- price is positive;
- timestamp is positive;
- timestamp unit evidence is accepted;
- the complete explicit freshness policy is present;
- the timestamp does not exceed the explicit future-skew limit;
- effective age is less than or equal to the explicit maximum age.

Only `fresh` slots may set:

```text
cmis_price_eligible = true
```

## Boundary semantics

The maximum-age boundary is inclusive:

```text
age_ms <= max_age_ms  -> fresh
age_ms >  max_age_ms  -> stale
```

The future-skew boundary is also inclusive:

```text
future_offset_ms <= max_future_skew_ms -> may continue
future_offset_ms >  max_future_skew_ms -> future
```

These comparisons are part of the deterministic contract.

## Aggregation

The candidate Oracle V2 median uses **only** slots classified `fresh`.

No:

- zero-fill;
- stale substitution;
- future-slot substitution;
- unit-unverified substitution;
- malformed-slot substitution.

The minimum eligible-slot count is explicit policy in `[1, 5]`.

Aggregation status is:

- `unavailable` when zero eligible slots remain or the minimum-slot policy is unconfigured;
- `partial` when at least one slot is eligible but fewer than the configured minimum remain;
- `ok` when the configured minimum is satisfied.

A median is emitted only for `ok`.

The raw median is exact:

- odd count: middle raw integer;
- even count: exact sum of the two middle integers divided by 2.

No floating-point rounding is used for median selection.

## Evidence contract

Each slot classification preserves:

- raw price;
- raw timestamp;
- CMIS observation time;
- timestamp-unit evidence method and provenance;
- maximum-age value and provenance;
- future-skew value and provenance;
- signed age;
- future offset when applicable;
- classification;
- eligibility;
- reason.

Aggregation preserves:

- all slot classifications;
- classification counts;
- eligible-slot count;
- explicit minimum eligible-slot count;
- exact raw median numerator/denominator;
- normalized price string;
- policy and timestamp-unit evidence.

## Source-independence boundary

Five Oracle V2 relay slots are not five independent market sources.

The reviewed relays consume a common aggregated price-feed server. Freshness-qualified relay agreement is therefore same-system redundancy evidence only.

This remains explicit:

```text
source_independence_verified = false
```

unless a separate accepted evidence path proves otherwise.

## Promotion boundary

Even when this policy can classify slots as `fresh` and calculate a candidate median, Issue #277 does not promote Oracle V2 into CMIS current-price authority.

The policy result remains:

```text
current_price_use_authorized = false
cmis_provider_promoted = false
public_service_promoted = false
scout_reliance_promoted = false
execution_authorized = false
```

A later evidence/promotion gate must separately establish:

1. sufficient deployed timestamp-unit evidence;
2. deployment-owned production policy values and provenance;
3. live fresh-slot behavior;
4. same-fact identity/unit/time comparison semantics against accepted X1 evidence;
5. Evidence Receipt / Proof Score integration;
6. normal CI and independent review.

## Test fixtures are not policy

Tests use concrete numerical values only to verify deterministic boundary behavior.

Those values are not:

- production recommendations;
- accepted market assumptions;
- hidden runtime defaults.

## Safety boundary

This policy is read-only analysis.

It introduces no:

- signing;
- OpenBao integration;
- oracle submission;
- transaction construction;
- broadcasting;
- custody;
- swaps;
- autonomous execution;
- execution authorization.
