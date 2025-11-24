# Implementation Plan - Phase 5D: Testing & Verification

## Goal
Verify the core functionality of the Insurance MCP system by executing the existing End-to-End integration tests and the Golden Dataset evaluation.

## User Review Required
> [!NOTE]
> This plan involves running existing tests. No new code creation is required unless tests fail.

## Proposed Changes

### Verification Execution
#### [EXECUTE] [test_end_to_end.py](file:///Users/shushu/insurance-mcp/tests/integration/test_end_to_end.py)
- Run the end-to-end workflow test which mocks external dependencies (OpenAI) to verify the pipeline logic (Post-processing -> Indexing -> Retrieval -> MCP Tool).

#### [EXECUTE] [test_retrieval_quality.py](file:///Users/shushu/insurance-mcp/tests/integration/test_retrieval_quality.py)
- Run the Golden Dataset evaluation against the `phase5_test_set_full.json`.
- **Note**: This test requires a populated ChromaDB with actual data. If the DB is empty, we may need to run the crawler/processor first or use a mock fixture.

## Verification Plan

### Automated Tests
1. **Run End-to-End Test**:
   ```bash
   pytest tests/integration/test_end_to_end.py -v
   ```

2. **Run Golden Dataset Evaluation**:
   ```bash
   pytest tests/integration/test_retrieval_quality.py -v
   ```
