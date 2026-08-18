# CMIS Phase 11 — Evidence Integration

Status: **read-only evidence-bound intelligence foundation**

This milestone binds accepted Phase 11 deterministic conclusions to CMIS Evidence Receipts and Proof Scores without promoting those conclusions into new public services or automatic Scout inputs.

## Evidence binding

`liquidity_scout/cmis/intelligence_evidence.py` accepts one validated conclusion plus one or more exact evidence bundles:

```text
{
  evidence_receipt: <CMIS Evidence Receipt v1>,
  proof_score: <CMIS Proof Score v1>
}
```

The binder:

- recomputes and verifies each content-addressed Evidence Receipt ID;
- recomputes the exact Proof Score from the receipt and rejects mismatches;
- verifies conclusion chain against every receipt;
- requires receipt source coverage for every deterministic conclusion source;
- requires receipt asset-identity coverage where the conclusion contains an asset identity;
- revalidates the deterministic Phase 11 conclusion before binding evidence;
- preserves reported observations separately from verifier observations;
- creates a content-addressed conclusion fingerprint and intelligence-evidence bundle ID.

## Supported conclusion types

- top-account concentration;
- top-account concentration change;
- wallet activity observation;
- wallet activity summary;
- sanitized history observation;
- observed sparse historical comparison.

Historical evidence binding accepts only an actual `OBSERVED_CHANGE` result. Insufficient, ambiguous, or incompatible comparisons remain explicit states rather than being turned into a conclusion.

## Proof and risk remain separate

Every intelligence evidence bundle states:

```text
proof_strength_separate_from_risk = true
risk_reinterpreted = false
behavioral_interpretation_added = false
provider_assertion_promoted = false
execution_authorized = false
```

A STRONG Proof Score means the accepted evidence categories are strong. It does not mean an asset is safe, a trade should occur, or a behavioral label is justified.

## Provider-reported vs independently verified evidence

The binder preserves the Evidence Receipt source classes separately:

- `source_record`;
- `reported_observation`;
- `verifier_observation`.

Provider-reported data is never silently relabeled as verifier evidence. Whether independent verification is present is recorded separately in the binding metadata.

## Capability boundary

CMIS contract `1.8.0` advertises an `intelligence_foundation` section with bounded read-only primitives for:

- top-account concentration;
- wallet activity facts;
- sanitized intelligence history;
- evidence-bound conclusions.

These primitives are **not** added to `supported_services`. The manifest explicitly states:

```text
public_service_promoted = false
scout_reliance_promoted = false
promotion_rule = new_accepted_public_service_contract_required
```

This lets external consumers discover that the foundation exists without assuming they may call it as a stable HTTP service or use it as an automatic decision input.

## Safety boundary

No whale/insider/bot/market-maker labels, behavioral intent, wallet-ownership inference, transaction construction, signing, broadcasting, custody, bridge transfer, autonomous trading, or value movement are introduced.