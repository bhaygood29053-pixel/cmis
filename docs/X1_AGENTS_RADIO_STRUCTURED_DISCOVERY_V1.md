# X1 Agents Radio Structured Discovery v1

Status: **ACCEPTED INTERNAL CONTRACT** via Issue #568 / PR #569. Exact-head Liquidity Scout Tests run #1731 passed before merge. The contract remains discovery-only, non-promoted, and `execution_authorized=false`.

Contract:

`x1_agents_radio_structured_discovery/v1`

## Purpose

This contract adds deterministic semantic shaping above the accepted
`x1_agents_radio` source in CMIS Web Discovery.

The source layer answers:

> What public Radio endpoint did CMIS observe?

The structured layer answers:

> What bounded program, deployment, activity, instruction, or health candidates
> can be extracted without treating the provider's labels as verified truth?

It does not create a second HTTP transport and does not make X1 Agents Radio an
authoritative chain provider.

## Accepted endpoint scope

Only the already accepted unauthenticated public GET surfaces are eligible:

- `/api/bootstrap`
- `/api/catalog`
- `/api/deployments`
- `/api/health`

The source allowlist remains:

- `x1radio.vercel.app`
- `x1agentsradio.xyz`

Subscriber/authenticated paths remain excluded. Structured Discovery never
signs requests, subscribes agents, registers webhooks, or authenticates to Radio.

## Schema policy

X1Report describes endpoint purpose, but CMIS does not currently have an
accepted field-by-field Radio response-schema contract.

Structured Discovery therefore does **not** hard-code one exact JSON envelope.
It walks a bounded object/array structure and recognizes candidate records by
program-identity field shape.

Supported candidate program-id aliases include common provider spellings such as
`program_id`, `programId`, `program_address`, `programAddress`,
`address`, and `pubkey`. A generic `id` is accepted only when it is itself
a syntactically valid 32-byte Base58 X1/SVM public key, preventing provider row
IDs from being mistaken for program addresses.

Nested `program` objects and maps keyed by program public key are also
supported.

Unknown provider fields remain visible as unmapped field names. CMIS does not
silently assign semantics to them.

## Candidate normalization

Program/bootstrap/catalog candidates may retain bounded provider-reported:

- program id;
- name/label;
- category/type label;
- instruction/method names;
- transaction/activity counts;
- last-active/last-seen slot or time candidates.

Deployment candidates may additionally retain bounded provider-reported:

- deployment slot;
- upgrade slot;
- deployment/upgrade times;
- event type;
- status;
- transaction signature candidate.

Health candidates may retain bounded provider-reported:

- watcher/service status;
- healthy/ok flag;
- latest slot candidate;
- indexed-program count;
- update time;
- uptime;
- version.

These are all provider-reported candidates, not verified facts.

## Program-id syntax

When a program-id candidate is present, CMIS deterministically checks whether it
Base58-decodes to exactly 32 bytes.

A syntactically valid program id means only:

`program_id_syntax_valid=true`

It does not establish:

- that the account exists;
- that the account is executable;
- its owner/loader;
- its deployed code identity;
- its program-data account;
- its name/category;
- its instruction semantics;
- its deployment or upgrade history;
- its activity counts.

## Verification handoff

A syntactically valid program-id candidate may emit explicit handoffs to:

1. **X1 RPC `getAccountInfo`** — verify exact account identity, executable
   state, owner/loader, and account-data candidate;
2. **X1 RPC `getSignaturesForAddress`** — bounded history discovery;
3. **CMIS source/IDL verification** — verify provider-reported program name,
   category, and instruction semantics against accepted implementation/IDL
   evidence.

Deployment records carrying a transaction-signature candidate may additionally
handoff to:

4. **X1 RPC `getTransaction`** — verify the candidate deployment/upgrade
   transaction.

No handoff result is assumed successful by this contract.

Issue #571 implements the first explicit direct-chain handoff as
`x1_agents_radio_rpc_corroboration/v1`. That follow-on contract can verify
exact current program-account state and bounded transaction activity through
canonical X1 RPC while keeping Radio names/categories/instructions and
deployment-vs-upgrade semantics unverified.

## Bounds

Default/max structured program records:

`100`

Maximum recursive JSON walk depth:

`4`

Maximum retained provider instruction names per record:

`50`

Maximum surfaced unmapped field names per object:

`50`

Provider text candidates are bounded before retention.

The parser fails closed on unsupported endpoints, non-object/non-array payloads,
invalid record limits, and non-object health payloads.

## Truth state

Every structured endpoint/payload result preserves:

```text
discovery_state = DISCOVERED
program_identity_verified = false
program_semantics_verified = false
instruction_semantics_verified = false
deployment_verified = false
upgrade_verified = false
activity_verified = false
freshness_verified = false
web_claim_verified = false
cmis_verified = false
source_independence_verified = false
public_service_promoted = false
scout_reliance_promoted = false
cmis_promotable = false
execution_authorized = false
```

A Radio label such as "DEX", "oracle", "bridge", "agent infrastructure", or
"upgrade" remains a provider classification until the exact claim is verified.

## Internal service seam

`CMISWebDiscoveryService.discover_x1_agents_radio_structured(...)` exposes the
structured endpoint and optionally normalizes an already-observed JSON payload.

It intentionally does not fetch authenticated endpoints and does not promote the
result into the public CMIS capability manifest.

## Regression requirements

Deterministic regression coverage includes:

- endpoint classification;
- subscriber-path rejection;
- nested and flexible provider envelopes;
- generic provider row-id versus nested program-id precedence;
- map-key program-id discovery;
- valid/invalid Base58 program-id syntax;
- provider name/category/instruction candidates;
- activity candidate fields;
- deployment/upgrade and transaction handoff candidates;
- health candidates;
- unknown-field visibility;
- record bounds and visible truncation;
- malformed-input failure;
- service-level non-promotion and `execution_authorized=false`.

Live Radio access is a separate evidence concern. Transport availability or a
successful HTTP response must not be interpreted as semantic verification.
