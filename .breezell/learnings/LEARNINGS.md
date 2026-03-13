# Learnings

Captured learnings, corrections, and best practices for this project.

---

## [LRN-20260313-351] best_practice

**Logged**: 2026-03-13T02:22:06.639Z
**Priority**: low
**Status**: pending
**Area**: infra

### Summary
review_learnings may fail due to truncation even with empty params.

### Details
review_learnings tool repeatedly failed with 'parameters too large/truncated' even with empty parameters. Suggest avoiding repeated attempts; consider smaller payloads or omit if tool is unreliable.

### Suggested Action
Avoid repeated review_learnings retries when tool truncation persists; proceed without it unless required.

### Metadata
- Source: conversation
- Related Files: .breezell/learnings

---

## [LRN-20260313-176] correction

**Logged**: 2026-03-13T02:22:21.509Z
**Priority**: low
**Status**: pending
**Area**: infra

### Summary
Path correction: avoid duplicated AimiGuard\AimiGuard when editing files.

### Details
Incorrectly attempted apply_diff on README.md using duplicated path AimiGuard\AimiGuard, causing file-not-found error. Correct path is c:\Users\Administrator\Desktop\AimiGuard\README.md.

### Suggested Action
Verify workspace root and avoid duplicating top-level folder names in paths before edits.

### Metadata
- Source: conversation
- Related Files: README.md

---
