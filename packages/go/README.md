# inference-kit (Go)

Provider-agnostic model registry and inference adapter for Go. Includes a Hub, model router,
SSE streaming, and HTTP handlers for a small REST surface.

## Quickstart
```bash
go get github.com/Volpestyle/inference-kit/packages/go
```
```go
package main

import (
  "context"
  "fmt"
  "os"

  inferencekit "github.com/Volpestyle/inference-kit/packages/go"
)

func main() {
  hub, err := inferencekit.New(inferencekit.Config{
    OpenAI: &inferencekit.OpenAIConfig{APIKey: os.Getenv("OPENAI_API_KEY")},
  })
  if err != nil {
    panic(err)
  }

  out, err := hub.Generate(context.Background(), inferencekit.GenerateInput{
    Provider: inferencekit.ProviderOpenAI,
    Model:    "gpt-4o-mini",
    Messages: []inferencekit.Message{{
      Role: "user",
      Content: []inferencekit.ContentPart{{
        Type: "text",
        Text: "Hello",
      }},
    }},
  })
  if err != nil {
    panic(err)
  }

  fmt.Println(out.Text)
}
```

## Examples
### HTTP handlers with SSE
```go
import (
  "net/http"

  inferencekit "github.com/Volpestyle/inference-kit/packages/go"
)

hub, _ := inferencekit.New(inferencekit.Config{
  OpenAI: &inferencekit.OpenAIConfig{APIKey: os.Getenv("OPENAI_API_KEY")},
})

http.HandleFunc("/provider-models", inferencekit.ModelsHandler(hub, nil))
http.HandleFunc("/generate", inferencekit.GenerateHandler(hub))
http.HandleFunc("/generate/stream", inferencekit.GenerateSSEHandler(hub))
http.ListenAndServe(":3000", nil)
```

### Route to a preferred model
```go
router := &inferencekit.ModelRouter{}
records, _ := hub.ListModelRecords(context.Background(), nil)
resolved, _ := router.Resolve(records, inferencekit.ModelResolutionRequest{
  Constraints: inferencekit.ModelConstraints{RequireTools: true},
  PreferredModels: []string{"openai:gpt-4o-mini"},
})

_ = resolved.Primary
```
