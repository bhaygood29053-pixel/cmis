# Theo Prime Advisory Provider Connection v1

Status: **internal / read-only / connection-ready / live transport unaccepted**

Tracking issue: #418

## Purpose

This slice establishes the CMIS trust boundary for communicating with Theo Prime
without turning an AI-agent answer into verified on-chain truth.

The architecture remains:

```text
ROBERTA
  -> X1 Scout
    -> CMIS
      -> Theo advisory provider
```

Theo is an advisory/discovery source beneath CMIS. ROBERTA and X1 Scout do not
call Theo directly through this contract.

## Contract

`theo_advisory_observation/v1`

A successful observation means only that CMIS used an **accepted transport
contract** and received text from the exact remote identity specified by that
contract. It does not verify any factual claim inside the text.

## Current connection state

The production registry starts empty:

```text
accepted Theo transport contracts = 0
connection state = blocked_transport_contract
```

This is deliberate. Public user-facing surfaces are not enough to invent a
machine API, authentication scheme, endpoint, request schema, or response
schema.

A separate evidence gate must prove the exact live Theo transport before CMIS
adds it to `ACCEPTED_THEO_TRANSPORT_CONTRACTS`.

## Required live-transport evidence

A future acceptance PR must establish, at minimum:

1. exact Theo remote identity;
2. exact transport type;
3. exact machine endpoint or transport mechanism, when applicable;
4. exact authentication requirements, if any;
5. exact request schema;
6. exact response schema;
7. deterministic error behavior;
8. identity binding between request destination and returned sender;
9. safe timeout/retry policy;
10. sanitized reproducible fixture;
11. no transaction/signing/value-movement side effects.

## Authority boundary

Transport verification is **not factual verification**.

Even if Theo says a statement is "verified", "safe", "official", or provides a
confidence score, the observation remains:

```text
status = observed_unverified
advisory_claims_verified = false
factual_authority = false
market_fact_authority = false
risk_authority = false
bridge_fact_authority = false
backing_fact_authority = false
custody_fact_authority = false
source_independence_verified = false
cmis_promotable = false
scout_reliance_promoted = false
execution_authorized = false
```

Fresh market, tokenomics, risk, bridge, backing, custody, and historical claims
must still be proven through accepted CMIS provider/on-chain evidence.

## Transport abstraction

The collection function uses an injected transport callable. This keeps the
CMIS trust contract stable whether a future accepted Theo path is X/xChat,
Telegram, HTTP, or another X1-owned machine surface.

Production calls fail before transport activity while the accepted registry is
empty. Tests may inject a private test-only registry to prove behavior without
creating a live endpoint or credential dependency.

## Non-goals

- no direct ROBERTA -> Theo provider bypass;
- no autonomous conversation loop;
- no wallet/private-key use;
- no signing or transaction construction;
- no broadcast or value movement;
- no trading or bridge execution;
- no Theo-based Proof Score;
- no Theo-based CMIS risk score;
- no promotion of Theo self-reported trust/confidence.
