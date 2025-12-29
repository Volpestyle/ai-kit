# Deterministic testing

ai-kit ships fixture adapters so consuming apps can test without live provider calls.
Each SDK lets you inject adapters into the Kit configuration, plus helpers to derive
fixture keys from inputs.

## How it works
- Build a fixture map keyed by a deterministic hash of the input.
- Inject a `FixtureAdapter` for the provider you want to stub.
- Use `buildStreamChunks`/`build_stream_chunks` or explicit stream fixtures for SSE tests.

## Node.js
```ts
import { createKit, Provider } from "@volpestyle/ai-kit-node";
import {
  FixtureAdapter,
  buildStreamChunks,
  createFixtureKey,
} from "@volpestyle/ai-kit-node/testing";

const input = {
  provider: Provider.OpenAI,
  model: "gpt-4o-mini",
  messages: [{ role: "user", content: [{ type: "text", text: "Hello" }] }],
};

const key = createFixtureKey({ type: "generate", input });

const adapter = new FixtureAdapter({
  provider: Provider.OpenAI,
  models: [
    {
      id: "gpt-4o-mini",
      displayName: "gpt-4o-mini",
      provider: Provider.OpenAI,
      family: "gpt",
      capabilities: {
        text: true,
        vision: false,
        tool_use: false,
        structured_output: false,
        reasoning: false,
      },
    },
  ],
  fixtures: {
    [key]: {
      generate: { text: "Hello from fixtures." },
      stream: buildStreamChunks({ text: "Hello from fixtures." }, 12),
    },
  },
});

const kit = createKit({
  providers: {},
  adapters: {
    [Provider.OpenAI]: adapter,
  },
});

const output = await kit.generate(input);
```

## Go
```go
package main

import (
  "context"

  aikit "github.com/Volpestyle/ai-kit/packages/go"
  "github.com/Volpestyle/ai-kit/packages/go/testkit"
)

func main() {
  input := aikit.GenerateInput{
    Provider: aikit.ProviderOpenAI,
    Model:    "gpt-4o-mini",
    Messages: []aikit.Message{{Role: "user", Content: []aikit.ContentPart{{Type: "text", Text: "Hello"}}}},
  }

  key := testkit.GenerateKey(input)
  adapter := &testkit.FixtureAdapter{
    Provider: aikit.ProviderOpenAI,
    Fixtures: map[string]testkit.Fixture{
      key: {
        Generate: &aikit.GenerateOutput{Text: "Hello from fixtures."},
      },
    },
  }

  kit, _ := aikit.New(aikit.Config{
    Adapters: map[aikit.Provider]aikit.ProviderAdapter{
      aikit.ProviderOpenAI: adapter,
    },
  })

  _, _ = kit.Generate(context.Background(), input)
}
```

## Python
```py
from ai_kit import Kit, KitConfig, GenerateInput, GenerateOutput, Message, ContentPart
from ai_kit.testing import FixtureAdapter, FixtureEntry, FixtureKeyInput, fixture_key

input = GenerateInput(
    provider="openai",
    model="gpt-4o-mini",
    messages=[Message(role="user", content=[ContentPart(type="text", text="Hello")])],
)

key = fixture_key(FixtureKeyInput(type="generate", input=input))
adapter = FixtureAdapter(
    provider="openai",
    fixtures={
        key: FixtureEntry(generate=GenerateOutput(text="Hello from fixtures."))
    },
)

kit = Kit(KitConfig(providers={}, adapters={"openai": adapter}))
output = kit.generate(input)
```

## Notes
- `adapters` overrides built-in providers for the same key.
- `adapterFactory`/`adapter_factory` lets you plug in dynamic adapters (for example, per-tenant fixtures).
- If you need precise streaming or tool-call behavior, supply `stream` fixtures directly.
