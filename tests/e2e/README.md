# End-to-end tests

Reserved for future Playwright/Cypress flows that drive the web UI:

1. Open `/upload`.
2. Drop a sample PDF.
3. Watch the SSE event stream populate.
4. Open `/pages/<page-id>/review`.
5. Verify the CAD overlay renders at least one primitive.
6. Trigger export and download the ZIP.
