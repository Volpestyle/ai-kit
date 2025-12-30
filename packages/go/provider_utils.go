package aikit

import (
	"context"
	"encoding/base64"
	"fmt"
	"io"
	"net/http"
	"strings"
)

func imageInputToDataURL(input ImageInput) string {
	if strings.TrimSpace(input.URL) != "" {
		return input.URL
	}
	if strings.TrimSpace(input.Base64) == "" {
		return ""
	}
	mime := strings.TrimSpace(input.MediaType)
	if mime == "" {
		mime = "image/png"
	}
	return fmt.Sprintf("data:%s;base64,%s", mime, input.Base64)
}

func parseDataURL(raw string) (mime string, data string, ok bool) {
	if !strings.HasPrefix(raw, "data:") {
		return "", "", false
	}
	parts := strings.SplitN(raw, ",", 2)
	if len(parts) != 2 {
		return "", "", false
	}
	meta := strings.TrimPrefix(parts[0], "data:")
	mime = strings.SplitN(meta, ";", 2)[0]
	if mime == "" {
		mime = "image/png"
	}
	return mime, parts[1], true
}

func fetchURLAsBase64(ctx context.Context, client *http.Client, rawURL string) (mime string, data string, err error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, rawURL, nil)
	if err != nil {
		return "", "", err
	}
	resp, err := client.Do(req)
	if err != nil {
		return "", "", err
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 400 {
		body, _ := io.ReadAll(resp.Body)
		return "", "", &KitError{
			Kind:           classifyStatus(resp.StatusCode),
			Message:        string(body),
			UpstreamStatus: resp.StatusCode,
		}
	}
	payload, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", "", err
	}
	mime = resp.Header.Get("Content-Type")
	if mime == "" {
		mime = "image/png"
	}
	data = base64.StdEncoding.EncodeToString(payload)
	return mime, data, nil
}

func isHTTPURL(raw string) bool {
	return strings.HasPrefix(raw, "http://") || strings.HasPrefix(raw, "https://")
}
