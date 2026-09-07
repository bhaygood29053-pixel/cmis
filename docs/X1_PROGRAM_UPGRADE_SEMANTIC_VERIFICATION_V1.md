# X1 Program/Upgrade Semantic Verification v1

Status: **ACCEPTED INTERNAL CONTRACT** via Issue #574 / PR #576. Exact-head Liquidity Scout Tests run #1739 passed before merge. The contract verifies loader-level Program/ProgramData and deploy/upgrade semantics only, remains non-promoted as a public/Scout capability, and preserves `execution_authorized=false`.

Contract:

`x1_program_upgrade_semantic_verification/v1`

## Purpose

This contract is the semantic proof layer above
`x1_agents_radio_rpc_corroboration/v1`.

The prior corroboration layer can prove that a successful transaction involving
an exact program occurred at a Radio-reported slot. It deliberately cannot call
that transaction a deploy or upgrade.

This contract closes that gap by decoding canonical SVM BPF Upgradeable Loader
state and instruction semantics from finalized X1 RPC.

## Architecture

```text
X1 Agents Radio
  -> Structured Discovery
  -> X1 RPC Corroboration
  -> X1 Program/Upgrade Semantic Verification
  -> exact loader-state + loader-instruction proof
```

No layer above CMIS is allowed to manufacture deployment/upgrade semantics.

## Underlying loader contract

X1 Tachyon is an Agave-derived SVM implementation. The upgradeable loader
contract used here follows the standard BPF Upgradeable Loader interface.

The canonical loader id is:

`BPFLoaderUpgradeab1e11111111111111111111111`

The loader state variants relevant to this contract are:

- discriminator `2`: `Program { programdata_address }`;
- discriminator `3`: `ProgramData { slot, upgrade_authority_address }`.

Stable serialized sizes used by the verifier:

- Program state: `36` bytes;
- ProgramData metadata prefix: `45` bytes.

The current loader interface documents the ProgramData `slot` as the slot in
which the program was last modified.

Reference lineage:

- X1 Tachyon: https://github.com/x1-labs/tachyon
- Solana loader-v3 state contract:
  https://docs.rs/solana-loader-v3-interface/latest/src/solana_loader_v3_interface/state.rs.html
- Solana loader-v3 instruction contract:
  https://docs.rs/solana-loader-v3-interface/latest/src/solana_loader_v3_interface/instruction.rs.html

## Current program-state proof

For an exact program id, finalized X1 RPC must return a current account that:

1. exists;
2. is executable;
3. is owned by the BPF Upgradeable Loader;
4. contains loader state discriminator `2`;
5. contains one exact ProgramData address.

The verifier then fetches that exact ProgramData account. It must:

1. exist;
2. be owned by the same upgradeable loader;
3. be non-executable;
4. decode as loader state discriminator `3`.

Only then:

`current_program_state_verified=true`

## Upgradeability

ProgramData contains the current upgrade-authority option.

If an authority exists:

```text
current_upgradeability_verified = true
current_upgradeable = true
current_immutable = false
```

If the authority is absent:

```text
current_upgradeability_verified = true
current_upgradeable = false
current_immutable = true
```

This is a current-state fact.

The current authority must not be presented as the historical authority that
signed an older deployment/upgrade unless the exact historical transaction
proves that identity separately.

## Event semantic proof

A Radio-reported event must first pass
`x1_agents_radio_rpc_corroboration/v1`.

For a reported slot, this contract requires the prior layer to provide an exact
transaction signature already corroborated as:

- available;
- successful;
- at the reported slot;
- referencing the exact program id.

The semantic verifier then fetches that same transaction from finalized X1 RPC
and scans top-level and inner instructions for the BPF Upgradeable Loader.

### Upgrade

Legacy/current-compatible loader wire encoding is recognized as:

- little-endian instruction discriminator `3`;
- optional trailing close-buffer boolean.

The exact loader instruction account order must bind:

- account 0 = expected ProgramData;
- account 1 = expected Program.

