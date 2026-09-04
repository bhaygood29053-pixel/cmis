# Warp Bridged Supply Evidence v1

Contract: `warp_bridged_supply_evidence/v1`

Parent: CMIS #409  
Evidence issue: CMIS #451

## Purpose

Provide a bounded, read-only current bridged-supply basis for an exact
provenance-qualified Warp route without treating the provider label
`/api/bridge/tvl` as supply truth.

The first accepted candidate route is:

- Solana native wSOL:
  `So11111111111111111111111111111111111111112`
- X1 wrapped wSOL.X:
  `JDqX4vau2P5zJmLpuNitvR6vMURr9kYjex6oZQXz3Ja8`
- Warp program:
  `6JbPTuxVuoTgyQeXFb9MH8C8nUY8NBbLP1Lu4B13JfMD`

## Exact current closure

The contract requires all of the following:

1. accepted `warp_config/exact-mint-pair/v1` route semantics;
2. source representation is native and destination representation is non-native;
3. exact source Warp vault PDA derived from `["vault", source_mint]`;
4. exactly one source token account for that vault and exact source mint;
5. source token-account authority equals the exact vault PDA;
6. exact destination Warp mint-authority PDA derived from
   `["mint_authority", destination_mint]`;
7. destination mint current authority equals that exact Warp PDA;
8. destination mint-account supply and `getTokenSupply` agree exactly;
9. source/destination decimals agree with the accepted route;
10. source vault raw balance equals destination wrapped-mint raw supply;
11. source/destination observation times are within the bounded skew policy.

Only then may the contract emit a verified `supply_evidence` object suitable
for the existing `bridge_flow_intelligence/v1` supply projection.

## Why this is stronger than `/tvl`

A label such as TVL does not define whether the value means locked source
reserves, destination issued supply, USD value, or another provider-specific
quantity. This contract instead proves the exact chain objects and requires
cross-chain raw-unit closure.

The public third-party Warp IDL is corroboration only. It documents the
expected lock/mint/burn topology and the deterministic `vault` and
`mint_authority` PDA seeds, but CMIS does not promote IDL prose by itself.

## Fail-closed cases

Bridged supply remains unavailable on any:

- route or mint mismatch;
- wrong vault or token-account owner;
- wrong mint authority;
- missing/malformed RPC field;
- mint-account / getTokenSupply mismatch;
- decimals mismatch;
- source-vault / destination-supply mismatch;
- incompatible observation times.

## Promotion boundary

This evidence slice does not by itself complete #409.

Still separate:

- #441 historical-retention / requested-window coverage;
- normalized 24h/7d/30d flow-window completion in #409;
- #410 Bridge-to-XDEX utilization;
- ROBERTA #314 adoption.

The contract always remains read-only and keeps:

- `public_service_promoted=false`
- `scout_reliance_promoted=false`
- `execution_authorized=false`
