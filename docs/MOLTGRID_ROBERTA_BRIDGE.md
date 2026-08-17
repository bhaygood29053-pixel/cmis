# MoltGrid -> Roberta pre-trade bridge

This integration keeps the existing Liquidity Scout MoltGrid/Signal transport
and moves only explicit pre-trade conversation synthesis to Roberta.

```text
MoltGrid / Signal
       |
       v
Liquidity Scout transport
       |
       v
Roberta local bridge
       |
       v
Roberta -> X1 Scout -> CMIS -> X1 provider
```

CMIS remains the deterministic market/risk authority. Roberta remains the
conversation/orchestration authority. The MoltGrid transport does not recompute
CMIS facts.

## Start order

1. Start the CMIS gateway from the Liquidity Scout environment:

```bash
python -m liquidity_scout.cmis.http
```

2. Start Roberta from the `roberta-langgraph` environment after exporting the
   live model key:

```bash
roberta-serve
```

3. Start the MoltGrid listener from the Liquidity Scout environment with the
   pre-trade bridge explicitly enabled:

```bash
ROBERTA_MOLTGRID_PRETRADE_ENABLED=1 \
python -m liquidity_scout.integrations.moltgrid_roberta
```

Defaults:

```text
ROBERTA_BASE_URL=http://127.0.0.1:8766
ROBERTA_TIMEOUT_SECONDS=60
```

If `ROBERTA_API_KEY` is configured on the Roberta bridge, configure the same
value in the MoltGrid listener environment so it is sent as a Bearer token.

## Failure behavior

The feature is disabled by default. When disabled, the wrapper preserves the
existing MoltGrid pre-trade formatter exactly.

When enabled, the exact user message is sent to Roberta. If the Roberta bridge
is unavailable or returns an invalid service envelope, the listener preserves
service continuity with the existing deterministic Liquidity Scout pre-trade
answer and explicitly labels it as a fallback.

No transaction construction, signing, broadcast, wallet custody, autonomous
execution, or value movement is added by this bridge.
