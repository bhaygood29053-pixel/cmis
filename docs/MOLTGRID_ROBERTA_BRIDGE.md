# MoltGrid -> Roberta bridge

This integration keeps Liquidity Scout's existing MoltGrid/Signal transport and
makes Roberta the conversational/orchestration front door.

The recommended production mode is **Roberta-first for every admitted Signal
question**:

```text
MoltGrid / Signal
       |
       v
Liquidity Scout transport + admission / duplicate protection
       |
       v
Roberta
       |
       +--> general conversation / identity -> Roberta answers directly
       |
       +--> X1 market / ranking / history / tokenomics / risk
       |          |
       |          v
       |       X1 Scout -> CMIS -> X1 provider
       |
       +--> explicit pre-trade analysis
                  |
                  v
               X1 Scout -> CMIS -> X1 provider
```

CMIS remains the deterministic market/risk authority. Roberta remains the
conversation/orchestration authority. The MoltGrid transport does not recompute
CMIS facts.

## Recommended all-questions mode

Enable:

```text
ROBERTA_MOLTGRID_ALL_QUESTIONS_ENABLED=1
```

When this flag is on, every message that the existing Signal intake already
accepts is sent to Roberta before Liquidity Scout's legacy question router is
allowed to answer it. This includes general conversation, identity, X1/XDEX
market data, rankings, historical comparisons, tokenomics, risk, multi-asset
questions, and explicit pre-trade questions.

If Roberta cannot return a valid bridge response for one message, that message
alone falls back to Liquidity Scout's existing router. The fallback does not
re-enter Roberta, and the existing reply-link confirmation remains in control so
a failed or ambiguous post does not produce a second visible reply.

## Compatibility mode

The earlier selected-route flags remain supported when all-questions mode is
off:

```text
ROBERTA_MOLTGRID_PRETRADE_ENABLED=1
ROBERTA_MOLTGRID_CONVERSATION_ENABLED=1
```

Those flags route explicit pre-trade and general/identity questions to Roberta
while leaving normal market/ranking routes under the legacy listener router.
They are retained for rollback and compatibility; they are not the recommended
mode when Roberta is intended to control the complete conversation.

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

3. Start the MoltGrid listener from the Liquidity Scout environment:

```bash
ROBERTA_MOLTGRID_ALL_QUESTIONS_ENABLED=1 \
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

All Roberta handoff features are disabled by default and require an explicit
environment flag. This permits a controlled rollback to the existing Liquidity
Scout listener.

In all-questions mode, the exact admitted user message is sent to Roberta. If
the Roberta bridge is unavailable or returns an invalid service envelope, the
listener preserves service continuity by running the pre-existing Liquidity
Scout route for that exact message and visibly labels the result as a fallback.

No transaction construction, signing, broadcast, wallet custody, autonomous
execution, or value movement is added by this bridge. Pre-trade remains
analysis-only and Roberta's X1 market facts continue to come through X1 Scout
and deterministic CMIS services.
