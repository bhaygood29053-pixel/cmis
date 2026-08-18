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

The legacy Liquidity Scout router remains in the codebase for deliberate
operator diagnostics and rollback only. It is **not** an automatic user-facing
fallback in Roberta-first production mode. If Roberta cannot return a valid
bridge response, the user receives one concise availability message instead of
raw Liquidity Scout/CMIS output:

> Roberta is temporarily unavailable. Please try your request again shortly.

The existing reply-link confirmation remains in control so a failed or ambiguous
post does not produce a second visible reply.

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

Supported Roberta replies are also converted to MoltGrid-safe plain text in
simple-only mode. Markdown headings, bold/code markers, and list syntax are
removed as presentation only; answer facts are not summarized or recalculated.
List items are rendered with Unicode bullets so the response remains readable
when MoltGrid does not interpret Markdown.

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
They are retained for rollback and compatibility. Once a compatibility route
has been handed to Roberta, a Roberta bridge failure returns the same concise
availability message instead of exposing a legacy formatter response.

## Recommended production service stack

The production deployment should run CMIS, Roberta, and the MoltGrid listener as
managed systemd services. This removes the need to keep terminal sessions open.

1. Install the CMIS gateway from the Liquidity Scout repository:

```bash
bash scripts/install_cmis_systemd.sh
```

CMIS listens on `127.0.0.1:8765`, starts automatically, and restarts after an
unexpected failure.

2. Install the Roberta bridge from the `roberta-langgraph` repository:

```bash
bash scripts/install_roberta_bridge_systemd.sh
```

Roberta listens on `127.0.0.1:8766`. Its installer stores model secrets outside
Git and waits for the bridge health endpoint before declaring success.

3. After the existing `liquidity-scout.service` listener unit is installed,
   install the startup dependency drop-in from this repository:

```bash
bash scripts/install_moltgrid_service_dependencies.sh
```

The helper writes a systemd drop-in that declares:

```ini
[Unit]
Wants=roberta-bridge.service cmis-gateway.service
After=roberta-bridge.service cmis-gateway.service
```

It also adds pre-start health gates for both `http://127.0.0.1:8766/healthz`
and `http://127.0.0.1:8765/healthz`. Each dependency gets up to 30 seconds to
become healthy before the MoltGrid listener startup fails closed.

The listener remains loosely coupled with `Wants=` rather than `Requires=` so a
later Roberta or CMIS restart does not automatically tear down the transport.
Roberta's user-facing availability handling remains responsible for temporary
runtime outages.

If the listener unit uses a different service name, set
`LIQUIDITY_SCOUT_SERVICE_NAME` when running the helper.

Expected managed topology:

```text
cmis-gateway.service       -> 127.0.0.1:8765
roberta-bridge.service     -> 127.0.0.1:8766
            \                 /
             \               /
              v             v
             liquidity-scout.service
                     |
                     v
              MoltGrid / Signal
                     |
                     v
                  Roberta
                     |
                  X1 Scout
                     |
                    CMIS
```

## Manual development start order

For local development only, the same components can still be launched manually
in separate terminals:

```bash
python -m liquidity_scout.cmis.http
```

then, from the Roberta repository after loading its model environment:

```bash
roberta-serve
```

then the MoltGrid listener:

```bash
ROBERTA_MOLTGRID_ALL_QUESTIONS_ENABLED=1 \
ROBERTA_MOLTGRID_SIMPLE_ONLY_ENABLED=1 \
python -m liquidity_scout.integrations.moltgrid_roberta
```

Do not run a manual listener at the same time as the managed
`liquidity-scout.service` listener.

Defaults:

```text
ROBERTA_BASE_URL=http://127.0.0.1:8766
ROBERTA_TIMEOUT_SECONDS=60
```

If `ROBERTA_API_KEY` is configured on the Roberta bridge, configure the same
value in the MoltGrid listener environment so it is sent as a Bearer token.

## Failure behavior

Roberta handoff features require explicit environment flags. This permits a
controlled operator rollback to the existing Liquidity Scout listener when the
Roberta-first mode itself is deliberately disabled.

In all-questions mode, a supported user message is sent to Roberta exactly as
admitted. If the Roberta bridge is unavailable or returns an invalid service
envelope, the listener does **not** execute the legacy router for the user. It
posts only:

> Roberta is temporarily unavailable. Please try your request again shortly.

The legacy router can still be exercised explicitly by an operator for
diagnostics or restored by deliberately changing the configured ownership mode;
it is not part of the automatic production failure path.

When simple-only mode declines a question, it returns the fixed interface-policy
message before any request is sent to Roberta. This is intentional and does not
invoke the legacy router.

No transaction construction, signing, broadcast, wallet custody, autonomous
execution, or value movement is added by this bridge. Pre-trade remains
analysis-only when simple-only mode is disabled, and Roberta's X1 market facts
continue to come through X1 Scout and deterministic CMIS services.
