# MoltGrid -> Roberta bridge

This integration keeps Liquidity Scout's existing MoltGrid/Signal transport and
makes Roberta the conversational/orchestration front door.

The recommended production mode is **Roberta-first for every admitted Signal
question**, optionally combined with the MoltGrid **simple-only** interface
policy described below.

```text
MoltGrid / Signal
       |
       v
Liquidity Scout transport + admission / duplicate protection
       |
       +--> simple-only scope gate (optional)
       |        |
       |        +--> advanced/report-style request -> short interface limitation
       |
       v
Roberta
       |
       +--> general conversation / identity -> Roberta answers directly
       |
       +--> concise X1 market facts -> X1 Scout -> CMIS -> X1 provider
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
accepts is owned by the Roberta-first bridge before Liquidity Scout's legacy
question router is allowed to answer it.

If Roberta cannot return a valid bridge response for one message, that message
alone falls back to Liquidity Scout's existing router. The fallback does not
re-enter Roberta, and the existing reply-link confirmation remains in control so
a failed or ambiguous post does not produce a second visible reply.

## MoltGrid simple-only interface policy

For the current MoltGrid site, advanced answers can be harder to read reliably.
Enable the conservative channel policy with:

```text
ROBERTA_MOLTGRID_SIMPLE_ONLY_ENABLED=1
```

This is a **channel/presentation policy**, not a limitation on Roberta's
underlying capabilities.

When enabled, concise requests continue to Roberta, including examples such as:

- general conversation and identity questions;
- simple explanations;
- single current market facts such as price, liquidity, volume, or holders;
- short X1/token questions and simple status questions.

Requests that normally require long or structured output are not sent to
Roberta from this MoltGrid bridge. Examples include:

- multi-asset comparisons and `vs` requests;
- rankings, top-N, trending, gainers, and losers;
- historical comparisons and time-series reports;
- pre-trade or buy/sell advice requests;
- detailed risk/safety analysis;
- raw CMIS evidence, diagnostics, technical reports, tables, JSON/CSV, or code;
- unusually long prompts that do not fit the current concise interface policy.

Those requests receive this professional response:

> Thank you for your question. This request requires more detailed analysis or
> formatting than MoltGrid's current messaging interface can reliably support.
> To preserve accuracy and readability, I'm unable to provide that analysis on
> this site at this time. I can still help here with general questions and
> concise information.

Disable the flag later when MoltGrid presentation capabilities improve or when
a richer response surface is available.

## Compatibility mode

The earlier selected-route flags remain supported when all-questions mode is
off:

```text
ROBERTA_MOLTGRID_PRETRADE_ENABLED=1
ROBERTA_MOLTGRID_CONVERSATION_ENABLED=1
```

Those flags route explicit pre-trade and general/identity questions to Roberta
while leaving normal market/ranking routes under the legacy listener router.
They are retained for rollback and compatibility.

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
ROBERTA_MOLTGRID_SIMPLE_ONLY_ENABLED=1 \
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

Roberta handoff features require explicit environment flags. This permits a
controlled rollback to the existing Liquidity Scout listener.

In all-questions mode, a supported user message is sent to Roberta exactly as
admitted. If the Roberta bridge is unavailable or returns an invalid service
envelope, the listener preserves service continuity by running the pre-existing
Liquidity Scout route for that exact message and visibly labels the result as a
fallback.

When simple-only mode declines a question, it returns the fixed interface-policy
message before any request is sent to Roberta. This is intentional and does not
invoke the legacy router.

No transaction construction, signing, broadcast, wallet custody, autonomous
execution, or value movement is added by this bridge. Pre-trade remains
analysis-only when simple-only mode is disabled, and Roberta's X1 market facts
continue to come through X1 Scout and deterministic CMIS services.
