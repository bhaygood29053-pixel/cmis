# CMIS Phase 12 — First Verified Intelligence Service Contract

## Status

Promotion candidate for Issue #237.

The accepted contract/store prerequisite from PR #238 remains narrow and fail-closed. This integration promotes exactly one public X1 service through the canonical CMIS runtime and capability manifest:

`concentration_change_intelligence/v1`

Accepted conclusion type:

`top_account_concentration_change`

CMIS capability contract version: `1.9.0`.

## Purpose

Phase 11 established deterministic Verified Intelligence foundations while deliberately keeping the whole `intelligence_foundation` outside public Scout reliance.

Phase 12 does **not** promote that whole foundation. It promotes one read-only service around already-built, CMIS-owned concentration-change evidence.

The architecture remains:

```text
Roberta
  -> X1 Scout
    -> CMIS concentration_change_intelligence
      -> CMIS-owned intelligence evidence ledger
        -> exact Phase 11 Evidence Receipts + Proof Scores
```

Roberta or a Chain Scout never supplies trusted proof objects and never calls a provider directly.

## Trust root

A content-addressed Evidence Receipt proves deterministic integrity, not who supplied it. Therefore the public request never accepts a conclusion, full `intelligence_evidence` bundle, Evidence Receipt, or Proof Score as a trusted input.

The request binds only:

1. `chain = x1`;
2. exact `asset_id`;
3. canonical CMIS-owned `intelligence_evidence_id` (`ie_...`);
4. optional explicit/versioned concentration-threshold policy.

The canonical runtime owns `IntelligenceEvidenceLedger`. The ledger:

- stores only canonical X1 `top_account_concentration_change` bundles;
- reruns deterministic Phase 11 validation before persistence;
- stores sanitized canonical JSON keyed by the exact `ie_...` id;
- reruns validation on read;
- is idempotent by content id;
- has no public store endpoint.

The runtime exposes an internal `store_intelligence_evidence(...)` method for trusted CMIS producers. This method is not a CMIS HTTP service and does not authorize provider or Scout writes.

## Public request

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

`threshold_policy` is optional and has no hidden/default threshold.

Caller-supplied proof objects, wallet/behavior inputs, and arbitrary extra parameters fail closed.

## Response separation

### Facts

`data.facts` is the exact revalidated `cmis_top_account_concentration_change.v1` conclusion. It preserves exact chain/asset/source identity, observed top-token-account scope, requested top-N, observation count, before/after times, exact share/delta values, direction, and limitations.

It does not convert token accounts into unique holders or beneficial owners.

### Evidence and proof

`data.evidence` preserves:

- CMIS-owned `intelligence_evidence_id`;
- authoritative Evidence Receipt ids;
- exact Proof Score records;
- explicit receipt freshness state;
- unresolved evidence fields;
- limitations;
- the nested Phase 11 intelligence-evidence bundle.

The runtime's normal `EvidenceQualityMixin` also adds a fresh top-level Evidence Receipt and Proof Score to the completed public service envelope. These post-processing records cannot rewrite service facts, status, risk, or execution policy.

Proof strength remains separate from risk.

### Freshness / unknown state

Freshness is never inferred from timestamps.

- every authoritative receipt explicitly fresh **and** no unresolved receipt fields -> service may be `ok`;
- explicit stale/unverified freshness -> `partial`;
- unknown freshness -> `partial`;
- any unresolved authoritative receipt field -> `partial`.

Unknown state is never zero-filled or upgraded.

### Optional deterministic policy

When `threshold_policy` is supplied, CMIS uses the accepted deterministic concentration-threshold evaluator.

Possible policy observations:

- `WITHIN_THRESHOLD`;
- `AT_THRESHOLD`;
- `EXCEEDS_THRESHOLD`.

This output is policy, not a market fact and not risk. It does not establish whale, insider, bot, accumulator, distributor, market-maker, manipulation, ownership, relationship, or intent.

`risk` remains null in this service.

## Capability-manifest promotion

CMIS `1.9.0` classifies the new service explicitly for every known chain.

### X1

- `state = bounded`
- `callable = true`
- `read_only = true`
- `public_service_promoted = true`
- `scout_reliance_promoted = true`
- accepted conclusion type is only `top_account_concentration_change`
- `execution_authorized = false`

### Solana

- `state = unavailable`
- `callable = false`
- `public_service_promoted = false`
- `scout_reliance_promoted = false`
- `execution_authorized = false`

The existing capability validator still compares the runtime service list against every known-chain service classification at startup/import time. A new runtime service cannot silently ship without a manifest entry.

## Phase 11 foundation remains unpromoted

The top-level `intelligence_foundation` remains unchanged:

```text
read_only = true
public_service_promoted = false
scout_reliance_promoted = false
promotion_rule = new_accepted_public_service_contract_required
```

Its broader foundation primitives remain non-public/non-automatic, including wallet activity, sanitized history, and raw concentration snapshots.

## Unsupported scope

This milestone does not promote:

- a generic `verified_intelligence` service;
- public intelligence-evidence storage/upload;
- top-account concentration snapshots as a separate service;
- wallet activity observations/summaries;
- generic sanitized history or historical comparisons;
- holder/beneficial-owner identity;
- behavioral or intent labels;
- Solana/future-chain intelligence;
- direct provider access from Roberta or Chain Scouts.

## Execution boundary

This service is read-only. It performs no transaction preparation, simulation as an execution precursor, signing, broadcasting, custody, trading, bridge transfer, autonomous execution, or value movement. `execution_authorized = false` remains mandatory.
