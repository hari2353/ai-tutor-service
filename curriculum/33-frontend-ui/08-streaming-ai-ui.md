# Streaming Agent UIs: SSE vs WebSocket, Token Streaming, Optimistic Tool-Call Rendering

> **Track:** T33 Frontend & UI Engineering · **Time:** 3h · **Prereqs:** T33-react-advanced, T33-state-management
> **Module id:** `T33-streaming-ai-ui` · **Tags:** ai, critical

## The 30-second version

Use Server-Sent Events over a POST `fetch()` with a `ReadableStream` reader for the 90% case — one-directional token delivery from an LLM that needs to survive proxies, load balancers, and CDNs without sticky sessions; reach for WebSockets only when the client needs to push mid-stream (barge-in on a voice agent, collaborative multi-user cursors). SSE has no transport-level backpressure — the server keeps writing regardless of whether the client is consuming — so the client must buffer incoming deltas and drain them on its own schedule (typically `requestAnimationFrame`, ~60Hz) rather than calling `setState` per token, or a fast model on a slow device turns into a re-render storm. Cancellation is `AbortController` wired through the `fetch` call and the reader; the client must also tell the server to actually stop billing tokens, which `abort()` alone does over a dropped TCP connection but is worth confirming server-side rather than assuming. Optimistic tool-call UI means rendering the "calling `search_flights`..." card the instant the tool-call delta arrives, not when the result comes back, and reconciling state (not remounting) when the result lands so the card doesn't flash. Vercel's AI SDK (v6, shipped May 2026) standardizes this whole pattern behind `useChat` and a message-parts model, and it's worth knowing what it does for you and what it hides, because interviewers will ask you to explain the raw mechanics underneath it.

## Why this gets asked

Because every AI product built since 2023 has a chat-shaped UI, and building that UI correctly touches a surprising number of frontend fundamentals at once: streams, backpressure, cancellation, error boundaries, and rendering performance under high update frequency. The interviewer has almost certainly shipped a chat UI that fell over in one of three specific ways — the tab became unresponsive because every token triggered a full component re-render, the "stop generating" button didn't actually stop the model from burning tokens server-side, or a network blip mid-stream left the UI showing a permanently truncated response with no way to recover. They want to know if you understand streaming as a systems problem (producer/consumer rate mismatch, partial failure, resource cleanup) rather than as "hook up `useChat` and it works." For an AI engineer specifically, this module is often the one place in a frontend interview loop where your backend/LLM experience and your frontend experience have to visibly meet — you're expected to reason about token generation rate, not just DOM updates.

---

## Lineage: past → present → future

**What came before.** Early LLM-backed UIs (2020-2022, GPT-3 playground era) mostly did the naive thing: send a request, show a spinner, render the full response when it arrived. That was tolerable when responses were short and latency was a second or two, but as models scaled to multi-paragraph, multi-second generations, a blocking spinner on a 15-second response felt broken even though nothing was actually wrong — users abandon requests they can't see progress on. The fix borrowed directly from a mechanism that already existed for a different problem: SSE (part of the HTML5 spec, formalized around 2009-2011) had been built for one-directional server push — stock tickers, live scores, notification feeds — where the client never needed to talk back mid-stream. The insight that made "type out the response like a person typing" the default UX wasn't new UI thinking, it was repurposing a decade-old push mechanism because the shape of the problem (one long producer, one passive consumer) matched exactly.

**Where it stands now.** SSE over `fetch()` (not the browser `EventSource` API, which can't POST or set auth headers) is the dominant transport for token streaming — OpenAI, Anthropic, and Google's chat completion APIs all use it, and Vercel's AI SDK defaults to it. The live disagreement is narrower than it looks: almost nobody argues WebSockets are better for pure token delivery, because the bidirectional capability just goes unused and the stateful connection complicates horizontal scaling (sticky sessions or a shared connection broker across server instances) for zero benefit. Where WebSockets earn their keep is specifically when the client needs to send something *while* the server is still streaming — voice-agent barge-in (user interrupts mid-response), collaborative editing, or a tool that needs a mid-generation approval click. The other live disagreement is client-side rendering strategy: whether to batch token updates through `requestAnimationFrame`, debounce/throttle with a fixed interval, or rely on React 18's automatic batching and just accept per-token `setState` calls — the answer depends on measured token rate versus frame budget, and "it depends, here's how I'd measure it" is the senior answer, not a fixed rule.

**Where it's heading.** The AI SDK ecosystem (Vercel's `ai` package specifically) is consolidating the pattern into a standard message-parts model — a message is not a string, it's an ordered array of parts (text delta, tool-call, tool-result, reasoning, source citation, file), and UI components subscribe to parts rather than re-parsing raw stream chunks. This is genuinely useful and likely to keep spreading (LangChain's `LangGraph` UI helpers and other framework SDKs are converging on similar shapes) but it is speculative to claim any one vendor's wire format becomes a durable standard — Vercel's own v5→v6 migration in 2026 changed the wire format again for a claimed 15-25% first-token latency improvement, which tells you these formats are still actively being iterated on, not settled. What does look durable: text deltas arriving as they're generated, tool calls as a distinct streamed event type, and client-side reconciliation rather than full-message replacement, because those map to how autoregressive generation and tool-calling actually work mechanically, independent of any SDK's opinions.

