# INC-008 — Accessible political themes and manual accessibility evidence

## Problem

The interface exposes four unlabeled accent dots and one generic dark surface. Color selection lacks product meaning, premium entitlement behavior is absent, and automated semantics are not accompanied by a repeatable accessibility evidence protocol.

## Purpose

Provide four accessible, politically neutral visual themes (blue, red, green and orange), expose a premium theme only behind an explicit paid-entitlement contract, and create repeatable automated/manual evidence for keyboard, contrast, zoom/reflow and reduced motion.

## Actors

- non-technical campaign operator choosing a familiar visual identity;
- tenant administrator managing paid capabilities;
- keyboard and screen-reader user;
- accessibility and release reviewer.

## Invariants

- Theme color never grants, implies or changes political or application authority.
- Status, risk, permissions and Greenlight are never communicated by theme color alone.
- Free themes are available without authentication or persistence.
- Premium cannot activate without a server-derived entitlement input.
- No payment, billing or entitlement is fabricated by the frontend.
- Theme selection never stores credentials or creates an external effect.

## Functional requirements

- FR-001: expose blue, red, green and orange as named free themes.
- FR-002: expose premium with a visible paid-entitlement explanation.
- FR-003: keep premium focusable/discoverable but fail closed when entitlement is false.
- FR-004: represent current selection with text and `aria-pressed`, not color alone.
- FR-005: apply semantic background, panel, text, muted, border, accent and on-accent tokens.
- FR-006: preserve selection through component updates without browser storage.
- FR-007: use View Transition only when supported and reduced motion is not requested.
- FR-008: announce selection or locked-premium result through a polite live region.
- FR-009: maintain at least 4.5:1 normal-text contrast and 3:1 focus/non-text contrast for every available theme token pair.
- FR-010: provide a reviewer checklist for 320 CSS px, 400% zoom, keyboard, screen reader and motion.

## States

`selected`, `available`, `premium_locked`, `premium_entitled`, `reduced_motion`, `transition_supported`, `transition_unavailable`.

## Acceptance criteria

- catalog tests verify IDs, labels, entitlement behavior and contrast ratios;
- component tests verify keyboard activation, `aria-pressed`, locked premium and reduced-motion behavior;
- application tests verify semantic tokens and `data-theme` application;
- full frontend, package and supply-chain regression pass;
- manual checklist records environment, observed result and limitations without overclaim.

## Out of scope

- payment processing;
- billing provider integration;
- server entitlement endpoint;
- partisan recommendations or political authority;
- declaring manual assistive-technology completion without a human/browser session.
