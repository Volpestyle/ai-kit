# inference-kit (Node)

Provider-agnostic model registry and inference adapter for Node.js. The SDK includes a Hub
for list/generate/stream, a model router, SSE helpers, and HTTP handler utilities.

## Quickstart
```bash
pnpm add @volpestyle/inference-kit-node
```
```ts
import { createHub, Provider } from "@volpestyle/inference-kit-node";

const hub = createHub({
  providers: {
    [Provider.OpenAI]: { apiKey: process.env.OPENAI_API_KEY ?? "" },
  },
});

const output = await hub.generate({
  provider: Provider.OpenAI,
  model: "gpt-4o-mini",
  messages: [{ role: "user", content: [{ type: "text", text: "Hello" }] }],
});

console.log(output.text);
```

## Examples
### Stream tokens in-process
```ts
for await (const chunk of hub.streamGenerate({
  provider: Provider.OpenAI,
  model: "gpt-4o-mini",
  messages: [{ role: "user", content: [{ type: "text", text: "Stream" }] }],
  stream: true,
})) {
  if (chunk.type === "delta") {
    process.stdout.write(chunk.textDelta);
  }
}
```

### HTTP handlers with SSE
```ts
import express from "express";
import { createHub, httpHandlers, Provider } from "@volpestyle/inference-kit-node";

const app = express();
app.use(express.json());

const hub = createHub({
  providers: {
    [Provider.OpenAI]: { apiKey: process.env.OPENAI_API_KEY ?? "" },
  },
});

const handlers = httpHandlers(hub);
app.get("/provider-models", handlers.models());
app.post("/generate", handlers.generate());
app.post("/generate/stream", handlers.generateSSE());

app.listen(3000);
```
