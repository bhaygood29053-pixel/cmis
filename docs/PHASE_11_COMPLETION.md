# CMIS Phase 11 Completion

**Status:** COMPLETE  
**Completed:** 2026-08-18  
**Tracker:** GitHub Issue #171  
**Accepted CMIS contract:** `1.8.0`

## Scope

Phase 11 established a **read-only Verified Intelligence foundation** on top of the accepted CMIS evidence, verification, capability, and historical-storage contracts.

The phase deliberately stops at deterministic, auditable intelligence primitives. It does not authorize behavioral labels, ownership inference, execution, or automatic downstream reliance on new intelligence fields.

## Accepted priorities

### Priority 1 — Top-account concentration primitives

Accepted in PR #170, merge `33ed6d26e37e1a87dc96081bbdec4e928c09bc57`.

The accepted contract:

- uses explicit observed top-token-account sets and independently supplied total supply;
- preserves exact raw numerator/denominator evidence;
- rejects missing positive-supply observations instead of converting them into zero concentration;
- requires compatible scope for change comparisons;
- requires verified identity before concentration change becomes an observed fact;
- never promotes token-account concentration into holder, wallet, beneficial-owner, whale, insider, manipulation, or intent claims.

Validation: Liquidity Scout Tests #517 / `32135843269` passed on exact tested head `62c4ff763dfdc5385b2de8dc7d177d11eeda5520`.

### Priority 2 — Wallet activity facts before labels

Accepted in PR #172, merge `df800f12f9fc241ff2f4d37f9d989f6c1e6f8085`.

The accepted contract supports neutral verified facts including:

- token-account balance change;
- transfer IN/OUT when direction and asset identity are verified;
- BUY/SELL when trade direction is independently verified;
- LP add/remove when LP semantics are verified;
- deployer-originated transfer when deployer identity is independently established;
- first/last observed activity, bounded windows, transaction counts, and verified volume with explicit units.

Missing amounts remain unknown. Observations are content-addressed and revalidated before aggregation. No wallet ownership or behavioral classification is inferred.

Validation: Liquidity Scout Tests #521 / `32136624819` passed on exact tested head `355f0eabc8a93e0a163b09990be86f5473504e5e`.

### Priority 3 — Historical storage for intelligence primitives

Accepted in PR #176, merge `14f89aa85242156f17724519dc5512a1640bdfd2`.

The accepted history contract:

- persists sanitized concentration, wallet activity, liquidity, supply, price, and activity observations;
- preserves source, scope, observation time, slot, and proof metadata;
- compares only compatible chain/category/subject/metric/unit/scope/source/verification-method series;
- orders history by canonical observation time rather than database insertion time;
- keeps sparse samples distinct from continuous or archival coverage;
- performs no interpolation and no inferred or zero-filled missing observations;
- fails closed on same-time ambiguity and tampered content-addressed records.

Validation: Liquidity Scout Tests #531 / `32137317589` passed on exact tested head `1b724d0b3bbb36dba8451d7c6e1ddd14d4706257`.

### Priority 4 — Evidence integration

Accepted in PR #177, merge `092ba82cce371afe51a76c24474a7990b1c72ec8`.

The accepted evidence-integration contract:

- attaches exact CMIS Evidence Receipts and recomputed Proof Scores to material Phase 11 conclusions;
- revalidates deterministic conclusions before evidence binding;
- recomputes content-addressed Evidence Receipt IDs;
- recomputes Proof Scores from the receipt and requires an exact match;
- requires receipt chain/source/asset coverage to match the conclusion;
- rejects duplicate or tampered evidence;
- preserves provider-reported observations separately from verifier observations;
- content-addresses conclusion fingerprints and intelligence-evidence bundles;
- keeps proof strength separate from risk and behavioral interpretation;
- keeps sparse historical conclusions explicitly non-archival and non-continuous.

The CMIS capability manifest now advertises a read-only `intelligence_foundation` boundary under contract `1.8.0`.

Validation: Liquidity Scout Tests #537 / `32138861669` passed on exact tested head `4623caab66909b9594a713feba2d88516a4d1078` using the standard workflow before merge.

## Accepted foundation after Phase 11

CMIS now has bounded deterministic foundations for:

- exact top-account concentration observations and numeric changes;
- verified wallet-activity facts without behavioral labels;
- sanitized sparse historical intelligence storage and comparison;
- evidence-bound conclusions with content-addressed Evidence Receipts and recomputed Proof Scores.

These primitives are discoverable as a read-only intelligence foundation, but they are **not** automatically promoted into new public CMIS services or downstream Scout dependencies.

## Explicitly not promoted or authorized

Phase 11 does **not** authorize:

- public HTTP services for the new intelligence primitives;
- automatic downstream Scout reliance on the new intelligence primitives;
- whale, insider, bot, market-maker, accumulator, distributor, manipulation, or behavioral-intent labels;
- wallet ownership or beneficial-owner inference;
- relationship-graph ownership claims;
- predictive manipulation or scam accusations;
- transaction construction;
- signing or broadcasting;
- custody;
- bridge transfer;
- trading or autonomous execution;
- autonomous value movement.

Any future public-service exposure or Scout reliance on Phase 11 intelligence requires a new accepted service contract and its own deterministic acceptance gates.

## Acceptance record

| Priority | PR | Merge | Exact-head CI |
|---|---:|---|---|
| Top-account concentration | #170 | `33ed6d26e37e1a87dc96081bbdec4e928c09bc57` | #517 / `32135843269` |
| Wallet activity facts | #172 | `df800f12f9fc241ff2f4d37f9d989f6c1e6f8085` | #521 / `32136624819` |
| Historical intelligence storage | #176 | `14f89aa85242156f17724519dc5512a1640bdfd2` | #531 / `32137317589` |
| Evidence integration | #177 | `092ba82cce371afe51a76c24474a7990b1c72ec8` | #537 / `32138861669` |

GitHub Issue #171 is closed as completed.