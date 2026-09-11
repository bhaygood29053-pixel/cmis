# CMIS Evidence Completion v1

Contract: `cmis_evidence_complete_response/v1`

## Purpose

Every normal CMIS service response produced by the protected runtime is evidence-bound before a Chain Scout may rely on it. The protected runtime centrally attaches:

- CMIS Evidence Receipt v1;
- CMIS Proof Score v1;
- CMIS Evidence Completion v1.

The public CMIS HTTP shell separately attaches the accepted top-level response-freshness contract. Chain Scouts preserve all of these fields without recomputation.

This is a system-wide infrastructure rule. Individual services do not need to remember to request Evidence Receipt, Proof Score, proof/risk separation, or the service-scope completion state.

## Completion states

`COMPLETE`
: The returned service scope is usable and the protected evidence binder reports no material unresolved fields or unknown proof categories for that exact scope.

`PARTIAL`
: Useful verified evidence exists, but some evidence is unresolved, conflicting, stale, incomplete, or otherwise unavailable inside the accepted service scope.

`BLOCKED`
: The service result is unavailable, ambiguous, or error-like and the requested judgment must fail closed.

The completion state describes evidence availability. It is not a risk level, Proof Score, trade recommendation, compliance conclusion, or execution permission.

## Required metadata

The protected runtime completion record contains fields equivalent to:

```text
contract_version = cmis_evidence_complete_response/v1
state = COMPLETE | PARTIAL | BLOCKED
primary_service
service_status
evidence_receipt_available
proof_score_available
receipt_freshness_checked
receipt_freshness_verified
verification_status
unresolved_fields
unknown_proof_categories
missing_or_unavailable_evidence
supporting_evidence_checked
risk_separate_from_proof = true
facts_recomputed = false
risk_recomputed = false
status_rewritten = false
execution_authorized = false
```

## System-wide rule

For every service routed through ROBERTA -> Chain Scout -> CMIS:

1. the requested CMIS service owns its deterministic facts and any internal supporting-service/provider composition;
2. the protected CMIS runtime attaches Evidence Receipt and Proof Score after the service decision;
3. the same protected post-processing attaches Evidence Completion v1;
4. the public shell attaches response freshness;
5. the Chain Scout preserves these fields and explicitly exposes missing/unavailable evidence;
6. ROBERTA explains the result but does not manufacture a missing fact or strengthen the completion state.

A composite service may call other accepted CMIS services internally when its contract requires them. Evidence completion does **not** mean every CMIS service is called for every user question. It means every returned service result identifies what was verified and what remains unavailable within its bounded scope.

## Pre-trade example

A pre-trade result may legitimately be `PARTIAL` when verified identity, current market evidence, liquidity, trade-size analysis, freshness, Evidence Receipt, and Proof Score are present but verified route quality, expected slippage, fees, or transaction simulation are unavailable.

The unavailable execution fields must remain explicit. They are never converted to zero and ROBERTA must not infer them.

## Safety

Evidence completion never authorizes transaction construction, signing, broadcasting, custody, swaps, bridge transfers, autonomous trading, or value movement.

`execution_authorized=false` remains mandatory.
