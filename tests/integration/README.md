# Integration tests

Run with `bash scripts/run_local_pipeline.sh` after `make up`. The script
generates a synthetic A4 drawing, uploads it, and waits for the page to
reach the `exported` state. The resulting DXF can be downloaded from the
batch page in the web UI.

For more elaborate fixtures, drop PDFs/images/archives into
`tests/fixtures/sample_inputs/` and pass the path to
`scripts/create_test_batch.sh`.
