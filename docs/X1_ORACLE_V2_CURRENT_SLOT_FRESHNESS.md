# X1 Oracle V2 Current-Slot Freshness Evaluation

Status: **timestamp unit verified / freshness policy not yet selected**

Tracker: **#296**

Timestamp-unit promotion: **#293 / #294**

Freshness primitives: **#277 / #280**

Parent Oracle V2 evaluation: **#272**

## Purpose

This layer applies the accepted Oracle V2 Unix-ms timestamp semantics to the
current 6-asset × 5-relay on-chain state.

It does not choose production freshness thresholds.

CMIS currently has no accepted production values for:

```text
max_age_ms
max_future_skew_ms
minimum_eligible_slots
```

Therefore the default live run must fail closed.

## Verified input

Downstream freshness analysis consumes the reusable timestamp-unit evidence
promoted in #293/#294:

```text
timestamp_unit = unix_ms
method = x1_block_time_correlation
verified = true
```

Its provenance is pinned to the accepted promotion merge, workflow artifact,
policy digest, and raw-evidence digest.

The freshness layer does not reconstruct or weaken that decision.

## Current-state source

The evaluator reuses the existing read-only Oracle V2 structural probe and
requires:

```text
status = verified_contract_shape
```

before evaluating any current slot.

The structural probe verifies the expected program/state, account owner,
executable flags, state layout, discriminator, decimals, bump, and exact
6 × 5 price/timestamp layout.

## Runtime clock

The CLI does not accept an `observed_at_ms` argument.

The runtime injects the current timezone-aware UTC clock internally and derives:

```text
observed_at_ms = UTC Unix milliseconds
```

The pure evaluation function accepts a timezone-aware injected datetime only so
tests can be deterministic.

A naive datetime is rejected.

## Raw current-slot ages

Once Unix-ms semantics are verified, CMIS may deterministically calculate:

```text
signed_age_ms = observed_at_ms - timestamp_raw
```

for every positive timestamp.

If `signed_age_ms < 0`, the evaluator also preserves:

```text
future_offset_ms = -signed_age_ms
```

These are raw time observations. They are not themselves freshness decisions.

## Explicit policy application

An optional policy JSON may provide:

```json
{
  "max_age_ms": "<positive integer>",
  "max_age_provenance": "<required>",
  "max_future_skew_ms": "<non-negative integer>",
  "future_skew_provenance": "<required>",
  "minimum_eligible_slots": "<integer 1..5>",
  "minimum_eligible_slots_provenance": "<required>"
}
```

No numerical defaults exist.

If any required field or provenance is missing:

```text
freshness_policy_complete = false
freshness_policy_applied = false
freshness_verified = false
status = unavailable
reason = freshness_policy_incomplete
```

All slot classifications remain ineligible.

## Deterministic slot classification

When a complete explicit policy is supplied, the existing accepted classifier
applies these boundaries:

```text
price_raw <= 0 or timestamp_raw <= 0
    => invalid

future_offset_ms > max_future_skew_ms
    => future

future_offset_ms <= max_future_skew_ms
    => effective age 0

effective_age_ms > max_age_ms
    => stale

effective_age_ms <= max_age_ms
    => fresh
```

Exact boundaries are inclusive:

- age exactly equal to `max_age_ms` is fresh;
- future offset exactly equal to `max_future_skew_ms` may be fresh.

## Per-asset aggregation

Each asset is evaluated independently across its five relay slots.

Only slots classified `fresh` are eligible for the candidate median.

The candidate median is calculated only when:

```text
eligible_slot_count >= minimum_eligible_slots
```

The median calculation remains exact integer/rational arithmetic before decimal
normalization.

## Authority boundary

Even if a complete freshness policy later produces fresh slots and an eligible
candidate median, this layer always keeps:

```text
current_price_use_authorized = false
cmis_provider_promoted = false
public_service_promoted = false
scout_reliance_promoted = false
source_independence_verified = false
price_correctness_verified = false
execution_authorized = false
```

Freshness is only time validity.

It does not prove that an Oracle price is correct, independent, or suitable as
an authoritative CMIS current price.

## Live evidence step

The branch-scoped workflow intentionally runs with **no freshness policy**.

It must demonstrate:

1. timestamp-unit evidence is accepted;
2. the current Oracle state still passes structural verification;
3. all 30 slot ages can be calculated;
4. the incomplete policy fails closed;
5. no slot becomes price eligible;
6. no asset median is promoted;
7. all downstream authority flags remain false.

The live age range from that workflow should be recorded after CI succeeds.

## Next governance decision

After the live raw-age evidence is captured, the next explicit decision is to
select and justify:

- `max_age_ms`;
- `max_future_skew_ms`;
- `minimum_eligible_slots`.

Those values must come with provenance and must not be inferred merely from the
current age observations.
