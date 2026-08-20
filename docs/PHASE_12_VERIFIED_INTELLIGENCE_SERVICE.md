# CMIS Phase 12 — First Verified Intelligence Service Contract

## Status

Accepted-candidate contract/store layer for Issue #237. **Not yet advertised by the canonical CMIS gateway or capability manifest.**

## Purpose

Phase 11 established deterministic Verified Intelligence foundations, but those foundation objects deliberately carry:

- `public_service_promoted = false`
- `scout_reliance_promoted = false`
- `execution_authorized = false`

The first Phase 12 slice does not promote the whole foundation. It defines exactly one bounded service contract around:

`top_account_concentration_change`

The service name/version is:

`concentration_change_intelligence/v1`

Initial chain scope is `x1` only.

## Why the first draft was narrowed

A content-addressed Evidence Receipt proves deterministic integrity, not who supplied it. Therefore a Scout/caller must not be allowed to submit a complete `intelligence_evidence` bundle and obtain promotion merely because the bundle can be rebuilt exactly.

The public request trust root is instead:

1. exact `chain = x1`;
2. exact `asset_id`;
3. one canonical CMIS-owned `intelligence_evidence_id` (`ie_...`);
4. an internal CMIS resolver/store that returns the already-built canonical bundle.

Caller-supplied conclusions, Evidence Receipts, Proof Scores, or full intelligence bundles are rejected.

## CMIS-owned evidence store

`IntelligenceEvidenceLedger` is an internal SQLite-backed store for the first Phase 12 slice.

It:

- accepts only canonical `top_account_concentration_change` intelligence-evidence bundles;
- reruns the existing Phase 11 deterministic bundle validator before storage;
- stores sanitized canonical JSON keyed by the exact content-addressed `ie_...` id;
- revalidates the bundle again on read;
- is idempotent by evidence id;
- has no public store endpoint.

Persistence ownership is the trust boundary. The content id alone is not authentication.

## Request contract

Conceptual request:

```json
{
  "service": "concentration_change_intelligence",
  "chain": "x1",
  "params": {
    "asset_id": "<exact asset identity>",
    "intelligence_evidence_id": "ie_<sha256>",
    "threshold_policy": {
      "policy_id": "optional-explicit-policy",
      "policy_version": "1.0",
      "absolute_delta_threshold_bps": "100"
    }
  }
}
```

`threshold_policy` is optional. If supplied, it must contain exactly the three named fields. There is no hidden/default threshold.

The dispatcher does not accept:

- `intelligence_evidence`;
- `evidence_receipt`;
- `proof_score`;
- wallet/behavior inputs;
- arbitrary extra parameters.

## Response separation

The service response keeps three layers distinct:

### Facts

`data.facts` is the exact revalidated `cmis_top_account_concentration_change.v1` conclusion. It preserves:

- exact X1 asset/source identity;
- observed top-token-account scope;
- requested top-N and observed count;
- before/after observation times;
- exact rational before/after/delta shares;
- numeric direction;
- the original limitations.

It does **not** convert token accounts into unique holders or beneficial owners.

### Evidence / proof

`data.evidence` preserves:

- the CMIS-owned `intelligence_evidence_id`;
- Evidence Receipt ids;
- exact Proof Score records;
- explicit Evidence Receipt freshness state;
- unresolved evidence fields;
- limitations;
- the nested Phase 11 intelligence-evidence bundle.

Nested Phase 11 objects remain non-promoted. Proof strength remains separate from risk.

Freshness is not inferred from timestamps. If every authoritative receipt explicitly says freshness is verified, the service may report `freshness_verified = true`. Explicit false remains false; missing/unknown remains null. False or unknown freshness yields a partial service result rather than a silent upgrade.

### Optional deterministic policy assessment

When `threshold_policy` is supplied, CMIS applies the already-accepted deterministic concentration-threshold evaluator. The threshold is explicitly caller/policy supplied and versioned.

The output remains a policy observation only:

- `WITHIN_THRESHOLD`;
- `AT_THRESHOLD`;
- `EXCEEDS_THRESHOLD`.

A threshold crossing does not establish whale/insider behavior, accumulation, distribution, manipulation, ownership, or risk.

`risk` remains separate/null in this service.

## Promotion boundary

The contract/store layer is intentionally fail-closed before integration:

```text
public_service_promoted = false
scout_reliance_promoted = false
callable = false
promotion_blocker = canonical_runtime_and_capability_manifest_integration_required
```

The candidate promotion scope is:

`cmis_owned_top_account_concentration_change_evidence_by_id`

A later Issue #237 integration must explicitly:

1. wire the internal ledger/resolver into the canonical CMIS runtime;
2. add exactly this service to the public capability manifest for X1;
3. keep Solana unavailable;
4. prove manifest/runtime service lists do not drift;
5. authorize public/Scout reliance only at that canonical integration boundary;
6. preserve the Phase 11 `intelligence_foundation` non-promotion flags.

Until that step is accepted, this contract does not advertise itself as a supported CMIS service.

## Unsupported scope

This milestone does not promote:

- `top_account_concentration` snapshots as a separate public service;
- wallet activity observations or summaries;
- generic sanitized history observations or historical comparisons;
- holder/beneficial-owner identity;
- whale, insider, bot, accumulator, distributor, market-maker, manipulation, relationship, or intent labels;
- Solana/future-chain intelligence;
- direct provider access from Roberta or Chain Scouts.

## Execution boundary

This service/store layer is read-only. It performs no transaction preparation, simulation as an execution precursor, signing, broadcasting, custody, trading, bridge transfer, autonomous execution, or value movement. `execution_authorized = false` remains mandatory.
