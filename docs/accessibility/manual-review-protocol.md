# Manual accessibility review protocol

This protocol creates evidence; it does not treat automated tests as manual certification.

## Required environment record

- commit and deployed/local URL;
- browser and version;
- operating system;
- assistive technology and version;
- viewport and device pixel ratio;
- reviewer and timestamp.

## Keyboard

1. Start at the address bar and press Tab.
2. Confirm the skip link is the first application control and moves focus to `main`.
3. Traverse theme choices, mission profiles, forms, pipeline nodes, inspector tabs, runtime session, run lookup, audit refresh and Greenlight controls.
4. Confirm visible focus, logical order, no trap and no unreachable action.
5. Activate each free theme with Enter and Space.
6. Confirm premium remains discoverable, explains its lock and does not activate without entitlement.

## Screen reader

1. Navigate by landmarks and headings.
2. Confirm theme group name, theme name, selected state and premium lock are announced.
3. Confirm loading, empty, error, rate-limit, conflict and session-expired states are announced once with appropriate urgency.
4. Confirm decorative canvas, noise, icons and topology do not add noise.
5. Confirm form labels, validation and audit items have useful names.

## Zoom and reflow

1. Set viewport to 1280 CSS px and zoom to 400% (effective 320 CSS px).
2. Confirm no horizontal page scroll, clipped text or obscured control.
3. Confirm controls remain at least 44 CSS px in their primary dimension where applicable.
4. Confirm theme labels and entitlement explanation remain visible.

## Contrast

Use a contrast analyzer against the rendered tokens and representative controls. Record foreground/background pairs and ratios. Theme catalog automation is supporting evidence only.

## Reduced motion

1. Enable the OS/browser reduced-motion preference.
2. Change themes and run the simulator.
3. Confirm no circular View Transition, decorative canvas animation or repeated pulse is required to understand state.
4. Confirm state changes remain visible through text.

## Evidence format

```yaml
commit:
url:
browser:
os:
assistive_technology:
reviewer:
timestamp:
keyboard: PASS | FAIL | NOT_RUN
screen_reader: PASS | FAIL | NOT_RUN
contrast: PASS | FAIL | NOT_RUN
zoom_reflow: PASS | FAIL | NOT_RUN
reduced_motion: PASS | FAIL | NOT_RUN
findings:
limitations:
artifacts:
```
