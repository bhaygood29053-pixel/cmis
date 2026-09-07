# X1 Agents Radio → X1 RPC Corroboration v1

Status: **IMPLEMENTATION FOR ISSUE #571 — NOT ACCEPTED UNTIL PR/CI MERGE**

Contract:

`x1_agents_radio_rpc_corroboration/v1`

## Purpose

This contract is the verification layer immediately above accepted X1 Agents
Radio discovery and structured discovery.

The pipeline is:

```text
X1 Agents Radio
  -> CMIS Radio discovery / structured candidate
  -> X1 Agents Radio -> X1 RPC Corroboration v1
  -> canonical X1 RPC direct-chain evidence
  -> only exact proven chain fields may be treated as verified chain facts
```

The contract does not make Radio an authoritative source. It uses Radio only to
discover an exact program/deployment candidate, then asks canonical X1 RPC what
the chain itself proves.

## Accepted inputs

The corroborator accepts either:

- a normalized record from the existing read-only
  `liquidity_scout.providers.x1.agents_radio` provider; or
- a `program_candidate` / `deployment_candidate` produced by
  `x1_agents_radio_structured_discovery/v1`.

The candidate must resolve to one syntactically valid 32-byte Base58 X1/SVM
program id.

When chain/network/source fields are supplied they must remain X1-mainnet /
X1 Agents Radio scoped. A candidate that arrives with execution authority or as
pre-promoted CMIS truth fails closed.

## Canonical RPC proof

The default runtime path uses the accepted canonical X1 RPC transport.

### 1. Current program account

`getAccountInfo` is requested at `finalized` commitment for the exact Radio
candidate program id.

RPC may establish:

- whether the exact account currently exists;
- the observation slot;
- the account `executable` flag;
- the current owner/loader;
- optional current lamports/space fields when present.

A currently existing executable account with a verified owner yields:

`exact_program_account_corroborated=true`

This verifies the exact on-chain program-account address/state only. It does not
verify a Radio name or business identity.

### 2. Bounded finalized activity

`getSignaturesForAddress` is requested at `finalized` commitment for the exact
program id.

Default history bound:

`25`

Maximum history bound:

`100`

The response can verify only the returned bounded page and successful
transactions inside that page.

An empty bounded page is explicitly **not** lifetime-inactivity proof.

### 3. Radio-reported deployment/upgrade slot

For a deployment candidate, the Radio-reported slot is retained only as a
provider claim.

The corroborator checks whether bounded finalized history contains a successful
transaction at that exact slot.

If a syntactically valid provider-reported transaction signature is available,
the corroborator may inspect that signature directly even when it is not present
in the bounded history page.

Otherwise the first successful matching history signature may be inspected.

### 4. Exact transaction corroboration

`getTransaction` is requested with:

- `encoding=jsonParsed`;
- `commitment=finalized`;
- `maxSupportedTransactionVersion=0`.

For the inspected transaction, RPC may verify:

- the transaction exists;
- it is at the Radio-reported slot;
- it succeeded;
- the exact candidate program id is referenced by the transaction.

Only when all of those are true:

`reported_slot_transaction_corroborated=true`

That is **activity-at-slot corroboration**, not deployment or upgrade semantic
proof.

## What RPC does not prove here

This v1 contract always preserves the following Radio claims as unverified by
this corroboration layer:

- program name;
- category such as DEX, bridge, oracle, or agent infrastructure;
- framework;
- provider status labels;
- description;
- instruction/IDL semantics;
- Radio's own `verified` flag;
- `tx_count_24h`;
- deployment semantics;
- upgrade semantics.

For example, a successful transaction involving an executable program at a
Radio-reported "upgrade" slot does not prove that the transaction was an
upgrade. A separate loader/program-data semantic proof is required for that
claim.

## Source independence

X1 RPC is the canonical direct-chain verifier for the exact chain-native fields
it returns.

However:

```text
radio_rpc_source_independence_verified = false
same_fact_agreement_is_source_independence = false
```

CMIS does not assume that X1 Agents Radio was produced independently of X1 RPC
or another overlapping upstream chain/indexer source.

## Result states

Possible high-level states include:

- `PROGRAM_ACCOUNT_CORROBORATED`
- `REPORTED_SLOT_ACTIVITY_CORROBORATED`
- `ACCOUNT_NOT_FOUND`
- `ACCOUNT_NOT_EXECUTABLE`
- `EVIDENCE_INCOMPLETE`

`ACCOUNT_NOT_FOUND` means finalized RPC returned `value=null` for the exact
current account query. It is a current-account observation and is not a
historical claim.

`EVIDENCE_INCOMPLETE` is not a factual failure of Radio. For example, a
reported slot not appearing inside a bounded recent history page is insufficient
negative evidence.

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

The result may contain individually verified direct-chain fields under
`verified_chain_fields`. That field-level verification must not be confused
with wholesale promotion of the Radio record.

## Internal service seam

`CMISWebDiscoveryService.corroborate_x1_agents_radio_rpc(...)` exposes this
read-only verification handoff internally and defaults to canonical X1 RPC.

The service remains an internal CMIS Web Discovery seam. It does not add a new
public CMIS capability and does not authorize X1 Scout reliance.

## Regression requirements

Deterministic regressions cover:

- direct parsed Radio program records;
- Structured Discovery deployment candidates;
- exact Base58 program-id validation;
- current account existence/executable/owner verification;
- current account absence;
- existing non-executable account handling;
- bounded finalized history;
- empty-history non-overclaim;
- exact reported-slot successful activity;
- optional provider-reported transaction signature;
- transaction slot/success/program-reference requirements;
- malformed RPC fail-closed behavior;
- source/chain/network/authority mismatch rejection;
- history bounds;
- service-level non-promotion;
- `execution_authorized=false`.

Live RPC/Radio availability is a separate operational evidence concern. A
successful live call does not weaken any semantic boundary above.
