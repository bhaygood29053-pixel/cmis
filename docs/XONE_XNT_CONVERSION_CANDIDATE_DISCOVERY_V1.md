# XONE/XNT Conversion Candidate Discovery v1

Status: **ACCEPTED INTERNAL CONTRACT** via Issue #589 / PR #590. XONE XNT Conversion Candidate Discovery run #2 passed deterministic and live jobs at head `72b341c823af861e85b43cb12912efe148850f35`, Liquidity Scout Tests run #1766 passed, and PR #590 merged as `d34e83076b3a1cfd4dd5709c6c790aa89034bf6f`.

Contract:

`xone_xnt_conversion_candidate_discovery/v1`

## Purpose

Convert exact Ethereum addresses already present inside bounded XONE/XNT web claims into reviewable candidates. This contract does not discover arbitrary Ethereum addresses and does not treat a source-reported address as a verified XONE→XNT converter.

Accepted upstream foundations:

- `xone_xnt_conversion_scraper/v1`;
- `ethereum_xone_identity/v1`;
- `ethereum_xone_event_observer/v1`;
- `ethereum_xone_migration_sink_semantics/v1`.

## Candidate creation rule

An address becomes a candidate only when:

1. it is an exact 20-byte Ethereum-style address already extracted from a bounded XONE/XNT claim;
2. the claim contains conversion/migration/redeem/burn/contract or closely related context;
3. the source claim retains its exact claim ID, source, URL, observation time, excerpt and topics.

The candidate is then deduplicated by exact lowercase Ethereum address while all supporting source claims are preserved.

## Known identities are excluded from sink inference

Two exact addresses are specially classified:

- XONE token contract `0x4DCDa2274899d9BbA3Bb6f5A852C107Dd6E4fE1c` → `exact_xone_token_contract`;
- XONE deployer `0xc73fc08c931efe3fce850c09278472e8a81c2e05` → `exact_xone_deployer`.

Neither is eligible to become a migration sink merely because it appears near XONE/XNT conversion language.

## Relevance score

A deterministic relevance score helps order manual/on-chain review. It uses only bounded claim context such as:

- conversion;
- contract;
- burn;
- claim;
- cross-chain;
- lockup/vesting;
- presence of both XONE and XNT;
- the exact address in the excerpt.

The score is triage metadata only:

`relevance_score != verification`

## Ethereum qualification

An otherwise-unverified candidate may be checked read-only on Ethereum for:

- Ethereum mainnet chain ID;
- current runtime bytecode;
- `IBurnRedeemable` ERC165 support through the accepted migration-sink semantics contract.

Possible technical outcomes include:

- `no_runtime_bytecode`;
- `contract_without_iburnredeemable_support`;
- `iburnredeemable_compatible_contract`;
- `contract_interface_unverified`.

Even the strongest technical outcome means only that a contract is compatible with the XONE burn-redeemer callback interface.

It does **not** prove:

- XONE→XNT conversion;
- migration sink;
- lock/claim contract;
- XNT issuer;
- conversion ratio;
- eligibility;
- vesting/unlock;
- Ethereum→X1 event correlation.

## Zero-candidate semantics

A live scrape with zero candidates is a valid result.

It means only:

> no exact Ethereum address candidates were found in the bounded pages and claims inspected by this run.

It does not mean no conversion contract exists.

## Accepted live gate

Run #2 executed the acceptance workflow against the bounded X1 Report sitemap corpus. It inspected 13 ranked pages, produced 0 XONE/XNT candidate claims and therefore 0 exact Ethereum address candidates. All inspected pages were available in that run. The evidence artifact digest is `sha256:68f9eb35c2bb2f77ba68f2f2c65bf7f4905e1cbbba5f9b764a88f68659d4477d`.

The accepted interpretation is deliberately narrow:

```text
bounded_pages_attempted = 13
candidate_claim_count = 0
candidate_count = 0
migration_sink_identified = false
xone_xnt_conversion_verified = false
```

This does **not** prove that no XONE→XNT conversion contract exists. It proves only that the exact-address candidate extractor found none in the 13 ranked X1 Report pages inspected by that live run.

The acceptance workflow:

1. scrapes up to 30 ranked X1 Report sitemap pages with the dedicated XONE/XNT scraper;
2. builds up to 10 exact-address candidates;
3. excludes known XONE identities from sink qualification;
4. read-only qualifies other candidates across multiple public Ethereum RPC transports where possible;
5. fails closed if multiple successful RPC observations materially disagree;
6. preserves source/RPC availability failures;
7. permits a PASS with zero candidates or technically unqualified candidates.

## Authority boundary

Every candidate and qualification preserves:

```text
candidate_role_verified = false
migration_sink_identified = false
lock_or_migration_verified = false
xone_xnt_conversion_verified = false
xnt_issuance_verified = false
cross_chain_correlation_verified = false
public_service_promoted = false
scout_reliance_promoted = false
execution_authorized = false
```

## Next slice

Independently identify and verify the X1-side XNT allocation, issuance, vesting or claim mechanism that could service XONE holders. This can proceed even though the bounded X1 Report corpus produced no Ethereum contract candidate. Conversion still cannot be verified until the exact Ethereum-side role and exact X1-side mechanism are independently bound by accepted evidence.
