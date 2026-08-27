# X1 Oracle V2 Timestamp-Unit Live Evidence — 2026-08-27

Status: **LIVE CORRELATION EVIDENCE COLLECTED / TIMESTAMP UNIT NOT PROMOTED**

Tracker: **#283**

Pull request: **#285**

Parent Oracle V2 evaluation: **#272**

Policy baseline: **#277 / #280**

Structural deployment baseline: **#274**

Pinned upstream source: `jacklevin74/oracle-v2@97177f772689e44ca4eed9bb95be32ffdf0c5e66`

Live workflow run: `33037683674`

Artifact:

- ID: `9632630582`
- name: `x1-oracle-v2-timestamp-evidence-33037683674`
- digest: `sha256:3da246c305ee0225399022f62ad409626da1bd52c0ba13fcc3595a7b42bcae86`

## Result

The read-only X1 history probe successfully collected **25 verified transaction samples from 25 requested history rows**.

Observed aggregate facts:

```text
history_rows = 25
successful_history_rows = 25
transaction_records = 25
decoded_verified_batch_samples = 25

relay_indexes_observed = [1, 2, 3, 4, 5]

candidate_unix_ms_min_difference_ms = 576
candidate_unix_ms_max_difference_ms = 1604

explicit_correlation_policy_configured = false
timestamp_unit_sample_sufficiency_policy_defined = false
timestamp_unit_verified = false
freshness_verified = false
price_correctness_verified = false
source_independence_verified = false
current_price_use_authorized = false
cmis_provider_promoted = false
```

All five relay indexes were represented in the bounded 25-transaction sample.

## Transaction evidence chain

Each accepted sample had to satisfy all of the following:

1. the X1 state-PDA history row reported a successful transaction;
2. `getTransaction(jsonParsed)` returned the same transaction signature and slot;
3. transaction metadata reported no execution error;
4. the expected Oracle V2 program ID was present;
5. the expected Oracle V2 state PDA was the batch instruction state account;
6. instruction data began with the pinned Anchor `batch_submit_prices` discriminator:
   `116224b954f96553`;
7. exact pinned-source Borsh argument shape decoded:
   - relay index;
   - exactly six raw prices;
   - positive raw timestamp;
   - 64-byte signature field;
   - signed-message vector;
8. the signed message parsed exactly as:
   `BATCH:<relay>:<btc>:<eth>:<sol>:<hype>:<zec>:<fartcoin>:<timestamp>`;
9. relay index, six prices, and timestamp in the signed message exactly matched the decoded batch instruction fields;
10. the same transaction contained a preceding Ed25519SigVerify instruction whose decoded signed message exactly matched the batch signed-message vector;
11. the Ed25519 signature hash exactly matched the 64-byte signature argument carried by the batch instruction;
12. the Ed25519 public-key hash exactly matched the current configured Oracle public key read fail-closed from the verified Oracle state account;
13. the transaction block time matched the block time preserved by the history row when present;
14. an additional X1 `getBlockTime(slot)` call returned a verified block time equal to the transaction block time.

A successful sample therefore ties one raw signed Oracle timestamp to one successful X1 batch transaction and its X1 block time under the reviewed transaction-shape contract.

This does **not** establish that the deployed program binary is byte-for-byte equivalent to the pinned upstream source.

It also does not prove historical Oracle-key continuity. The tracer intentionally accepts only transactions signed by the key that is currently configured in the live Oracle state. If the key has rotated, earlier transactions using a prior valid key fail closed rather than being counted as verified evidence.

## Raw timestamp range

The 25 signed raw timestamp integers ranged from:

```text
1774600385807
through
1774600456170
```

The verified X1 block times for the same sampled transactions ranged from:

```text
1774600385
through
1774600455
```

If the signed raw timestamps are interpreted as Unix milliseconds, the sample spans approximately:

- **2026-03-27T08:33:05.807Z**
- through **2026-03-27T08:34:16.170Z**

The corresponding verified block-time range spans approximately:

- **2026-03-27T08:33:05Z**
- through **2026-03-27T08:34:15Z**

These calendar conversions are the candidate Unix-ms interpretation being investigated. They are not promoted as a verified timestamp unit.

## Raw correlation result

For every accepted sample the probe calculated:

```text
candidate_unix_ms_difference_ms =
    abs(timestamp_raw - verified_block_time_seconds * 1000)
```

Across all 25 samples:

```text
minimum difference = 576 ms
maximum difference = 1604 ms
```

This is strong empirical evidence that the raw signed timestamp values are numerically consistent with Unix milliseconds relative to X1 block time.

However, the #277/#280 policy explicitly forbids turning empirical closeness into a verified unit without an accepted numerical correlation tolerance and provenance.

The live CI run supplied **no** such tolerance.

Therefore:

```text
explicit_correlation_policy_configured = false
all_samples_within_explicit_tolerance = null
timestamp_unit_verified = false
```

## Sample-sufficiency boundary

Even if a later explicit tolerance classifies every sampled correlation as passing, #277 intentionally does not define how many successful historical samples are sufficient to promote the deployed timestamp unit.

Therefore this remains false:

```text
timestamp_unit_sample_sufficiency_policy_defined = false
timestamp_unit_verified = false
```

A later acceptance decision must explicitly define both:

1. the maximum accepted timestamp-to-block-time difference and its provenance;
2. the minimum / coverage requirements for timestamp-unit evidence.

Neither value may be inferred from this one live sample set.

## Source-contract boundary

The pinned source labels the batch timestamp argument as Unix milliseconds.

The live transactions also match the pinned source's:

- Anchor instruction discriminator;
- Borsh argument shape;
- six-asset batch message shape;
- relay-index range;
- same-message Ed25519 linkage;
- successful batch-submission log shape.

This is useful source-contract consistency evidence.

It is **not** a deployed-binary equivalence proof:

```text
deployed_binary_source_equivalence_verified = false
```

CMIS must preserve that distinction.

## Authority boundary

This evidence does not establish:

- current Oracle freshness;
- current price correctness;
- upstream Pyth/CEX observations;
- independent source agreement;
- a production freshness threshold;
- a production correlation threshold;
- provider promotion;
- public-service promotion;
- Scout reliance;
- transaction or execution authority.

The accepted state remains:

```text
timestamp_unit_verified = false
freshness_verified = false
price_correctness_verified = false
source_independence_verified = false
current_price_use_authorized = false
cmis_provider_promoted = false
public_service_promoted = false
scout_reliance_promoted = false
execution_authorized = false
```

## Next gate

The next decision is not another live-price read.

It is a deterministic policy/governance decision defining:

1. an explicit timestamp-unit correlation tolerance with provenance;
2. an explicit sample-sufficiency / coverage rule for timestamp-unit verification;
3. whether deployed-binary equivalence is required for promotion or whether the transaction-shape + live behavioral evidence is sufficient under an accepted evidence tier.

Only after those gates are accepted should CMIS re-run the live evidence with the configured policy and consider changing `timestamp_unit_verified`.

No signing, Oracle submission, transaction construction, broadcast, OpenBao integration, custody, or execution path is introduced.
