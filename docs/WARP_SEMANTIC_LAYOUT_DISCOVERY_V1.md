# Warp semantic layout discovery v1

Issue: #428  
Historical evidence lineage: #407  
Depends on: #425 / PR #426  
Runs after accepted #407 / PR #429 and does not block #409

## Purpose

Move Warp rare-account work from structural byte families into reproducible account-type identity without treating a third-party IDL as truth. This is an on-chain corroboration/hardening layer for the already accepted official-config semantics from #407 / PR #429; it does not replace that accepted contract and is not a prerequisite for #409.

Contract:

`warp_semantic_layout_discovery/v1`

## Evidence chain

The merged `warp_rare_account_capture/v1` gate established four rare account families on both Solana and X1:

| Space | Live first 8 bytes |
| ---: | --- |
| 170 | `c5344915bfef2a86` |
| 236 | `b12511c9f29ed441` |
| 321 | `9b0caae01efacc82` |
| 335 | `784d4a622253607d` |

A public Warp dashboard repository contains an IDL for the exact live Warp program id:

- repository: `nibty/warp-bridge-dashboard`
- commit: `6a9ea7187879778d3a46e313d1fec177541adce8`
- path: `src/idl/warp_bridge.json`
- blob: `59da74924923a7155c5187c35c4a5c559c32ad0b`

This source is explicitly treated as **public third-party corroboration only**.

## Reproducible account-type identity

The IDL account names reproduce the live first eight bytes under Anchor's deterministic rule:

`sha256("account:<AccountName>")[:8]`

| Space | Account type | Anchor discriminator |
| ---: | --- | --- |
| 170 | `TokenRegistryEntry` | `c5344915bfef2a86` |
| 236 | `Roles` | `b12511c9f29ed441` |
| 321 | `Config` | `9b0caae01efacc82` |
| 335 | `GuardianSet` | `784d4a622253607d` |

The declared layouts also account for the observed allocation sizes.

Account type is accepted by this discovery contract only when all of these agree:

1. exact Warp owner already verified by #426;
2. exact rare-family account length;
3. exact Anchor discriminator;
4. reproducible PDA identity;
5. decoded PDA bump equals the derived bump.

## PDA evidence

The fixed singleton seeds reproduce the exact live pubkeys:

- `["config"]` -> `48Po6qAHRJojbXH7KRqt6s5GfNfs9VEGccfqYEHmubEi` (bump 255)
- `["guardian_set"]` -> `837ujVePfx3EB5CibC4FAAZJf5CTpiVXCE41BNBJoB3x` (bump 253)
- `["roles"]` -> `HFWg6MpqBr446bGUqDxpr3sCQ5B92uCbTj7RUZa2aS6v` (bump 255)

For each 170-byte `TokenRegistryEntry`, v1 reads the first IDL-declared field (`local_mint`) from ephemeral bytes and independently reproduces:

`["token_registry", local_mint]`

The account is rejected if that PDA does not equal the observed account pubkey.

## Decoded discovery fields

The slice decodes bounded fields from the pinned layout for discovery.

Examples include:

- `Config`: paused candidate, guardian-count/threshold candidates, sequence counters, fee candidates, pause metadata, chain-id candidate;
- `GuardianSet`: set-index, guardian-count, threshold and guardian pubkeys;
- `Roles`: pauser / fee-manager / registrar candidates;
- `TokenRegistryEntry`: local mint, decimals, native/wrapped candidate, symbol candidate, pause candidate, caps, volume, fee candidates and whale-delay candidates.

These names are **not promoted semantics** merely because the IDL labels them. The live workflow is intended to test whether they also satisfy independent cross-chain and behavioral invariants.

## Confidence boundary

The contract may report:

`account_type_identity_verified=true`

and

`pda_identity_verified=true`

when the reproducible identity checks pass.

It still preserves:

`field_semantics_verified=false`  
`account_role_verified=false`  
`route_semantics_verified=false`  
`bridge_health_verified=false`  
`semantic_contract_accepted=false`  
`cmis_promotable=false`  
`execution_authorized=false`

## Why the distinction matters

The account type `Config` can be cryptographically identified without yet accepting that a byte named `paused` is authoritative bridge-health truth.

Likewise, `TokenRegistryEntry` can be identified by discriminator + PDA without yet accepting its fee, cap, mint relationship, or native/wrapped flag as CMIS route truth.

Those semantic promotions require separate behavioral or independently sourced evidence.

## Live gate

`.github/workflows/warp-semantic-layout-discovery-evidence.yml`:

1. runs deterministic discriminator/PDA/layout tests;
2. re-captures the rare accounts on Solana and X1 with ephemeral base64;
3. requires every candidate to classify by discriminator + size + PDA;
4. prints only decoded, non-raw discovery evidence;
5. keeps all semantic and execution promotion flags false.

Raw base64 is never committed as a source fixture or workflow artifact.

## Next evidence target

If the live gate confirms the expected Config, GuardianSet, Roles and TokenRegistryEntry identities, later hardening may independently corroborate specific on-chain fields while #409 proceeds from the already accepted official-config semantic contract:

1. `Config.chain_id` against the observed chain;
2. `GuardianSet` threshold/cardinality against independently observed bridge signing behavior;
3. `TokenRegistryEntry.local_mint` against exact chain token identities;
4. pause, fee, cap and native/wrapped fields against official-app or transaction behavior.

Only fields that survive those independent checks should become eligible for CMIS semantic promotion.
