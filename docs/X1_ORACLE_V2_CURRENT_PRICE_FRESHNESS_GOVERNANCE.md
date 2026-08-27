# X1 Oracle V2 Current-Price Freshness Governance

Status: **policy selected / implementation and live evidence pending review**

Trackers: **#277, #296**

Parent provider evaluation: **#272**

Timestamp-unit evidence: **#293 / #294**

Freshness primitives: **#277 / #280**

## Decision

CMIS accepts the following source-specific current-price freshness policy for
read-only Oracle V2 candidate evidence:

```text
policy_id = cmis.x1.oracle_v2.current_price_freshness.v1
max_age_ms = 60000
max_future_skew_ms = 5000
minimum_eligible_slots = 3
```

This policy governs only whether an Oracle V2 relay slot is temporally eligible
to participate in a candidate median. It does not authorize the candidate
median as an authoritative CMIS price.

## Intended meaning of "fresh enough"

For this provider, **current** means that the Oracle timestamp is no more than
one minute behind the CMIS post-read UTC observation clock and no more than
five seconds ahead of that clock.

A timestamp satisfying that time window is only *temporally eligible*. It must
also have a positive price and timestamp and consume the already accepted
Unix-ms timestamp-unit evidence.

For an asset-level candidate median, at least three of the five Oracle V2 relay
slots must be temporally eligible.

## Provenance and rationale

### `max_age_ms = 60000`

This is an explicit CMIS current-price evidence service contract: a price
observation older than one minute is not "current" for this candidate provider.

The one-minute bound was selected as a governance definition **before applying
it to the current live Oracle state**. It is not derived from the ages observed
in #297 and is not chosen to make those observations pass.

The upstream implementation currently documents an approximately ten-second
relay submission loop. That cadence is a compatibility/sanity check only: it
shows that the selected CMIS bound is not inherently tighter than the
provider's documented operating design. The relay cadence is **not** the
provenance used to derive the one-minute value, consistent with #277.

### `max_future_skew_ms = 5000`

This is an explicit CMIS clock-reference contract. A source timestamp may be up
to five seconds ahead of the post-read CMIS UTC clock and remain temporally
eligible. A larger future offset is classified `future` and fails closed.

The five-second budget is an operator-owned clock-skew allowance. It is not
derived from current slot ages or from the previously observed timestamp-to-
block-time differences used to prove the timestamp unit.

### `minimum_eligible_slots = 3`

Oracle V2 stores five relay slots per asset. Requiring three eligible slots
establishes a strict majority quorum.

This quorum is same-system redundancy only. The five relay slots must never be
counted as five independent market sources. The reviewed Oracle architecture
uses a common upstream aggregated price feed, so relay quorum and source
independence are distinct facts.

## Deterministic boundaries

Given verified Unix-ms semantics and the CMIS post-read observation clock:

```text
future_offset_ms > 5000
    => future / ineligible

future_offset_ms <= 5000
    => effective age = 0 for max-age comparison

age_ms > 60000
    => stale / ineligible

age_ms <= 60000
    => fresh / temporally eligible
```

The exact boundaries are inclusive:

- age exactly 60,000 ms is eligible;
- age 60,001 ms is stale;
- future offset exactly 5,000 ms may be eligible;
- future offset 5,001 ms is future.

At asset level:

```text
eligible_slot_count >= 3
    => exact candidate median may be constructed

eligible_slot_count in {1, 2}
    => partial / no median

eligible_slot_count = 0
    => unavailable / no median
```

The median is calculated from eligible prices only. No stale, future, invalid,
missing, or zero slot may enter the median. No zero-fill or stale substitution
is allowed.

## Evidence and live-run interpretation

A live read-only run under this policy may legitimately show every current
Oracle slot as stale. That outcome is not a policy failure.

The policy decision is valid independently of the current provider state.
Live evidence answers a separate question: which currently observed slots
satisfy the already-selected contract?

Therefore CI must not require live data to pass the threshold. It must require
the policy to be complete, classify every live slot deterministically, verify
eligible-slot counts, and verify any candidate median from eligible slots only.

## Price correctness and source independence remain separate

Passing freshness does not establish:

```text
price_correctness_verified
source_independence_verified
current_price_use_authorized
cmis_provider_promoted
public_service_promoted
scout_reliance_promoted
execution_authorized
```

All remain false at this gate.

The next price-evidence step is a same-fact cross-check against an already
accepted CMIS X1 price source. That comparison must bind exact asset identity,
price unit/decimals, and compatible observation time. If the Oracle V2
observation is stale relative to this policy, the comparison must not be
promoted into current-price correctness evidence.

Source independence must be reviewed separately from numerical agreement.
Five Oracle relays are not five independent sources.

## Three-axis review requirement

Before merge, this change requires the repository's independent three-axis
review:

1. **Spec / contract fidelity** — values, boundaries, fail-closed semantics,
   eligible-only median construction, and non-promotion states match #277,
   #296, and #272.
2. **Code / architecture quality** — policy remains explicit and centralized,
   live collection remains read-only, and no provider-specific policy leaks
   into unrelated shared CMIS behavior.
3. **Authority / evidence safety** — freshness is not upgraded into price
   correctness, source independence, provider promotion, Scout reliance, or
   execution authority.

## Promotion boundary

This policy resolves only the Oracle V2 freshness-governance decision.

Provider promotion still requires separate accepted evidence for:

```text
price_correctness_verified
source_independence_verified
cmis_provider_promoted
scout_reliance_promoted
```

No signing, submission, transaction construction, broadcasting, custody,
trading, bridge transfer, or execution behavior is introduced.
