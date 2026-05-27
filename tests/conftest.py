"""Pytest configuration for the talent-agent test suite.

The `_legacy/` directory holds tests for the pre-refactor `talent_agent.*`
package (now superseded by `backend/app/`). They reference modules that no
longer exist and would break collection, so they are excluded here until
someone ports them. See reviews/2026-05-28_*.md (item N3 / M4) for context.
"""

collect_ignore_glob = ["_legacy/*"]
