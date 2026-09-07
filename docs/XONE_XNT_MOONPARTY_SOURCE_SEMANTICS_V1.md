# XONE/XNT MoonParty Source Semantics v1

Status: **IMPLEMENTATION FOR ISSUE #598 — NOT ACCEPTED UNTIL DETERMINISTIC + LIVE PINNED-SOURCE GATES PASS AND PR MERGES**

Contract:

`xone_xnt_moonparty_source_semantics/v1`

## Why this slice exists

The authoritative FairCrypto repositories expose a substantially stronger XONE/XNT lead than the previously searched public web corpus.

Pinned FairCrypto/x1-app source includes a MoonParty contract artifact whose constructor accepts `_xoneAddress` and whose ABI exposes XONE redemption/burn participation plus XNT-credit accounting.

Pinned FairCrypto/XONE source independently verifies that XONE's burn path calls an `IBurnRedeemable` callback.

## Exact source semantics

The MoonParty ABI exposes:

- `XONE()`
- `redeemXone(uint256)`
- `getRedeemableXONE()`
- `getExpectedBurnPointsForXone()`
- `getXoneRate(uint256)`
- `allocateXNTCredits(address)`
- `totalAllocatedXNTCredits()`
- `totalBurnPoints()`
- `onTokenBurned(address,uint256)`
- `supportsInterface(bytes4)`

The same pinned application source also:

- renders XONE as a MoonParty participation row;
- displays `XNT Distribution`;
- displays `Burn Points Allocated`;
- reads `totalAllocatedXNTCredits`;
- models user `allocateXNTCredits`.

This is enough to verify a **source-level design link**:

```text
XONE participation/redemption
    -> MoonParty burn/redeemer surface
    -> burn points
    -> XNT credit allocation accounting
```

## What this does not yet prove

The source artifact is not itself deployment proof.

v1 therefore keeps:

```text
moonparty_deployment_verified = false
moonparty_deployment_chain_verified = false
moonparty_runtime_bytecode_verified = false
xnt_credit_to_native_xnt_equivalence_verified = false
xnt_credit_transferability_verified = false
xnt_issuance_verified = false
xnt_vesting_or_unlock_verified = false
xone_snapshot_eligibility_verified = false
october_6_unlock_applies_to_xone_verified = false
xone_xnt_conversion_verified = false
cross_chain_correlation_verified = false
public_service_promoted = false
scout_reliance_promoted = false
execution_authorized = false
```

In particular, `allocateXNTCredits` is not automatically interpreted as a 1:1 native-XNT balance, transferable XNT, a genesis allocation, or an October 6 unlock.

## Pinned provenance

FairCrypto/x1-app:
`abf168fad119e91a8da0773625fd6115e8756cb4`

FairCrypto/XONE:
`267bfeaabd69bf81f272cfd52aa5082333cd317a`

The verifier requires these exact provenance identities for acceptance.

## Next gate after acceptance

Find the exact MoonParty deployed contract address and deployment chain, then verify runtime bytecode/ABI compatibility and direct `XONE()` binding to the already accepted Ethereum XONE contract. Only after that should CMIS query live MoonParty credit state or attempt any Ethereum→X1 issuance correlation.