---

## Mental model

Think of the stream as three independent rate-mismatched stages, each of which can be the bottleneck:

```
[Model decode loop]  --tokens-->  [Network/SSE frame]  --bytes-->  [Client parser]  --deltas-->  [Renderer]
   ~20-100 tok/s          arbitrary chunking            immediate         apply to state    60Hz frame budget
   (server-controlled)    (TCP/proxy buffering)         (synchronous)     (batched or not)   (16.7ms/frame)
```

The model decode loop is the producer; it emits tokens at whatever rate the model, batch size, and hardware allow (roughly 20-100 tokens/sec for typical hosted chat models as of 2026, faster for smaller/distilled models, slower under contention). The renderer is the ultimate consumer, and it has a hard budget: one frame is 16.7ms at 60Hz, and if you do `setState` per token and each token triggers a full subtree re-render that takes longer than that, you fall behind and the UI stutters or the tab becomes unresponsive under a fast model. Everything between producer and final consumer — the SSE frame boundaries, the client-side parser, any buffering you add — exists to absorb the rate mismatch. The critical thing SSE gets wrong for you: there is no flow-control signal from consumer back to producer, so if your renderer falls behind, bytes just pile up in the browser's internal buffer and your batching layer, not the network, has to be the thing that catches up gracefully (drop to rendering larger chunks, not drop data).

---

## How it actually works

### The wire format: what an SSE frame actually looks like

An SSE stream is plain text over a normal HTTP response with `Content-Type: text/event-stream`, one or more `data:` lines per event, and a blank line terminating each event:

```
data: {"type":"text-delta","delta":"The capital"}

data: {"type":"text-delta","delta":" of France"}

data: {"type":"text-delta","delta":" is Paris."}

data: {"type":"tool-call","toolCallId":"call_1","toolName":"search_flights","args":{"from":"SFO"}}

data: {"type":"tool-result","toolCallId":"call_1","result":{"flights":[...]}}

data: {"type":"finish","finishReason":"stop","usage":{"promptTokens":42,"completionTokens":18}}

```

The payload inside `data:` is application-defined JSON — SSE itself only mandates the `data:`/`event:`/`id:`/`retry:` line structure and the double-newline frame boundary. `id:` lets the client track the last event it saw (`Last-Event-ID` header on reconnect); `retry:` sets the browser's auto-reconnect delay for native `EventSource` (default 3000ms) — irrelevant here since POST streaming bypasses `EventSource` entirely and reconnection has to be handled by application code.

### Server side: emitting the stream (Node, minimal, framework-agnostic)

```javascript
// untested sketch — illustrates the mechanics, not a full production handler
import { createServer } from "node:http";

const server = createServer(async (req, res) => {
  if (req.method !== "POST" || req.url !== "/chat") return res.end();

  res.writeHead(200, {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache, no-transform", // no-transform stops proxies from buffering/chunking SSE
    Connection: "keep-alive",
    "X-Accel-Buffering": "no", // disables nginx response buffering specifically
  });

  const send = (obj) => res.write(`data: ${JSON.stringify(obj)}\n\n`);

  // heartbeat comment line every 15s — keeps idle load balancers/proxies from
  // timing out the connection during long tool calls with no token output
  const heartbeat = setInterval(() => res.write(`: ping\n\n`), 15000);

  req.on("close", () => {
    // client disconnected (tab closed, or AbortController fired) — stop the
    // upstream model call here, this is where you actually save the tokens
    clearInterval(heartbeat);
    upstreamModelCall.abort?.();
  });

  try {
    for await (const chunk of streamFromModel(requestBody)) {
      send({ type: "text-delta", delta: chunk });
    }
    send({ type: "finish", finishReason: "stop" });
  } catch (err) {
    send({ type: "error", message: "upstream generation failed" });
  } finally {
    clearInterval(heartbeat);
    res.end();
  }
});
```

