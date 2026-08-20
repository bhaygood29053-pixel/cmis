# CMIS Engineering Workflow

Status: repository-authoritative workflow for meaningful CMIS changes.

Related governance initiative: CMIS #259. Cross-project coordinator: `bhaygood29053-pixel/roberta-langgraph#97`.

## Purpose

CMIS is the deterministic evidence, verification, risk, intelligence, capability, and bounded analysis authority beneath Chain Scouts and Roberta:

```text
User / transport
  -> Roberta
    -> Chain Scout
      -> CMIS
        -> Chain Provider / verified source
```

This workflow applies to meaningful CMIS features, bug fixes, provider integrations, deterministic intelligence contracts, policy changes, promotions, compatibility migrations, and readiness changes.

It does not create product capability by itself. It does not widen public-service, Scout-reliance, transaction, signing, broadcasting, custody, trading, bridge-transfer, or autonomous value-movement authority.

## 1. Roadmap ownership gate

Before implementation, record in the issue/spec:

- the accepted roadmap item or defect being advanced;
- the exact capability or behavior being changed;
- the supported chain(s) and scope;
- whether the work is foundation-only, internal, public-service promoted, Scout-reliance promoted, deployment/readiness-only, or documentation/governance-only;
- what is explicitly not promoted or authorized.

Interesting provider features, AI ideas, libraries, or external technologies remain research candidates until an accepted issue/roadmap decision promotes them into implementation work.

## 2. Contract/spec before code

Define the accepted contract before adapting CMIS to a provider response shape.

As applicable, specify:

- problem / missing capability;
- exact chain and subject identity requirements;
- accepted input and output semantics;
- source role, provenance, and verification requirements;
- evidence scope, freshness, time/slot/block bounds;
- units and normalization rules;
- canonical or content-addressed identity requirements;
- deterministic classification or policy semantics;
- Evidence Receipt relationship;
- Proof Score relationship;
- risk relationship;
- `null` / unknown / unavailable / partial / conflict behavior;
- provider disagreement behavior;
- fail-closed conditions;
- public-service and Scout-reliance state;
- execution-authorization state;
- non-goals;
- deterministic regression cases.

Provider field names or provider assertions are inputs to contract design, not the CMIS contract itself.

## 3. Prefer narrow tracer-bullet slices

Implement the smallest end-to-end behavior that can be independently verified through the accepted internal or public seam.

Prefer:

```text
one accepted behavior
  -> deterministic contract
  -> provider/evidence binding if needed
  -> public/internal seam
  -> regression test
  -> exact-head validation
```

Avoid large horizontal sequences such as adding all models, then all providers, then all tests when a smaller vertical slice can prove the intended behavior first.

If a wide compatibility migration is unavoidable, use:

```text
expand -> migrate -> contract
```

Preserve a green accepted path between steps.

## 4. Behavior-first deterministic tests

Tests should prove accepted CMIS behavior through stable contracts and seams rather than private implementation details.

Expected values should come from an independent specification, fixture, worked example, or accepted external contract. Avoid tautological tests that simply reproduce the implementation formula.

Where practical:

```text
failing behavior test
  -> confirm RED
  -> minimum deterministic implementation
  -> confirm GREEN
  -> next slice
```

Regression coverage must include malformed, conflicting, missing, ambiguous, stale, incompatible-scope, incompatible-unit, and duplicate/tampered cases whenever those failure modes are relevant to the contract.

## 5. Provider facts remain candidates until CMIS verifies them

A provider response, documentation statement, or API label does not automatically become an independently verified CMIS fact.

Preserve:

- exact provider/source identity;
- source role;
- exact chain/asset/pool/route/account/transaction scope as applicable;
- observation time/slot/block where available;
- coverage limitations;
- disagreement and unresolved state.

Promotion to verified CMIS truth requires the accepted verification contract for that exact field/capability.

Do not convert provider labels such as `holder`, `whale`, `insider`, `bot`, `market maker`, `risk`, or `verified` into authoritative CMIS meaning without an accepted deterministic contract proving those semantics.

## 6. Evidence and provenance discipline

Preserve the existing Evidence Receipt / Proof Score / provenance architecture as the canonical evidence system. Do not create a competing trust or provenance authority.

For freshness-sensitive or externally sourced claims, the accepted record should preserve enough information to answer:

1. What exact fact is claimed?
2. Which source produced the observation?
3. What is that source's role and verification state?
4. What exact identity/scope does the claim cover?
5. When was it observed?
6. What limitations or disagreements remain?
7. Which Evidence Receipt / Proof Score identity applies where the contract supports one?

Proof Score and risk are separate dimensions. Neither may be silently converted into the other.

Missing evidence remains unknown/unavailable. Never replace missing values with `0`, `false`, an empty collection, or an estimate unless the contract explicitly defines that value as a proven fact.

## 7. Deterministic reconciliation vocabulary

