# MoonParty Deployment Verification v1

Status: **ACCEPTED INTERNAL BOUNDED FOUNDATION** via Issue #601 / PR #602. MoonParty Deployment Verification run #2 passed deterministic and live discovery jobs at head `b6396af0052a68f4bfe5db1dea099df2e333b000`, Liquidity Scout Tests run #1786 passed, and PR #602 merged as `2b73ec07c775eebe7ea86ff54155e29b866d0d9a`.

Contract:

`moonparty_deployment_verification/v1`

## Purpose

Turn the accepted FairCrypto MoonParty source design into exact deployment evidence without collapsing source code, frontend configuration, Ethereum runtime identity, XNT-credit accounting, and native XNT issuance into one claim.

The previous accepted source-semantic gate proved:

```text
XONE participation/redemption
  -> MoonParty burn/redeemer surface
  -> burn points
  -> XNT credit allocation accounting
```

This gate asks whether an exact deployed MoonParty contract can be identified and directly tied to the already accepted Ethereum XONE contract.

## Candidate discovery

Deployment candidates are extracted only from bounded MoonParty-specific contexts, including explicit `MOONPARTY_ADDRESS_*` configuration, `moonPartyAddress` payloads, or exact addresses on a MoonParty-specific source line.

The live gate inspects:

- pinned FairCrypto/x1-app artifact/config sources;
- current `xen.network` MoonParty/portfolio/root frontend payloads;
- current `preview.xen.network` equivalents;
- bounded same-host JavaScript chunks referenced by those pages.

Generic page-wide Ethereum addresses are not treated as MoonParty candidates.

If the corpus yields zero exact addresses, the accepted interpretation is only:

```text
deployment_candidate_count = 0
zero_candidates_are_scoped_corpus_evidence_only = true
moonparty_deployment_verified = false
```

It is not proof that MoonParty was never deployed.

## Accepted live result

The bounded live gate retrieved all 4/4 pinned FairCrypto sources, all 6/6 current `xen.network` / `preview.xen.network` frontend targets, and 26/28 bounded same-host JavaScript chunks. Across 35 inspected documents, it found **0 exact MoonParty deployment-address candidates**.

The evidence artifact digest is `sha256:56198255749d41ddba7d5bb7f65eac874b4eddd3191737fd8adebd4888fc9a68`.

The accepted interpretation is strictly scoped:

```text
deployment_candidate_count = 0
zero_candidates_are_scoped_corpus_evidence_only = true
zero_candidates_do_not_prove_non_deployment = true
moonparty_deployment_verified = false
moonparty_deployment_chain_verified = false
moonparty_runtime_compatible = false
moonparty_xone_binding_verified = false
```

This means the current pinned/public frontend corpus does not expose the deployment address needed for direct-RPC qualification. It does **not** establish that MoonParty was never deployed.

## Direct-chain qualification

An exact candidate must independently pass Ethereum mainnet direct-RPC checks:

1. non-empty runtime code;
2. exact runtime length matching the pinned artifact;
3. matching Solidity compiler metadata trailer;
4. required MoonParty ABI selectors present;
5. runtime agreement with the pinned artifact outside declared linked/immutable deployment regions;
6. direct `XONE()` call equals accepted XONE:
   `0x4dcda2274899d9bba3bb6f5a852c107dd6e4fe1c`;
7. `supportsInterface(0x543746b1)` is true;
8. nonzero `VMPX()`, `xenBurn()`, `xenCrypto()`, and `xenTorrent()` bindings;
9. bounded reads of `DURATION()`, `genesisTs()`, `amp()`, `totalBurnPoints()`, and `totalAllocatedXNTCredits()`.

One RPC proof is not enough to verify deployment identity.

## Corroboration

`moonparty_deployment_verified=true` requires matching candidate identity from at least two distinct public Ethereum RPC transport hosts.

Only deployment identity is promoted by that corroboration. The contract deliberately keeps:

```text
xnt_credit_to_native_xnt_equivalence_verified = false
xnt_credit_transferability_verified = false
xnt_issuance_verified = false
xnt_vesting_or_unlock_verified = false
october_6_unlock_applies_to_xone_verified = false
xone_xnt_conversion_verified = false
cross_chain_correlation_verified = false
public_service_promoted = false
scout_reliance_promoted = false
execution_authorized = false
```

A positive `totalAllocatedXNTCredits` value would still be a MoonParty accounting fact, not proof that native XNT was issued or is transferable.

## Next gate

Because this accepted run found zero exact deployment candidates, the next task is **MoonParty deployment provenance expansion**: search additional authoritative FairCrypto/XEN release history, archived frontend/config material, package/deployment artifacts, verified explorer source, and provenance-qualified deployer history for an exact address. Any newly discovered candidate must pass this contract's direct-chain and two-RPC corroboration gate before deployment identity can be promoted.

Only after a deployment is verified should CMIS establish the exact semantics and provenance of `allocateXNTCredits` and test whether those credits map into native X1 XNT allocation/claim/vesting state.