The `req.on("close", ...)` handler is the part people skip and then wonder why aborting the client fetch doesn't stop the model bill — closing the TCP connection fires `close` on the server request object, and that is exactly where you cancel the upstream model call. Without it, the client stops rendering but the server keeps generating (and paying for) tokens nobody will ever see.

### Client side: reading the stream without `EventSource`

`EventSource` cannot send a POST body or custom headers, which rules it out for any authenticated chat API. The real client implementation reads the raw byte stream off `fetch()`'s `response.body`:

```javascript
async function streamChat(messages, { signal, onDelta, onToolCall, onFinish, onError }) {
  const res = await fetch("/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages }),
    signal, // AbortController.signal — this is what makes cancellation work
  });

  if (!res.ok || !res.body) throw new Error(`stream failed: ${res.status}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const frames = buffer.split("\n\n");
      buffer = frames.pop(); // last element may be an incomplete frame, keep it

      for (const frame of frames) {
        const line = frame.split("\n").find((l) => l.startsWith("data: "));
        if (!line) continue;
        const payload = JSON.parse(line.slice(6));

        if (payload.type === "text-delta") onDelta(payload.delta);
        else if (payload.type === "tool-call") onToolCall(payload);
        else if (payload.type === "finish") onFinish(payload);
        else if (payload.type === "error") onError(new Error(payload.message));
      }
    }
  } catch (err) {
    if (err.name === "AbortError") return; // expected on user-initiated stop
    onError(err);
  } finally {
    reader.releaseLock();
  }
}
```

`decoder.decode(value, { stream: true })` matters — without `stream: true`, a multi-byte UTF-8 character split across two network chunks (very possible mid-emoji or mid-CJK-character) gets decoded incorrectly on the boundary. The `buffer.split("\n\n")` / `frames.pop()` dance handles SSE frames that arrive split across TCP packet boundaries, which happens constantly and is the most common source of "streaming works in dev, breaks in prod" bugs when someone assumes one `read()` call maps to one complete event.

### Rendering without a re-render storm

The naive version — `setState` on every `onDelta` call — works fine up to some token rate, then doesn't. The fix decouples arrival rate from render rate with a small buffer flushed on the frame clock:

```javascript
function useTokenBuffer(onFlush) {
  const bufferRef = useRef("");
  const rafRef = useRef(null);

  const push = useCallback((delta) => {
    bufferRef.current += delta;
    if (rafRef.current == null) {
      rafRef.current = requestAnimationFrame(() => {
        onFlush(bufferRef.current);
        bufferRef.current = "";
        rafRef.current = null;
      });
    }
  }, [onFlush]);

  return push;
}
```

This caps rendering at 60fps regardless of how fast tokens arrive — at 80 tokens/sec you'd otherwise fire 80 `setState` calls/sec (still usually fine), but at higher rates (parallel tool-call streams, or a fast small model at 200+ tok/s) or with an expensive component tree (markdown re-parse, syntax highlighting per render), this is the difference between smooth and visibly janky. The real production version (see Vercel AI SDK's `useChat` internals) goes further and uses React's `startTransition` to mark the text update as non-urgent, so a concurrent user interaction (typing in a different input, scrolling) doesn't get blocked behind the streaming re-render.

### Backpressure: the part SSE genuinely can't do for you

WebSockets have real backpressure — `ws.bufferedAmount` reports unsent bytes, and a well-behaved server pauses writing when it grows past a threshold (commonly checked against something like 1MB) because TCP's own receive window will stall the socket if the client stops reading. SSE has none of this: the server keeps writing regardless of whether the client's `reader.read()` loop is keeping up, and the browser's own internal stream buffer absorbs the difference until it doesn't. In practice this rarely matters for text token streams (bytes are tiny, tens of KB total per response) but it matters a great deal if you're streaming something heavier over the same connection (base64 image chunks, large tool results) — the mitigation is application-level, not transport-level: chunk large payloads yourself, and if the client's `onDelta` handler is doing something expensive (markdown parsing, syntax highlighting), move that work off the hot path (a Web Worker, or defer it until the buffer flush in the pattern above) rather than doing it synchronously per network chunk.

### Cancellation, correctly

```javascript
const controller = new AbortController();

// kick off the stream
streamChat(messages, { signal: controller.signal, onDelta, onToolCall, onFinish, onError });