When comparable observations differ, classify only when the evidence contract supports the distinction:

- **superseded** — a later accepted observation replaces an older observation for the same semantics;
- **evolution** — both observations can be valid because the observed state changed over time;
- **conflict** — materially comparable evidence disagrees and cannot both satisfy the current contract;
- **unknown / insufficient** — the available evidence cannot resolve the state.

Do not use LLM judgment as the trust root for these classifications when CMIS market, risk, or intelligence semantics are at stake.

## 8. Exact-head and degraded-evidence verification

Before merge:

- run targeted tests for the changed contract;
- run the full applicable deterministic suite / GitHub Actions on the exact PR head;
- confirm the final changed-file scope;
- inspect unresolved review threads;
- verify the branch is integrated with the intended current base.

Where live/configured evidence matters, deterministic tests establish the contract while separately accepted live/configured probes establish only the exact bounded operational claim they prove.

Failures, skips, provider errors, disagreements, partial states, and unavailable evidence must remain visible rather than being converted into successful-looking output.

## 9. Three-axis PR readiness gate

A non-trivial CMIS PR is merge-ready only when all three axes pass independently.

### Axis 1 — Spec / contract fidelity

Verify that:

- every accepted requirement is implemented;
- failure, unavailable, partial, and conflict semantics match the issue/spec;
- required regressions exist;
- unsupported capability is not silently added;
- chain, identity, scope, units, freshness, and provenance rules are preserved;
- public-service, Scout-reliance, readiness, and execution state match the contract exactly.

### Axis 2 — Code / architecture quality

Check for:

- unnecessary duplication or abstraction;
- hidden provider coupling;
- unclear domain names or types;
- scope or unit ambiguity;
- brittle test seams;
- scattered policy logic that should be deterministic and centralized;
- accidental breaking changes to accepted contracts;
- compatibility or migration hazards.

### Axis 3 — Authority / evidence safety

Fail the review if the change, without a separately accepted contract:

- upgrades provider-reported information to independently verified truth;
- converts missing/unknown values into `0`, `false`, empty, or estimated values;
- merges incompatible chain/source/pool/route/time/unit scopes;
- treats token accounts as unique holders or beneficial owners;
- adds ownership, whale, insider, bot, accumulator, distributor, market-maker, manipulator, fraud, scam, or intent labels;
- converts Proof Score into risk or risk into Proof Score;
- accepts caller-supplied Evidence Receipts, Proof Scores, trust labels, or replacement verification state as trust roots;
- lets Roberta or a Chain Scout bypass the CMIS verification boundary;
- changes an internal/foundation capability into public-service or Scout-reliance state by implication;
- turns analysis into transaction preparation, signing, broadcasting, custody, trading, bridge transfer, or autonomous value movement;
- weakens `analysis_only=true` or `execution_authorized=false` where currently required.

Passing tests and code review is insufficient if Axis 3 fails.

## 10. Post-merge reconciliation

After accepted work merges:

- verify post-merge `main` state and applicable CI;
- close/complete the originating issue only when its acceptance criteria are actually satisfied;
- update authoritative roadmap/status documentation so completed work is not left represented as an open dependency;
- keep foundation/internal work distinct from public-service/Scout-reliance promotion;
- record the next accepted roadmap boundary without silently authorizing it.

## PR author checklist

For every meaningful PR, be able to answer:

1. What exact behavior is being proven?
2. What issue/roadmap item owns it?
3. What exact evidence supports it?
4. What remains unknown/unavailable?
5. What identity, chain, scope, units, and freshness bounds apply?
6. What fails closed?
7. Is this foundation-only, internal, public-service, Scout-reliance, deployment/readiness, or governance-only?
8. Does it change Proof Score, risk, verification, or authority?
9. What does it explicitly not authorize?
10. Did Spec/Contract, Code/Architecture, and Authority/Evidence Safety each pass independently?

## Cross-project boundary

Roberta issue `bhaygood29053-pixel/roberta-langgraph#97` coordinates the shared engineering initiative, HXMP provenance discipline, and future Technology Radar specification.

CMIS #259 does not authorize CMIS to:

- implement HXMP durable memory;
- build or run a Technology Radar;
- monitor GitHub, Hacker News, Product Hunt, or trend feeds as a CMIS responsibility;
- become the general agent/orchestrator;
- change Roberta's conversational policy.

CMIS should expose deterministic machine-readable contracts that Chain Scouts and Roberta can consume without inventing facts.

## Permanent safety boundary

Unless a separately accepted future contract explicitly changes authority, CMIS governance and engineering workflow changes do not authorize:

- transaction preparation for execution;
- signing;
- broadcasting;
- private-key or seed custody;
- swap/trade execution;
- bridge/value transfer;
- autonomous trading;
- autonomous value movement.

**CMIS proves more by verifying more, not by guessing more.**