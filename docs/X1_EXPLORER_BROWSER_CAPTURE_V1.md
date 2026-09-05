# X1 Explorer Browser Capture v1

Status: implementation candidate under CMIS Issue #477.

## Purpose

This contract adds an operator-controlled passive browser capture utility above the accepted X1 Explorer network-observation layer.

Contract:

`x1_explorer_browser_capture/v1`

The tool exists only to make JavaScript-rendered X1 Explorer network activity observable in a bounded way. It does not turn CMIS into a browser agent.

## Runtime model

The capture accepts one explicit supported X1 Explorer mainnet route.

It then:

1. validates the route through `x1_explorer_structured_discovery/v1`;
2. lazily loads Playwright only when the operator actually invokes the capture;
3. launches Chromium in a fresh ephemeral browser context;
4. disables downloads;
5. blocks service workers for a smaller, more deterministic capture surface;
6. opens one page;
7. registers a response observer;
8. navigates to the exact requested route;
9. waits only for the bounded dwell window;
10. immediately converts each eligible response into a transient HAR-like record;
11. immediately sanitizes that transient record through `x1_explorer_network_observation/v1`;
12. retains only sanitized observation records;
13. closes the context and browser.

No click, form submission, wallet interaction, transaction simulation, request replay, or second-page crawl is part of this contract.

## Optional dependency

Playwright is intentionally **not** added to `requirements.txt`.

Core CMIS imports and deterministic CI must continue to work without Playwright installed.

An operator who wants to use the capture installs it explicitly, for example:

```bash
python -m pip install playwright
python -m playwright install chromium
```

Then from the repository root:

```bash
PYTHONPATH=. python scripts/capture_x1_explorer_network.py \
  "https://explorer.mainnet.x1.xyz/address/<ADDRESS>"
```

The script writes the sanitized JSON result to stdout only.

Optional bounds:

```bash
PYTHONPATH=. python scripts/capture_x1_explorer_network.py \
  "https://explorer.mainnet.x1.xyz/tx/<SIGNATURE>" \
  --navigation-timeout-ms 20000 \
  --dwell-seconds 3 \
  --max-network-events 100
```

`--headed` may show the browser window for operator visibility, but it does not enable interaction in the capture code.

## Initial bounds

- one page per invocation;
- supported structured X1 Explorer mainnet route only;
- default navigation timeout: 20 seconds;
- hard navigation timeout cap: 30 seconds;
- default dwell: 3 seconds;
- hard dwell cap: 10 seconds;
- default observed-event cap: 100;
- hard observed-event cap: 250;
- downloads disabled;
- no persistent profile/storage state supplied;
- no background monitoring.

## Network handling

Only requests to hosts already accepted by `x1_explorer_network_observation/v1` enter the transient sanitizer path.

Foreign targets are ignored before their body is read.

Non-JSON GET resources such as HTML, JavaScript, CSS, images, and fonts are ignored before their body is read.

POST requests are accepted into the sanitizer only as candidates; the downstream network-observation contract still rejects unknown or execution-oriented JSON-RPC methods.

Raw request headers, cookies, post bodies, response headers, cookies, and response bodies exist only transiently inside the browser/process when necessary and are not returned in the capture result.

No HAR file is written.

## Output

The sanitized result includes:

- capture contract;
- requested page URL;
- structured route candidate;
- configured bounds;
- number of network events seen;
- number of sanitized observations emitted;
- sanitized `x1_explorer_network_observation/v1` records;
- explicit browser-state and authority flags.

Required false/zero states include:

`clicks_performed=0`
`forms_submitted=0`
`wallet_interaction_performed=false`
`raw_har_retained=false`
`raw_network_records_retained=false`
`raw_request_bodies_retained=false`
`raw_response_bodies_retained=false`
`request_replay_authorized=false`
`background_monitoring_authorized=false`
`public_service_promoted=false`
`scout_reliance_promoted=false`
`cmis_promotable=false`
`execution_authorized=false`

## Truth boundary

Browser capture increases observability. It does not increase truth authority.

A captured `getTransaction` call and a matching Explorer `/tx/<signature>` route may improve discovery/correlation, but the transaction remains an unverified candidate until the accepted X1 RPC/CMIS verification path proves the relevant fields.

The browser is not the trust root.

## Failure behavior

The tool fails closed when:

- Playwright is unavailable;
- the page URL is not a supported structured X1 Explorer mainnet route;
- a capture bound is outside policy;
- browser launch/navigation raises an error.

It does not fall back to Selenium, shell commands, uncontrolled scraping, request replay, or a broader host set.

## Deterministic testing

CI uses fake browser objects.

No Playwright installation or real browser is required to prove:

- one-page navigation;
- fresh context settings;
- download prohibition;
- zero-click behavior;
- event-count bounds;
- foreign-resource body avoidance;
- non-JSON resource body avoidance;
- execution-RPC rejection through the v3 sanitizer;
- raw browser material absence from the returned result;
- authority and promotion invariants.

## Non-goals

This contract does not authorize:

- automated browsing across multiple pages;
- clicking or form submission;
- login/session use;
- wallet connection;
- CAPTCHA bypass;
- site restriction bypass;
- arbitrary page scripting;
- request replay;
- arbitrary RPC passthrough;
- transaction simulation;
- signing;
- broadcasting;
- custody;
- trading;
- bridge value movement;
- autonomous monitoring.

A later issue may generalize the same passive capture contract to other CMIS Web Discovery source adapters, but each source will require its own explicit host/action/data contract.