// "Stop" button
stopButton.onclick = () => controller.abort();
```

`controller.abort()` does two things: it rejects the pending `fetch()` promise chain with an `AbortError` (caught explicitly above so it doesn't surface as a real error), and — critically — it closes the underlying HTTP connection, which fires `req.on("close")` on the server and is the actual signal the server uses to stop the upstream model call. The mistake that ships to production regularly: aborting the client-side fetch and assuming that's sufficient, without verifying the server actually stops (and stops billing) generation on connection close. Test this specifically — open a stream, abort after 500ms, and check your LLM provider's token usage for that request; if it charges for the full generation, your server isn't wired to the disconnect event.

### Optimistic tool-call rendering

The pattern: render UI for a tool call the instant its `tool-call` event arrives (arguments known, result not yet), then reconcile — not replace — when `tool-result` arrives for the same `toolCallId`.

```javascript
function toolCallReducer(state, event) {
  switch (event.type) {
    case "tool-call":
      return {
        ...state,
        toolCalls: {
          ...state.toolCalls,
          [event.toolCallId]: { name: event.toolName, args: event.args, status: "running", result: null },
        },
      };
    case "tool-result":
      return {
        ...state,
        toolCalls: {
          ...state.toolCalls,
          [event.toolCallId]: { ...state.toolCalls[event.toolCallId], status: "done", result: event.result },
        },
      };
    default:
      return state;
  }
}
```

Keying by `toolCallId` and updating the existing entry (rather than appending a new "tool result" message and letting the UI show two separate cards) is what makes the card animate from "Searching flights..." to "Found 3 flights" instead of flashing a loading card, then a completely separate result card. This is the same reconciliation-over-replacement principle as React's key-based list diffing, applied to application state instead of the DOM.

### A2UI and the agentic-UX vocabulary

Job descriptions increasingly name **A2UI** and "AI-native front-ends," and both map cleanly onto machinery this module already covers — treat them as vocabulary to translate, not new topics. A2UI (Google, late 2025, positioned alongside the A2A protocol) describes agents driving user interfaces through structured output: the model emits a declarative component-tree payload — a card, a form, a chart spec — instead of raw text, and the client renders native components from it. That is generative UI with the tool-call → component contract made explicit, and it runs on exactly the mechanics above: SSE/token streaming carries the deltas, the message-parts model interleaves typed events with text, optimistic tool-call rendering shows intent instantly and reconciles when results land, and agent-to-agent handoffs ride the protocol covered in `T07-a2a-protocol`. The design constraint worth volunteering unprompted: render contracts must be **schema-versioned**, so a client built against component schema v1 keeps working when a server starts emitting v2-era tools — unknown components degrade to a fallback card carrying the raw payload rather than crashing the render tree. It's the same discipline as pinning the stream format and reconciling by id instead of replacing: old clients survive new capabilities by design, not by luck. Answering an A2UI question with those named mechanics, rather than buzzwords, is the senior signal.

---

## Build it from scratch

The runnable core is the server SSE handler plus the client `streamChat` function above — those two, wired together, are a complete token-streaming chat loop with no framework. A minimal lab would: (1) stand up the Node handler streaming from a stub generator (`function* fakeTokens() { yield "Hello"; yield " world"; }` with an artificial `setTimeout` between yields to simulate token latency), (2) build the client reader loop, (3) add the `requestAnimationFrame` buffer, (4) wire an abort button, (5) deliberately break the connection mid-stream (kill the server process) and confirm the client shows a recoverable error rather than hanging silently. Reference: `(lab pending)`.

---

## How it's done in production

Vercel's AI SDK (`ai` package, v6 as of May 2026) wraps all of the above behind `streamText` (server) and `useChat` (client). Server side:

```javascript
// untested sketch — AI SDK v6 shape as of 2026-08
import { streamText } from "ai";
import { anthropic } from "@ai-sdk/anthropic";

export async function POST(req) {
  const { messages } = await req.json();
  const result = streamText({
    model: anthropic("claude-sonnet-4-5"),
    messages,
    tools: { search_flights: searchFlightsTool },
  });
  return result.toUIMessageStreamResponse(); // handles SSE framing, tool events, finish events
}
```

Client side, `useChat` gives you message state, streaming status, and cancellation without hand-rolling the reader loop:

```jsx
import { useChat } from "@ai-sdk/react";

