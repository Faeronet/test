// dev_seed seeds a couple of empty batches so the UI has something to show on
// a brand-new install. Run with:  go run scripts/dev_seed.go
package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"time"
)

func main() {
	api := os.Getenv("API_URL")
	if api == "" {
		api = "http://localhost:8080"
	}
	for _, name := range []string{"sample-batch-A", "sample-batch-B"} {
		body, _ := json.Marshal(map[string]string{"name": name})
		resp, err := http.Post(api+"/api/batches", "application/json", bytes.NewReader(body))
		if err != nil {
			fmt.Fprintln(os.Stderr, "post:", err)
			os.Exit(1)
		}
		_ = resp.Body.Close()
		fmt.Printf("seeded %s @ %s\n", name, time.Now().Format(time.RFC3339))
	}
}