When the transaction succeeds at the exact reported slot and this binding is
unique:

`verified_semantic_type=UPGRADE`

### DeployWithMaxDataLen

Deployment wire encoding is recognized as:

- little-endian instruction discriminator `2`;
- 64-bit maximum program-data length;
- optional trailing close-buffer boolean.

The exact loader instruction account order must bind:

- account 1 = expected ProgramData;
- account 2 = expected Program.

When the transaction succeeds at the exact reported slot and this binding is
unique:

`verified_semantic_type=DEPLOY`

## ProgramData slot consistency

The current ProgramData last-modified slot must never precede a historically
verified deploy/upgrade event.

For a reported event:

- current ProgramData slot == event slot: the reported event is also the
  currently observed last modification;
- current ProgramData slot > event slot: the event may still be historically
  verified, but a later program modification is observed;
- current ProgramData slot < event slot: evidence is inconsistent and semantic
  verification fails closed.

## Radio label reconciliation

Radio labels such as `upgraded` and `deployed` are still provider claims.

After loader semantics are independently proven:

- verified `UPGRADE` + Radio `upgrade/upgraded` -> label matches;
- verified `DEPLOY` + Radio `deploy/deployed/deployment` -> label matches;
- verified semantic type differs from Radio label ->
  `RADIO_EVENT_LABEL_MISMATCH`.

This contract therefore verifies the event from chain semantics first, then
compares the provider label.

## Ordinary activity

A successful transaction involving the program is not enough.

If the exact successful transaction contains no decodable
DeployWithMaxDataLen/Upgrade loader instruction, the result may be:

`NO_DEPLOY_OR_UPGRADE_IN_TRANSACTION`

That state prevents ordinary swaps, calls, registry actions, or other program
activity from being mislabeled as deployment/upgrade evidence.

If loader instructions are present but cannot be decoded safely, the result is
`EVIDENCE_INCOMPLETE`, not a factual contradiction.

## Result states

Possible high-level states include:

- `PROGRAM_STATE_VERIFIED`
- `UPGRADE_VERIFIED`
- `DEPLOYMENT_VERIFIED`
- `RADIO_EVENT_LABEL_MISMATCH`
- `NO_DEPLOY_OR_UPGRADE_IN_TRANSACTION`
- `NOT_UPGRADEABLE_LOADER_PROGRAM`
- `EVIDENCE_INCOMPLETE`

## Non-goals

This contract does not prove:

- program business/application identity;
- Radio name/category/framework labels;
- application IDL/instruction semantics;
- bytecode correctness or safety;
- source independence;
- historical authority identity from current authority state;
- risk;
- recommendations;
- public service promotion;
- Scout reliance;
- execution authority.

## Authority boundary

Every result preserves:

```text
cmis_verified = false
cmis_promotable = false
public_service_promoted = false
scout_reliance_promoted = false
risk_conclusion_authorized = false
recommendation_authorized = false
execution_authorized = false
```

The contract can contain verified field-level chain semantics without promoting
the entire Radio record or creating a public CMIS product contract.

## Internal service seam

`CMISWebDiscoveryService.verify_x1_program_upgrade_semantics(...)` exposes the
verification handoff internally.

It defaults to canonical X1 RPC and remains read-only.

## Regression requirements

Deterministic coverage includes:

- observed XDEX upgradeable-program envelope compatibility;
- Program state decoding;
- ProgramData state decoding;
- upgradeable and immutable current-state classification;
- exact Program -> ProgramData linkage;
- Upgrade discriminator/account binding;
- DeployWithMaxDataLen discriminator/account binding;
- provider label match/mismatch;
- ordinary activity not becoming upgrade proof;
- exact account-binding mismatch;
- historical verified upgrade followed by a later modification;
- impossible ProgramData-slot ordering;
- non-upgradeable-loader programs;
- malformed loader states;
- prior corroboration-contract enforcement;
- service-level non-promotion;
- `execution_authorized=false`.
