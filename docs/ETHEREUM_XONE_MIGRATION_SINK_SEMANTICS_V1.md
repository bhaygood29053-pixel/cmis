# Ethereum XONE Migration Sink Semantics v1

Status: **ACCEPTED INTERNAL CONTRACT** via Issue #586 / PR #587. Ethereum XONE Migration Sink Semantics run #1 passed deterministic and live multi-RPC jobs at head `ed0ea9694b0ee0cb415541a3c1b23e7f95471253`, Liquidity Scout Tests run #1761 passed, and PR #587 merged as `cdba7189c5d9faf0b24e7e0df7c1e12d0a41e501`. The accepted result verifies the exact XONE burn-accounting surface while intentionally leaving `migration_sink_identified=false`.

Contract:

`ethereum_xone_migration_sink_semantics/v1`

## Why this gate exists

The next XONE/XNT question is not simply "which address receives XONE?"

The exact verified XONE contract exposes a burn/redeemer design. Its verified ABI includes:

- `burn(address user,uint256 amount)`;
- `userBurns(address)`.

The published XONE LP states that XONE implements `IBurnableToken` and permits compatible smart contracts adhering to `IBurnRedeemable` to burn XONE. FairCrypto's shared `IBurnRedeemable` interface uses:

`onTokenBurned(address user,uint256 amount)`.

That architecture means a future XONE -> XNT converter could be a callback/burn-redeemer contract rather than a passive address that accumulates transferred XONE.

Sources used only for semantic design context:

- exact verified XONE ABI/source surface: Etherscan address `0x4DCDa2274899d9BbA3Bb6f5A852C107Dd6E4fE1c`;
- XONE LP v4: `https://faircrypto.org/XONE_LP.pdf`;
- FairCrypto shared burn interfaces are visible in verified XEN-family contracts.

These source statements do not identify an XONE -> XNT converter.

## Canonical selectors

```text
burn(address,uint256)                 0x9dc29fac
userBurns(address)                    0xce653d5f
onTokenBurned(address,uint256)        0x543746b1
supportsInterface(bytes4)             0x01ffc9a7
```

The live gate directly calls `userBurns(address)` on the exact accepted XONE contract across multiple Ethereum RPC transports. This proves the readable burn-accounting surface without attempting a state-changing burn.

## Candidate contract verification

For an exact candidate address, CMIS may verify:

1. Ethereum mainnet;
2. non-empty runtime bytecode;
3. ERC165 `supportsInterface(0x543746b1)`.

A positive result means only:

`burn_redeemer_interface_candidate`

It does **not** mean:

- XONE -> XNT converter;
- migration contract;
- vesting contract;
- claim contract;
- XNT issuer;
- bridge;
- lock contract.

## No caller-supplied promotion

This v1 contract deliberately contains no boolean shortcut capable of converting a candidate into verified migration truth.

Even if a candidate:

- receives XONE transfers, and/or
- supports `IBurnRedeemable`,

the contract still returns:

```text
migration_sink_identified = false
lock_or_migration_verified = false
xone_xnt_conversion_verified = false
xnt_issuance_verified = false
cross_chain_correlation_verified = false
```

Promotion requires a later accepted proof that binds the exact Ethereum contract to an exact X1 XNT issuance/allocation/vesting/claim mechanism.

## Authority boundary

```text
public_service_promoted = false
scout_reliance_promoted = false
risk_conclusion_authorized = false
recommendation_authorized = false
execution_authorized = false
```

## Accepted live result

Run #1 satisfied the two-provider quorum with Tenderly and Blast; dRPC and 1RPC also returned compatible burn-surface proofs, while Merkle was rate-limited on one identity request. The evidence artifact digest is `sha256:e1a4b56476f87b733bfb71b4187758e1b3c8c31a74479075addb69d74ea5a808`.

The exact live `userBurns(address)` probe values were:

- zero address: `0`;
- XONE deployer `0xc73fc08c931efe3fce850c09278472e8a81c2e05`: `0`.

Those two zero values are scoped only to those two addresses at the observed finalized state. They do **not** establish zero lifetime XONE burns, zero burns by other addresses, or zero future burns.

The accepted result is:

```text
xone_burn_accounting_surface_verified = true
simple_transfer_sink_required_by_this_proof = false
migration_sink_identified = false
xone_xnt_conversion_verified = false
xnt_issuance_verified = false
cross_chain_correlation_verified = false
execution_authorized = false
```

This is a successful fail-closed result: CMIS verified the burn-accounting mechanism while refusing to fabricate a conversion sink.

## Next slice

Use the dedicated XONE/XNT web scraper plus direct Ethereum evidence to discover exact candidate contracts or addresses associated with migration/conversion language. Each candidate must then pass this contract's code/interface checks and, separately, be bound to exact X1 XNT issuance/vesting/claim evidence before conversion can be verified.
