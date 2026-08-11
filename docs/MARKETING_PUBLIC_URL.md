# Marketing public URL

## Purpose

The marketing surface is a public, interactive demonstration of CampaignOS. It is built
as static files and deliberately **does not expose** tenant credentials, private runtime
sessions, provider secrets, database access, social OAuth, paid-media authority, or real
publication effects.

Canonical URL after the GitHub Pages deployment succeeds:

```text
https://bernydotjar.github.io/AI-Native-Content-Agency-SaaS/
```

## Public experience

The Pages build sets:

```text
VITE_PUBLIC_MARKETING_DEMO=true
```

That mode is intentionally different from the authenticated product runtime:

- no session is restored or created;
- no `/api` request is required to use the demo;
- the radar uses clearly labelled local sample signals rather than pretending to fetch
  live trends;
- visitors can edit a mission and run a **simulación local** of all eight stations;
- the local run produces representative artifacts and review state with
  `external_side_effects_enabled=false`;
- publishing, OAuth, provider execution, credentials and private runs remain unavailable;
- appearance/theme controls continue to work locally;
- the UI explicitly labels the surface as `Demo pública` and the private runtime as
  isolated.

This makes the marketing URL useful rather than presenting a disabled login screen,
while keeping the security boundary honest.

## Deployment

`.github/workflows/deploy-marketing-site.yml` validates pull requests and builds the
React/Vite frontend on pushes to `main`. Pull requests run the complete lint, test,
marketing build and artifact contract but never deploy. A push to `main` additionally
configures/uploads the Pages artifact and deploys it through the `github-pages`
environment.

The workflow uses GitHub Actions pinned to full commit SHAs and the repository-scoped
`GITHUB_TOKEN`. It does not require Firebase, Google Cloud credentials, a service-account
key, Firestore, PostgreSQL, or any other database for the public marketing surface.

The Vite build uses the project-site base path:

```text
/AI-Native-Content-Agency-SaaS/
```

so JS, CSS and the favicon resolve correctly below the repository subpath rather than at
the `bernydotjar.github.io` origin root.

## Pages enablement and release gate

The deploy job uses `actions/configure-pages` with `enablement: true`, so the first
authorized deployment can create/configure the GitHub Pages site as a workflow-backed
site. No separate Firebase or cloud credential is required.

Publishing still obeys the repository release decision. Pull requests always run the
full static demo build, but pushes to `main` must additionally pass:

```bash
python3 scripts/verify-marketing-release-authority.py
```

Today `compliance/release-decision.json` remains `DENY_RELEASE`, so the public deployment
is intentionally blocked until the named legal/privacy, accessibility, staging and
independent-review gates are resolved. A merge must not silently convert that governance
state into a public release.

No custom domain is required for the canonical URL above.

## Verification

Source contract, with no Node installation required:

```bash
python3 scripts/verify-marketing-public-url.py
```

Full pull-request/build gate:

```bash
npm ci --no-audit --no-fund
npm run lint
npm test
VITE_PUBLIC_MARKETING_DEMO=true npm run build -- --base /AI-Native-Content-Agency-SaaS/
python3 scripts/verify-marketing-public-url.py --dist dist
CHROMIUM_BIN="$(command -v chromium || command -v google-chrome || command -v google-chrome-stable)" \
  node scripts/verify-marketing-public-browser.mjs
```

### Search crawling note

`public/robots.txt` is copied into the project subpath for transparency, but a GitHub
Pages project site cannot place that file at the host root
`https://bernydotjar.github.io/robots.txt`. Search engines that require host-root
`robots.txt` therefore will not treat the project-subpath copy as authoritative. The
page-level `meta robots`, canonical URL and `sitemap.xml` remain the applicable controls
for this project site. A future custom domain or user-site root can provide a true
host-root `robots.txt`.

After deployment:

```bash
curl -fsSI https://bernydotjar.github.io/AI-Native-Content-Agency-SaaS/
curl -fsS https://bernydotjar.github.io/AI-Native-Content-Agency-SaaS/robots.txt
curl -fsS https://bernydotjar.github.io/AI-Native-Content-Agency-SaaS/sitemap.xml
```

The authoritative deployment URL is also recorded by the `github-pages` environment.

## Firebase decision

Firebase Hosting remains a valid later facade if a custom domain, preview channels, or
same-origin rewrites to Cloud Run become actual requirements. Firestore is deliberately
not introduced for this marketing surface: the private application runtime already has
governed PostgreSQL persistence, and duplicating product state solely to obtain a public
URL would increase consistency and security scope without improving the static demo.

## Production boundary

This public URL is a marketing/demo endpoint, not the authenticated production control
plane. A future public application runtime must independently retain authentication,
RBAC, CSRF/session protections, durable PostgreSQL state, audit evidence, Greenlight
fencing, rate limits and effect-specific authority checks. The static Pages deployment
grants none of those authorities.
