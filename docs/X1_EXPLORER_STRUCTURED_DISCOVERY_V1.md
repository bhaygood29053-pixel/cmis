# X1 Explorer Structured Discovery v1

Status: implementation candidate under CMIS Issue #473.

## Purpose

This contract adds deterministic X1 Explorer route/entity extraction beneath the accepted CMIS Web Discovery v1 foundation.

It solves a specific limitation of ordinary HTML scraping: the official X1 Explorer is client-rendered and its useful chain views are primarily backed by Solana-style RPC calls. CMIS therefore treats the explorer as a discovery surface and converts supported explorer routes into explicit read-only RPC verification handoffs.

Contract:

`x1_explorer_structured_discovery/v1`

## Source evidence

Official public implementation repository:

- repository: `x1-labs/x1-explorer`
- ref observed: `master`
- commit observed: `a2f2512d8436bda544b7db49e06b503515af90d0`
- live mainnet surface: `https://explorer.mainnet.x1.xyz/`

Relevant implementation observations at the pinned commit:

- the search bar routes a Base58 value decoding to 32 bytes to `/address/<address>`;
- it routes a Base58 value decoding to 64 bytes to `/tx/<signature>`;
- numeric search creates `/block/<slot>` and eligible `/epoch/<epoch>` routes;
- transaction status uses an SDK history-aware signature-status call and `getBlockTime`;
- transaction detail uses raw and parsed transaction RPC reads;
- account history uses `getSignaturesForAddress` with an observed first-page limit of 25 and optional parsed-transaction batches;
- account views use parsed/raw account reads;
- block views use `getBlock`, `getBlocks`, and `getSlotLeaders`.

This is implementation evidence only. CMIS does not claim that the deployed explorer is proven to run this exact commit. Repository identity and deployment identity remain separate.

## Supported route classes

### Transaction

`/tx/<signature>`

The signature must decode from Base58 to exactly 64 bytes.

The route can produce an RPC verification handoff including:

- `getSignatureStatuses` as the JSON-RPC equivalent of the explorer SDK status lookup;
- `getBlockTime` if a status slot is available;
- `getTransaction` for raw transaction/meta verification;
- `getTransaction` with parsed encoding as the JSON-RPC equivalent of parsed transaction retrieval.

### Address

`/address/<address>`

The address must decode from Base58 to exactly 32 bytes.

Optional recognized source-code subviews include:

- tokens;
- transfers;
- instructions;
- rewards;
- metadata;
- attributes;
- domains;
- security;
- anchor-program;
- anchor-account;
- verified-build;
- program-multisig;
- and the other explicitly enumerated address tabs in the implementation.

A subview is a route hint only.

For example:

`/address/<address>/tokens`

does **not** prove that the address is a mint, wallet, token account, owner, holder, or beneficial owner.

Address verification handoff can include:

- parsed `getMultipleAccounts`;
- raw `getMultipleAccounts`;
- `getSignaturesForAddress`;
- optional `getTransaction` parsing for returned signatures.

### Block

`/block/<slot>`

The slot must be a non-negative integer.

Verification handoff includes `getBlock`. Explorer presentation also uses bounded `getBlocks` and `getSlotLeaders`, but those calls are optional for entity identity.

### Epoch

`/epoch/<epoch>`

The epoch must be a non-negative integer.

This first slice recognizes the route only. It does not promote epoch semantics or add an epoch verification service.

## Related-entity extraction

When bounded CMIS Web Discovery page retrieval exposes same-host links, this contract can convert supported links into related structured candidates.

Example:

`/address/A`
→ page link `/tx/T`
→ page link `/block/42`

becomes:

- address candidate A;
- related transaction candidate T;
- related block candidate 42.

Duplicates are removed by entity type + identifier. Unsupported routes are ignored rather than guessed.

Client-side content that is not present in retrieved HTML is not fabricated. Browser-rendered/network-call capture remains a later optional fallback layer.

## Truth state

A supported route establishes only that its **route syntax** matches the pinned explorer implementation contract.

Every result remains:

`discovery_state=DISCOVERED`
`explorer_route_verified=true`
`entity_identity_verified=false`
`address_subtype_verified=false`
`web_claim_verified=false`
`cmis_verified=false`
`source_independence_verified=false`
`public_service_promoted=false`
`scout_reliance_promoted=false`
`cmis_promotable=false`
`execution_authorized=false`

The exact chain identity is verified only after the designated CMIS/X1 RPC handoff succeeds under the relevant accepted contract.

## Example verification flow

`https://explorer.mainnet.x1.xyz/tx/<signature>`

→ X1 Explorer structured discovery identifies a syntactically valid 64-byte transaction signature
→ CMIS X1 RPC retrieves the transaction
→ exact signature / slot / instruction / account / token-balance evidence is checked
→ only the verified fields may enter downstream CMIS evidence or intelligence contracts

The explorer route itself is never the proof root.

## Non-goals

This contract does not:

- execute JavaScript in a browser;
- intercept private/authenticated browser traffic;
- claim current RPC/archive completeness;
- identify an address as a wallet/program/token/mint from URL shape alone;
- prove source independence;
- promote explorer labels to risk or ownership semantics;
- change the public CMIS capability manifest;
- authorize X1 Scout/ROBERTA reliance;
- construct, sign, broadcast, or execute transactions.

## Next extension after acceptance

After this route/RPC handoff slice is accepted, the next X1 Explorer extension can add bounded browser/network-call observation for information that is unavailable in static HTML, while preserving the same source allowlist, provenance, discovery-only state, and RPC verification boundary.