function Chat() {
  const { messages, sendMessage, status, stop } = useChat();
  // messages[i].parts is the message-parts array: text, tool-call, tool-result, reasoning, etc.
  return (
    <>
      {messages.map((m) => (
        <Message key={m.id} parts={m.parts} />
      ))}
      {status === "streaming" && <button onClick={stop}>Stop</button>}
    </>
  );
}
```

What the SDK adds beyond the raw pattern: the message-parts model (a message is `{ id, role, parts: [...] }` where parts can interleave text deltas, tool calls, tool results, and reasoning traces in order — this is what lets you render "thought, then called a tool, then more text" faithfully instead of collapsing everything into one string); automatic reconnection/resumption support for some providers; `onStepFinish`/`onChunk`/`onFinish` lifecycle hooks for multi-step tool-calling agents; and (in v6) the `Agent`/`ToolLoopAgent` abstraction for multi-turn tool loops without hand-writing the loop yourself.

| Symptom | Cause | Fix |
|---|---|---|
| Tab freezes/stutters during fast generation | `setState` (or store update) fired per token, each triggering an expensive re-render (markdown/syntax-highlight re-parse) | Batch updates on `requestAnimationFrame`; defer expensive rendering (syntax highlighting) to idle time or a Web Worker |
| "Stop" button stops the UI but the model keeps generating and billing | Client aborted the `fetch`, but server never wired `req.on("close")` (or framework equivalent) to cancel the upstream provider call | Explicitly cancel the upstream LLM SDK call on server-side disconnect detection |
| Streamed response is silently truncated with no error shown | Reverse proxy (nginx, some CDNs) buffers the response and only flushes it in full, or a load balancer idle-timeout kills the connection during a long tool call with no token output | Disable proxy buffering (`X-Accel-Buffering: no` on nginx), send periodic heartbeat comment lines (`: ping\n\n`) to keep idle connections alive |
| Tool-call card flashes/remounts when the result arrives | Client renders `tool-call` and `tool-result` as two separate list entries instead of reconciling by `toolCallId` | Key state by `toolCallId` and update in place, don't append a second entry |
| Garbled characters (mangled emoji/CJK) appear mid-stream | Multi-byte UTF-8 sequence split across two `read()` chunks, decoded without `{ stream: true }` | Always pass `{ stream: true }` to `TextDecoder.decode()` when consuming a chunked stream |
| Users on flaky mobile connections see the stream just stop | No reconnection/resume logic — a dropped connection mid-generation has no retry path | Persist a stream/message id server-side and support resuming from `Last-Event-ID` or an equivalent cursor, or fall back to "regenerate from here" |

---

## Tradeoffs & when NOT to use it

- **Don't reach for WebSockets by default.** They add real operational cost (sticky sessions or a shared connection store for horizontal scaling, more complex load balancer config, no free CDN/proxy compatibility) for a bidirectional capability that pure token streaming never uses. Use them only when the client genuinely needs to send mid-stream: voice-agent interruption, a mid-generation approval gate, or true multi-user collaboration over the same stream.
- **Don't stream when the response is already fast and short.** A classification call that returns in 200ms with a three-word answer gets nothing from streaming and picks up unnecessary client complexity (partial-state handling, cancellation wiring) for no perceptible UX gain. Streaming earns its complexity when generation genuinely takes multiple seconds.
- **Don't build your own message-parts protocol if you're already committed to a framework's SDK.** Hand-rolling the client reader loop is worth understanding (and worth being able to write in an interview) but reinventing `useChat` in a production app usually means re-solving reconnection, message-part ordering, and tool-call reconciliation bugs the SDK has already hardened.
- **Don't treat `AbortController.abort()` as sufficient cancellation.** It stops the client from rendering; it does not by itself guarantee the server stops incurring cost unless you've verified the server-side disconnect handler actually cancels the upstream call. This is the single most common gap between "looks done" and "actually done" in a streaming chat feature.
- **Don't skip heartbeats on long-running tool calls.** A tool call that takes 45 seconds with no token output in between looks identical to a dead connection to an idle-timing-out proxy or load balancer; silence needs periodic keep-alive frames even when there's nothing to say.

---

## Interview questions

### Q1 — Why is SSE the dominant transport for LLM token streaming instead of WebSockets?
**Testing:** whether the "always use WebSockets for real-time" reflex gets checked against the actual traffic pattern.
**Answer:** Token streaming is one-directional (server produces, client consumes); SSE over HTTP is stateless per-request, requires no sticky sessions to scale horizontally, and works through standard proxies/load balancers/CDNs once buffering is disabled. WebSockets add a persistent, stateful, full-duplex connection for a bidirectional capability that pure token delivery never uses.
**Follow-up trap:** *"When would you actually pick WebSockets?"* — when the client needs to send data mid-stream: voice-agent barge-in/interruption, a mid-generation human-approval gate on a tool call, or true multi-user collaborative state. Saying "never" is as wrong as saying "always."

### Q2 — Why can't you use the browser's native `EventSource` API for an authenticated LLM chat endpoint?
**Testing:** whether the candidate has actually implemented this versus read about SSE abstractly.
**Answer:** `EventSource` only supports GET requests with no custom headers and no request body, so it can't send a POST body (the message history) or an `Authorization` header. Real implementations use `fetch()` with a streamed `ReadableStream` reader and parse the SSE frame format manually.
**Follow-up trap:** *"How do you parse SSE frames from a raw byte stream then?"* — decode chunks with `TextDecoder`, buffer partial frames (split on `\n\n`, keep the last incomplete segment), and use `{ stream: true }` on the decoder to avoid corrupting multi-byte UTF-8 characters split across chunk boundaries.

### Q3 — Your chat UI stutters badly with a fast model but is smooth with a slow one. Diagnose it.
**Testing:** understanding of render cost versus arrival rate, not just "add debouncing."
**Answer:** Per-token `setState` calls each trigger a re-render; if the rendered component tree does expensive work per render (markdown parsing, syntax highlighting) and the model emits tokens faster than that work completes within a 16.7ms frame budget, the main thread falls behind and the tab visibly stutters or freezes. The fix is decoupling arrival rate from render rate — buffer incoming deltas and flush them on `requestAnimationFrame`, and move genuinely expensive rendering off the synchronous per-chunk path.
**Follow-up trap:** *"Why not just throttle to, say, 10 updates/sec with `setTimeout`?"* — a fixed timer either wastes frames when generation is slow or falls further behind when it's fast; `requestAnimationFrame` self-paces to the actual display refresh rate and batches naturally, whereas a fixed interval is a guess that's wrong for the majority of real device/network conditions.

### Q4 — SSE has no backpressure mechanism. What does that actually mean, and does it matter for token streaming?
**Testing:** precision about transport-level versus application-level flow control.
**Answer:** The server has no signal that the client is falling behind and no way for the client to say "slow down" — unlike WebSockets, where `bufferedAmount` and TCP's receive window let a server naturally pause. For plain text tokens this rarely matters in practice (total payload is small), but it matters if something heavier rides the same stream (large tool results, base64 chunks) — the mitigation has to be application-level: chunk large payloads deliberately, keep per-event work cheap, and don't assume the network layer will protect a slow consumer.
**Follow-up trap:** *"So should you switch to WebSockets to get backpressure?"* — no; that's solving a rarely-hit problem by taking on the operational cost of stateful connections everywhere. Fix it at the application layer (payload chunking, deferred rendering) rather than the transport layer.

### Q5 — Walk through what actually happens, end to end, when a user clicks "Stop" mid-generation.
**Testing:** whether cancellation is understood as a full-stack concern, not just a client-side UI state flip.
**Answer:** `controller.abort()` rejects the pending `fetch()` promise (caught as an expected `AbortError`, not a real error) and closes the underlying TCP connection. That connection close fires a `close` event on the server's request object — if and only if the server explicitly listens for it and cancels the upstream LLM provider call there, generation actually stops; otherwise the model keeps generating (and the caller keeps getting billed) even though the client shows nothing.
**Follow-up trap:** *"How would you verify this is actually wired correctly rather than just assuming it works?"* — abort a stream partway through in a test and check the LLM provider's own usage/billing metrics for that request; if it reflects the full generation length rather than a truncated one, the server-side cancellation isn't hooked up.

### Q6 — Design the state shape for a chat message that can contain interleaved text and tool calls, in order.
**Testing:** whether the candidate reaches for a naive string-concatenation model or the parts-array model that matches how generation actually happens.
**Answer:** A message is `{ id, role, parts: [...] }` where `parts` is an ordered array of typed entries — `{type:"text", text}`, `{type:"tool-call", toolCallId, toolName, args, status}`, `{type:"tool-result", toolCallId, result}` — rather than a single string, because a real agent response interleaves "some text, then a tool call, then more text after the result." Collapsing this into one string loses the ordering and the ability to render tool-call cards distinctly from prose.
**Follow-up trap:** *"How do you avoid the tool-call card remounting when its result arrives?"* — key by `toolCallId` and update the existing part in place (reconciliation) rather than appending a second, separate entry for the result — same principle as React's key-based diffing applied to application state.

### Q7 — A proxy in front of your streaming endpoint is silently buffering the whole response instead of flushing it incrementally. How do you diagnose and fix it?
**Testing:** operational awareness beyond the browser — a very common real production failure.
**Answer:** The symptom is the client waiting the full generation time and then receiving everything at once, defeating the purpose of streaming, even though the server is writing incrementally. Common cause: nginx (or another reverse proxy) buffering the upstream response by default. Fix: disable response buffering for the streaming route specifically (`proxy_buffering off` / `X-Accel-Buffering: no` header on nginx), and confirm with a raw `curl -N` against the endpoint directly, bypassing the app, to isolate proxy behavior from client behavior.
**Follow-up trap:** *"How would you catch this in CI before it hits prod?"* — an integration test that asserts chunks arrive incrementally with measurable gaps between them (not all bundled at the end) against the actual deployed proxy config, not just against the app server directly — testing only the app server would pass even with a misconfigured proxy in front of it.

### Q8 — Why send periodic heartbeat/ping comment lines during a long tool call with no token output?
**Testing:** whether the candidate has hit idle-timeout disconnects in practice.
**Answer:** A load balancer or reverse proxy with an idle-connection timeout (commonly 30-60s) can't distinguish "still working, just no output yet" from "dead connection" if nothing is sent — it'll kill the connection mid-tool-call. A `: ping\n\n` comment line (valid SSE syntax, ignored by the client's event parser since it has no `data:` field) sent every ~15s keeps the connection alive through any timeout shorter than that interval.
**Follow-up trap:** *"Does this affect billing or token usage?"* — no, comment lines aren't part of the model's output and cost nothing; they're purely a connection-liveness signal at the transport layer.

### Q9 — What's the actual difference between AI SDK v5 and v6's approach to `useChat`, and why does it matter that you can't mix versions in one render tree?
**Testing:** whether the candidate tracks the ecosystem or is answering from stale/generic knowledge.
**Answer:** v6 (May 2026) moved `useChat`'s message shape to the fully interleaved parts model described above, changed the tool-call streaming lifecycle to expose explicit step hooks, and changed the wire format for a claimed first-token latency improvement. The migration is described as "silent" — old code keeps compiling against the new message shape but consumes it incorrectly — because the breaking change is structural (shape of `messages[i]`), not a renamed export that would fail to compile.
**Follow-up trap:** *"Is that a v6-specific risk or a general lesson?"* — general: fast-moving SDKs around a young pattern (LLM UI streaming) change wire formats and internal state shapes as the pattern matures, so pin versions deliberately, read migration guides rather than assuming semver minor bumps are safe, and don't hardcode assumptions about message internals that the SDK doesn't officially expose as stable API.

### Q10 — How would you implement resumable streaming — a user's connection drops mid-generation on a flaky mobile network, and you want to resume rather than restart from scratch?
**Testing:** staff-level: whether the candidate can extend the basic pattern to handle partial failure gracefully rather than just "show an error."
**Answer:** The server needs to persist generated content against a stream/request id as it's produced (not just stream-and-forget), and the client needs to track the last successfully received position (an SSE `id:` field per event, or an application-level cursor/offset). On reconnect, the client sends the last known id/offset and the server resumes emitting from there (SSE natively supports this via the `Last-Event-ID` header with `EventSource`, but since chat streaming uses `fetch()` instead, this has to be reimplemented at the application level — send the cursor as a request parameter and have the server replay from its persisted buffer).
**Follow-up trap:** *"What if the model itself can't resume mid-generation, only replay what's already been generated?"* — then "resume" really means "reconnect and replay already-generated content instantly, then continue new generation from where the model actually is" — the server must buffer/persist output as it's produced specifically to support this, and if it doesn't, the honest fallback is "regenerate from the last complete message" with a clear UI affordance, not a silent, confusing partial state.

### Q11 — Why is `TextDecoder`'s `{ stream: true }` option specifically necessary here, and what breaks without it?
**Testing:** low-level correctness understanding, not just high-level architecture.
**Answer:** UTF-8 encodes some characters (emoji, many CJK characters) across multiple bytes, and network chunk boundaries don't respect character boundaries — a 4-byte emoji can be split 2 bytes in one `read()` call and 2 in the next. Without `{ stream: true }`, each `decode()` call treats its input as complete and replaces an incomplete trailing byte sequence with the U+FFFD replacement character, corrupting the text. With `{ stream: true }`, the decoder holds incomplete trailing bytes in internal state and prepends them to the next chunk.
**Follow-up trap:** *"Would you catch this in testing with typical English-language test fixtures?"* — no, plain ASCII text never exercises this path since every character is one byte; it requires test fixtures that include multi-byte characters (emoji, non-Latin scripts) deliberately positioned near expected chunk boundaries to catch, which is exactly why this bug ships silently to production and then reproduces only for specific users/content.

### Q12 — At the systems level, what determines the token arrival rate the client has to keep up with, and how would you find the actual number for a given deployment?
**Testing:** staff-level: connecting frontend rendering budget to backend serving characteristics, not treating token rate as a given constant.
**Answer:** Token generation rate is a function of the model size, batch size/concurrency on the serving side, hardware, and decoding strategy (e.g., speculative decoding can meaningfully raise effective tokens/sec) — it is not a frontend-controlled number and varies by provider, model tier, and load. To find the real number for a given deployment: instrument the client to log timestamped `onDelta` calls, compute inter-arrival intervals under realistic load, and design the render buffer/backpressure strategy against the observed p95, not an assumed constant, because production token rates under concurrent load are frequently different (often slower, sometimes burstier) than an unloaded local test suggests.
**Follow-up trap:** *"Would you design the same buffering strategy for a 20 tok/s model and a 150 tok/s model?"* — no; at 20 tok/s naive per-token `setState` is usually fine and adding a buffer is unnecessary complexity, while at 150+ tok/s (or with an expensive render tree) the `requestAnimationFrame` batching becomes necessary — the right answer is "measure first," which is the same discipline the web-performance module insists on for Core Web Vitals work generally.

---

## Red flags that fail you

- Defaulting to WebSockets for chat token streaming "because it's more real-time," without being able to name what bidirectional capability is actually being used.
- Claiming `AbortController.abort()` alone stops server-side model generation and billing, without mentioning the server needs to listen for the disconnect.
- Not knowing why `EventSource` can't be used directly for an authenticated POST-based chat API.
- Rendering tool-call results by appending a new message instead of reconciling the existing tool-call entry by id.
- Assuming SSE has backpressure equivalent to WebSockets/TCP flow control.
- Treating a proxy silently buffering the whole stream as a client-side bug and debugging the wrong layer.

---

## Cheat card

```
TRANSPORT: SSE over fetch() POST (not EventSource — can't POST/set headers) for
  one-directional token delivery. WebSocket only if client must send mid-stream
  (interruption, approval gate, collab).

SSE FRAME: "data: {...}\n\n" per event, blank line = frame boundary. Frames can
  split across TCP packets — buffer + split("\n\n") + keep last partial segment.

BACKPRESSURE: SSE has NONE at transport level (unlike WS's bufferedAmount / TCP
  window). Mitigate at app layer: chunk large payloads, defer expensive render work.

RENDER: batch token deltas via requestAnimationFrame (60Hz budget = 16.7ms/frame),
  don't setState per token if render tree does markdown/syntax-highlight work.

CANCEL: AbortController.abort() -> fetch rejects (AbortError, expected) + TCP
  connection closes -> server MUST listen (req.on('close')) and cancel upstream
  model call there, or generation keeps running/billing after UI stops.

DECODE: TextDecoder.decode(chunk, {stream:true}) — without stream:true, multi-byte
  UTF-8 chars split across chunks get corrupted (replacement char).

TOOL-CALL UI: render on tool-call event (args known, result pending), reconcile
  (not append) by toolCallId when tool-result arrives — avoids remount/flash.

PROXY GOTCHA: nginx/some CDNs buffer full response by default -> streaming looks
  broken (all-at-once). Fix: X-Accel-Buffering: no / proxy_buffering off.

HEARTBEAT: send ": ping\n\n" every ~15s during silent long tool calls — idle
  load balancer timeouts (~30-60s typ.) will kill an otherwise-healthy connection.

VERCEL AI SDK: v6 (May 2026) — message-parts model on useChat (text/tool-call/
  tool-result/reasoning interleaved in order), streamText().toUIMessageStreamResponse(),
  Agent/ToolLoopAgent abstraction. v5->v6 message shape change is a SILENT break
  (still compiles, wrong structure) — don't mix v5/v6 in one render tree.

TOKEN RATE: not a frontend constant — function of model/batch/hardware/decoding
  strategy (~20-100+ tok/s typical hosted chat models, varies by load). Measure
  real inter-arrival p95 before choosing a buffering strategy.
```

## Sources

- [AI SDK 5 — Vercel](https://vercel.com/blog/ai-sdk-5) — accessed 2026-08-02
- [Vercel AI SDK v5 to v6 Migration Playbook for 2026](https://www.digitalapplied.com/blog/vercel-ai-sdk-v5-to-v6-migration-playbook-2026) — accessed 2026-08-02
- [Vercel AI SDK 6 Deep Dive: Features + Tool Calls 2026](https://www.digitalapplied.com/blog/vercel-ai-sdk-6-deep-dive-features-tool-calls-2026) — accessed 2026-08-02
- [AI Token Streaming: From SSE to Durable Sessions — WebSocket.org](https://websocket.org/guides/use-cases/ai-streaming/) — accessed 2026-08-02
- [Streaming for LLM Apps: SSE vs WebSockets — Hivenet](https://www.hivenet.com/post/llm-streaming-sse-websockets) — accessed 2026-08-02
- [How do you abort a web request using AbortController in JavaScript? — GreatFrontEnd](https://www.greatfrontend.com/questions/quiz/how-do-you-abort-a-web-request-using-abortcontrollers) — accessed 2026-08-02
- MDN — Server-Sent Events, ReadableStream, TextDecoder (stream option), AbortController — living reference docs

## Changelog
- 2026-08-02 — created
