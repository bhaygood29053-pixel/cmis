# CMIS Regulatory Evidence v1

Issue: #536

Contract: `regulatory_evidence/v1`

## Purpose

This foundation gives CMIS a deterministic way to represent regulatory evidence
without turning CMIS into a legal opinion engine.

The first framework is the U.S. GENIUS Act, Public Law 119-27, approved
2025-07-18. The v1 model intentionally separates:

1. static law identity and status;
2. regulator/rulemaking provenance;
3. current asset and issuer identity evidence;
4. native/bridged representation relationships;
5. applicability state;
6. legal interpretation, which remains outside CMIS factual authority.

## GENIUS Act effective-date rule

The v1 fixture records the statutory effective-date form as the earlier of:

- 2027-01-18; or
- 120 days after the primary federal payment stablecoin regulators issue final
  implementing regulations.

The record must not silently convert proposed rulemaking into a final/effective
rule.

## Authority

Accepted source classes are intentionally narrow:

- `primary_law`
- `primary_regulator`

Initial source identities:

- GovInfo / U.S. Government Publishing Office — Public Law 119-27
- U.S. Department of the Treasury — GENIUS Act implementation/rulemaking material

A URL being present is not itself proof that every downstream asset claim is
verified. Current issuer, license, token, bridge, custody, and redemption facts
require their own accepted evidence.

## Applicability vocabulary

`APPLICABLE | NOT_APPLICABLE | UNKNOWN | INSUFFICIENT_EVIDENCE`

v1 does not emit `COMPLIANT` or `NON_COMPLIANT`.

## Native versus bridged stablecoins

The first fixtures intentionally distinguish:

- USDC — modeled as a native stablecoin identity fixture;
- USDC.X — modeled as a bridged representation of USDC.

The USDC.X fixture preserves `bridge_dependency=true` and
`custody_dependency=true`. Evidence about the underlying USDC must not erase
those additional dependencies.

## Promotion state

This is an internal contract foundation only:

```text
read_only = true
public_service_promoted = false
scout_reliance_promoted = false
compliance_conclusion_authorized = false
execution_authorized = false
```

Runtime ingestion, freshness policy, capability-manifest promotion, and Scout
reliance require separate acceptance.
