# Cloudflare Registrar Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox syntax for tracking.

**Goal:** Implement src/services/cloudflare_com/registrar.py and register CLOUDFLARE service so it can auto-signup Cloudflare accounts via testmail.app, verify email, skip onboarding, and create an AI token.

**Architecture:** Single FP module mirroring openrouter_ai/registrar.py; functions split by responsibility: form fill, Turnstile click, email verification, onboarding skip, token creation, credential extraction. Registry wires it into the job dispatcher.

**Tech Stack:** Python 3.11, Playwright (camoufox), testmail.app, FP style.

---

### Task 1: Add Cloudflare registrar module

**Files:**
- Create: src/services/cloudflare_com/registrar.py
- Modify: src/services/cloudflare_com/__init__.py (if needed to export)

- [ ] Step 1: Scaffolding and imports
- [ ] Step 2: Signup form fill
- [ ] Step 3: Turnstile click
- [ ] Step 4: Submit and ignore fake onboarding
- [ ] Step 5: Wait for verification email
- [ ] Step 6: Navigate verify link and skip onboarding
- [ ] Step 7: Extract account_id and navigate to token create page
- [ ] Step 8: Create API token with AI permissions
- [ ] Step 9: Save account record

### Task 2: Register service in registry

**Files:**
- Modify: src/services/registry.py

- [ ] Step 1: Add _make_cloudflare factory
- [ ] Step 2: Add to _FACTORIES
- [ ] Step 3: Verify make_registrar resolves

### Task 3: Config file

**Files:**
- Create: config/cloudflare.yaml

- [ ] Step 1: Add default URLs and timeouts

### Task 4: Tests

**Files:**
- Create: tests/unit/registrars/test_cloudflare.py

- [ ] Step 1: Registry resolve test
- [ ] Step 2: Config load test
- [ ] Step 3: Linter pass

### Task 5: Verification

- [ ] Run unit tests
- [ ] Run smoke imports
- [ ] Run registry-related tests