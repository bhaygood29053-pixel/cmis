# Scout ↔ CMIS Integration Contract

## Purpose

This document defines the external boundary between chain-specialist Scouts and
Cross-Chain Market Intelligence Service (CMIS).

The intended flow is:

```text
Roberta
  ↓
X1 Scout / Solana Scout
  ↓ HTTP + JSON
CMIS Gateway
  ↓
CMIS deterministic services
  ↓
X1 Provider / Solana Provider
```

Scouts interpret verified CMIS results. Scouts do **not** call X1.Ninja, X1
RPC, Solana RPC, DEX APIs, scanners, or CMIS databases directly.

## HTTP endpoint

CMIS exposes one service-request endpoint:

```text
POST /v1/cmis
Content-Type: application/json
```

Capability discovery:

```text
GET /v1/cmis/capabilities
```

Process health:

```text
GET /healthz
```

The default server bind is `127.0.0.1:8765`.

Start it from the repository root with:

```bash
python -m liquidity_scout.cmis.http
```

A non-loopback bind requires `CMIS_API_KEY`. When configured, callers send:

```text
Authorization: Bearer <CMIS_API_KEY>
```

CMIS never returns provider credentials to a Scout.

## Request envelope

Every service call uses this outer request shape:

```json
{
  "service": "market_report",
  "chain": "x1",
  "asset": "AGI",
  "params": {}
}
```

Fields:

- `service` — required CMIS service name.
- `chain` — required target chain.
- `asset` — required by asset-specific services; may be omitted for `rank`.
- `params` — optional service-specific JSON object.

The Scout must specify the chain. CMIS does not silently route a Solana request
through X1 or vice versa.

## Supported services

CMIS exposes exactly these service names:

```text
asset_lookup
market_report
rank
historical_compare
tokenomics
risk_check
pre_trade_check
```

### asset_lookup

```json
{
  "service": "asset_lookup",
  "chain": "x1",
  "asset": "AGI"
}
```

CMIS collects the current provider catalog and resolves the asset internally.
Ambiguous human-facing identifiers fail closed.

### market_report

```json
{
  "service": "market_report",
  "chain": "x1",
  "asset": "AGI"
}
```

The Scout does not supply pools. CMIS resolves the asset, collects the current
catalog, and performs asset-wide aggregation. External market reports expose
`#LPs` as the public liquidity-pool count while retaining internal compatibility
fields where needed.

### rank

```json
{
  "service": "rank",
  "chain": "x1",
  "params": {
    "metric": "volume",
    "limit": 10
  }
}
```

Supported ranking metrics are determined by CMIS. Ranking rows expose `#LPs`.
Incomplete metric coverage is not converted to zero.

### historical_compare

```json
{
  "service": "historical_compare",
  "chain": "x1",
  "asset": "AGI",
  "params": {
    "question": "Has AGI liquidity fallen more than 30% in 7 days?"
  }
}
```

CMIS obtains the current verified market report and compares it against its
separate historical store. The Scout does not supply a historical database or
current pool snapshot.

### tokenomics

Catalog-resolved request:

```json
{
  "service": "tokenomics",
  "chain": "x1",
  "asset": "AGI"
}
```

For an explicit mint that does not need catalog resolution:

```json
{
  "service": "tokenomics",
  "chain": "x1",
  "params": {
    "mint": "<mint supplied by the caller>"
  }
}
```

CMIS verifies current supply and authority facts through its provider boundary.
Ordinary tokenomics calls do not automatically claim lifetime burn/mint
coverage.

### risk_check

```json
{
  "service": "risk_check",
  "chain": "x1",
  "asset": "AGI",
  "params": {
    "policy": {
      "min_liquidity_usd": 1000
    }
  }
}
```

CMIS internally obtains current market and tokenomics evidence before running
the deterministic risk engine. A caller may also request a deterministic
historical input:

```json
{
  "service": "risk_check",
  "chain": "x1",
  "asset": "AGI",
  "params": {
    "historical_question": "Has AGI liquidity fallen more than 30% in 7 days?"
  }
}
```

Risk outcomes may be `PASS`, `WARN`, or `BLOCK`. Service status and risk outcome
are separate concepts.

### pre_trade_check

```json
{
  "service": "pre_trade_check",
  "chain": "x1",
  "asset": "AGI",
  "params": {
    "trade": {
      "side": "buy",
      "notional_usd": 25
    }
  }
}
```

CMIS resolves verified identity and runs `risk_check` before the deterministic
pre-trade gate. If the trade omits `chain` or `asset`, CMIS may fill them from
the verified risk result. Caller-supplied conflicting identities are preserved
so the deterministic mismatch gate can block them.

`pre_trade_check` is analysis only. It never authorizes signing or execution.

## Response envelope

Every valid CMIS service request returns the standard structure:

```json
{
  "service": "market_report",
  "chain": "x1",
  "status": "ok",
  "asset": {},
  "data": {},
  "risk": null,
  "confidence": {},
  "sources": [],
  "observed_at": null,
  "warnings": [],
  "errors": []
}
```

Supported service statuses:

```text
ok
partial
unavailable
ambiguous
error
```

A Scout must preserve `sources`, `observed_at`, `confidence`, `warnings`, and
`errors` when reporting findings upward to Roberta. `partial`, `unavailable`,
and `ambiguous` are meaningful states, not invitations to invent missing facts.

## Chain behavior

Current gateway state:

```text
x1      recognized + enabled
solana  recognized + provider not yet implemented
```

A Solana request currently returns `status="unavailable"` with
`chain_provider_not_implemented`. This is deliberate. It prevents accidental
X1 fallback while allowing the Scout contract to remain chain-aware before the
Solana Provider is added.

Unknown chains return `status="error"` with `unsupported_chain`.

## Scout client example

A separate Scout project can implement a very small client. For example:

```python
import json
from urllib.request import Request, urlopen


def cmis_request(base_url, payload, api_key=None):
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    request = Request(
        base_url.rstrip("/") + "/v1/cmis",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


report = cmis_request(
    "http://127.0.0.1:8765",
    {
        "service": "market_report",
        "chain": "x1",
        "asset": "AGI",
        "params": {},
    },
)
```

The client should treat the CMIS envelope as data. Interpretation belongs in
the chain Scout; final synthesis and user policy belong in Roberta.

## Boundary rules

The external Scout must not:

- import `liquidity_scout.providers.x1` or future Solana provider internals;
- send provider pool rows as substitutes for CMIS collection;
- manufacture missing market, liquidity, volume, supply, holder, authority,
  address, burn/mint, or risk values;
- convert `partial`, `unavailable`, or `ambiguous` into verified facts;
- treat `pre_trade_check` as transaction authorization.

CMIS must not:

- make final user recommendations on Roberta's behalf;
- silently substitute one chain for another;
- expose provider credentials;
- claim unavailable verification;
- authorize live trading.
