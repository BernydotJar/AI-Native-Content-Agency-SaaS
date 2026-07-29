# Accessible campaign themes

## Product boundary

Themes provide visual familiarity for campaign operators. They never encode party affiliation, authority, risk, approval, Greenlight state or political recommendation. Every operational state retains text, iconography and semantic roles independent of color.

The application has no billing or payment-provider integration. Premium access is instead derived from the exact server-owned `theme:premium` entitlement on the active individual identity. The entitlement is returned by the HttpOnly session contract and revalidated on each session-authenticated request; removing it from the active identity revokes access on the next request. Client storage, URL parameters and role labels never grant it. Without an authenticated entitled session, the premium control remains focusable, explained and fail-closed.

The theme implementation is a product entitlement boundary, not digital-rights management: CSS and frontend source are inspectable by a browser user. The authoritative guarantee is that the supported UI does not activate premium without a current server-issued entitlement. Billing, checkout, invoicing and subscription lifecycle remain unimplemented external systems.

## Catalog

| ID | Tier | Accent | Background | Panel | On-accent |
|---|---|---:|---:|---:|---:|
| `blue` | free | `#60a5fa` | `#070b12` | `#0b1220` | `#09090b` |
| `red` | free | `#fb7185` | `#10080b` | `#1c0d13` | `#09090b` |
| `green` | free | `#4ade80` | `#07100b` | `#0b1c12` | `#09090b` |
| `orange` | free | `#fdba74` | `#120c07` | `#20140a` | `#09090b` |
| `premium` | paid entitlement | `#c4b5fd` | `#0d0a16` | `#18112a` | `#09090b` |

Shared foreground is `#f4f4f5`; shared muted text is `#a1a1aa`. The executable catalog in `src/lib/themeCatalog.ts` is authoritative.

## Semantic tokens

`applyTheme` writes these document-level properties:

- `--bg-obsidian`
- `--bg-panel`
- `--bg-panel-solid`
- `--text-light`
- `--text-muted`
- `--theme-border`
- `--theme-accent-foreground`
- `--primary-color`
- `--primary-color-raw`
- `--primary-color-glow`
- `--border-cyber`
- `--border-cyber-focus`

Components must consume semantic variables for primary surfaces and focus. A component must not infer permission, safety or status from `data-theme`.

## Contrast contract

Automated tests require:

- normal text/background at least `7:1` for the primary text pair;
- muted text/background at least `4.5:1`;
- accent/background at least `4.5:1`;
- on-accent/accent at least `4.5:1`;
- accent/panel at least `3:1` for non-text and focus distinction.

These calculations support but do not replace rendered-page contrast review.

## Interaction contract

- five named buttons are exposed in one fieldset;
- the active theme uses `aria-pressed=true` and visible text;
- premium uses `aria-disabled=true` while remaining focusable and explanatory;
- Enter and Space activate available themes;
- locked premium announces why activation was refused;
- View Transition is used only when supported and `prefers-reduced-motion` is not `reduce`;
- selection is in-memory only and never written to browser storage.

## Evidence

`npm run verify:accessibility-browser` uses a real Chromium accessibility tree and a 320 CSS px viewport to verify:

- no horizontal reflow overflow;
- 44 CSS px minimum theme targets;
- skip link first and focus transfer to `main`;
- keyboard theme activation;
- premium lock;
- reduced-motion behavior;
- accessible names, pressed state and disabled state.

Generated JSON and screenshot artifacts are intentionally ignored locally and uploaded by CI for later human review. This gate is not a human screen-reader certification.
