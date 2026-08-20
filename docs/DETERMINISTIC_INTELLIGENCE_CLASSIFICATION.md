# Deterministic Intelligence Classification Boundary

## Status

This document defines the first internal classification contract after the Phase 12 read-only intelligence-service promotion.

The contract is intentionally **descriptive, evidence-bound, read-only, and non-promoted**. It establishes how CMIS may turn an already accepted deterministic fact into a versioned classification without turning inference into fact or creating unsupported behavioral, ownership, intent, fraud, manipulation, or risk claims.

Tracking issue: #250.

## First accepted classification

```text
classification_type = top_account_concentration_direction
classification_kind = descriptive
ruleset_id = top_account_concentration_direction/v1
```

Accepted deterministic labels are limited to:

```text
INCREASE  -> CONCENTRATION_INCREASED
DECREASE  -> CONCENTRATION_DECREASED
NO_CHANGE -> CONCENTRATION_UNCHANGED
```

The source fact is the already accepted `top_account_concentration_change` conclusion. The classifier does not accept a caller-supplied label.

## Evidence trust boundary

The classifier accepts an exact canonical CMIS intelligence evidence id and a trusted internal evidence resolver:

```text
ie_<64 lowercase hex>
  -> CMIS internal evidence resolver
  -> deterministic intelligence-evidence revalidation
  -> exact id match
  -> descriptive classification
```

A caller-supplied evidence bundle is not a trust root merely because it is internally self-consistent or content-addressed.

Before classification, CMIS revalidates the complete evidence bundle, including the concentration-change conclusion, Evidence Receipts, deterministic Proof Scores, chain/source/asset coverage, exact rational change, direction, time ordering, and content-addressed identity. Invalid or tampered receipt/proof basis therefore fails before a classification is emitted.

Resolver exceptions preserve only the exception type. Arbitrary resolver text is not reflected because storage/provider failures may eventually contain credential-bearing paths, URLs, or responses.

## Classification output invariants

Every first-slice classification records:

- a content-addressed `icl_...` classification id;
- schema and ruleset identity;
- exact evidence id and conclusion fingerprint;
- chain, asset, source, and concentration scope;
- observed top-account scope metadata;
- exact observation window;
- exact concentration direction and numeric change basis;
- attached Evidence Receipt ids and Proof Score summaries;
- whether independent verification is present in the accepted evidence bundle.

Every classification also preserves these hard boundaries:

```text
risk_interpretation = null
proof_strength_separate_from_risk = true
behavioral_interpretation_added = false
ownership_interpretation_added = false
provider_assertion_promoted = false
public_service_promoted = false
scout_reliance_promoted = false
cmis_promotable = false
execution_authorized = false
```

Proof strength describes evidence quality only. It is neither a risk grade nor a behavioral confidence score.

## Separation from threshold policy

`concentration_threshold` remains a separate explicit-policy contract.

Its statuses:

- `WITHIN_THRESHOLD`
- `AT_THRESHOLD`
- `EXCEEDS_THRESHOLD`

are caller-policy evaluation results, not market facts, behavioral labels, or risk classifications.

The first deterministic descriptive classifier therefore does **not** consume threshold policy, does not use a hidden threshold, and does not map a threshold result to `PASS`, `WARN`, `BLOCK`, HIGH/MEDIUM/LOW risk, or any behavioral conclusion.

## What this contract does not prove

A concentration increase does not prove:

- a whale acted;
- an insider acted;
- accumulation intent;
- bot activity;
- distribution intent;
- market-making activity;
- common ownership;
- manipulation;
- fraud or scam activity;
- beneficial-owner concentration;
- unique-holder concentration;
- market risk severity.

A concentration decrease does not prove the inverse of any of those claims. `CONCENTRATION_UNCHANGED` only means the exact accepted top-account concentration ratio did not change across the validated comparison window.

Those broader claims require separate deterministic evidence and classification contracts before they may be exposed by CMIS or relied on by a Scout.

## Fail-closed boundary

The classifier rejects or fails closed on:

- malformed/non-canonical `ie_...` identity;
- missing trusted resolver or missing stored evidence;
- resolved evidence whose content id does not match the requested id;
- unsupported conclusion types;
- tampered concentration exact ratios or direction;
- invalid Evidence Receipt or Proof Score basis;
- incompatible chain, asset, source/scope, or observation-time semantics;
- attempted replacement of the canonical descriptive label with a behavioral, ownership, intent, scam/fraud, manipulation, or risk label.

No fallback label is guessed.

## Promotion boundary

This module is an internal deterministic foundation only.

It does not add a CMIS public service, does not change `GET /v1/cmis/capabilities`, does not grant Scout reliance, and does not change Roberta behavior. A later promotion requires its own accepted public-service/Scout-reliance contract and capability metadata.

## Execution boundary

No classification result authorizes transaction preparation, simulation-as-execution, signing, broadcasting, custody, trading, bridge transfer, autonomous execution, or value movement.

CMIS remains read-only intelligence at this boundary.
