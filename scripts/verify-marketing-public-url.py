#!/usr/bin/env python3
"""Fail-closed verifier for the public GitHub Pages marketing surface."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_NAME = "AI-Native-Content-Agency-SaaS"
BASE_PATH = f"/{REPO_NAME}/"
CANONICAL = f"https://bernydotjar.github.io/{REPO_NAME}/"

EXPECTED_ACTIONS = (
    "actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803",
    "actions/setup-node@a0853c24544627f65ddf259abe73b1d18a591444",
    "actions/configure-pages@983d7736d9b0ae728b81ab479565c72886d7745b",
    "actions/upload-pages-artifact@7b1f4a764d45c48632c6b24a0339c27f5614fb0b",
    "actions/deploy-pages@d6db90164ac5ed86f2b6aed7e0febac5b3c0c03e",
)


class MarketingContractError(ValueError):
    pass


def text(path: Path) -> str:
    if not path.is_file():
        raise MarketingContractError(f"missing file: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def require(haystack: str, needles: tuple[str, ...], label: str) -> None:
    missing = [needle for needle in needles if needle not in haystack]
    if missing:
        raise MarketingContractError(f"{label}: missing {missing}")


def verify_source() -> None:
    workflow = text(ROOT / ".github/workflows/deploy-marketing-site.yml")
    index = text(ROOT / "index.html")
    app = text(ROOT / "src/App.tsx")
    workspace = text(ROOT / "src/components/WorkspaceRuntime.tsx")
    output = text(ROOT / "src/components/CampaignOutputPanel.tsx")
    radar = text(ROOT / "src/components/TrendRadar.tsx")
    demo = text(ROOT / "src/lib/publicMarketingDemo.ts")
    robots = text(ROOT / "public/robots.txt")
    sitemap = text(ROOT / "public/sitemap.xml")
    docs = text(ROOT / "docs/MARKETING_PUBLIC_URL.md")

    require(
        workflow,
        (
            "pull_request:",
            "branches: [main]",
            'VITE_PUBLIC_MARKETING_DEMO: "true"',
            f"npm run build -- --base {BASE_PATH}",
            "python3 scripts/verify-marketing-public-url.py --dist dist",
            "python3 scripts/verify-marketing-release-authority.py",
            "enablement: true",
            "if: github.event_name != 'pull_request'",
            "pages: write",
            "id-token: write",
            *EXPECTED_ACTIONS,
        ),
        "Pages workflow",
    )
    if re.search(r"uses:\s+[^\s]+@(v\d+|main|master)\b", workflow):
        raise MarketingContractError("Pages workflow contains a mutable action reference")

    require(
        index,
        (
            f'<link rel="canonical" href="{CANONICAL}"',
            f'<meta property="og:url" content="{CANONICAL}"',
            '<meta name="robots" content="index,follow,max-image-preview:large"',
            '<link rel="icon" type="image/svg+xml" href="%BASE_URL%favicon.svg"',
        ),
        "index metadata",
    )
    require(
        app,
        (
            'import.meta.env.VITE_PUBLIC_MARKETING_DEMO === "true"',
            "publicDemo={publicMarketingDemo}",
            "La demo se ejecuta localmente",
        ),
        "public App boundary",
    )
    require(
        workspace,
        (
            "createPublicMarketingDemoRun",
            'title: "Demo local completada"',
            'publicDemo ? "Ejecutar demo local"',
            "connectionOpen && !session && !publicDemo",
        ),
        "local workspace demo",
    )
    require(
        output,
        (
            "Vista previa local",
            "Sin efectos externos",
            "Concepto visual de demo",
        ),
        "local campaign output",
    )
    require(
        radar,
        (
            "PUBLIC_DEMO_TRENDS",
            "Muestra local · datos ilustrativos",
            "Runtime real separado de esta URL",
        ),
        "local trend demo",
    )
    require(
        demo,
        (
            "external_side_effects_enabled: false",
            'tenant_id: "public-demo"',
            'mode: "local_marketing_demo"',
        ),
        "demo data",
    )
    if "fetch(" in demo or "/api/" in demo or re.search(r"\bruntimeApi\s*[,;)]", demo):
        raise MarketingContractError("public demo data layer must not call the private runtime")

    require(robots, ("User-agent: *", "Allow: /", f"Sitemap: {CANONICAL}sitemap.xml"), "robots.txt")
    require(sitemap, (f"<loc>{CANONICAL}</loc>",), "sitemap.xml")
    require(
        docs,
        (
            CANONICAL,
            "simulación local",
            "GitHub Pages",
            "does not expose",
        ),
        "marketing documentation",
    )


def verify_dist(dist: Path) -> None:
    if not dist.is_dir():
        raise MarketingContractError(f"dist directory missing: {dist}")
    index_path = dist / "index.html"
    built = text(index_path)
    require(
        built,
        (
            f'href="{BASE_PATH}favicon.svg"',
            f'<link rel="canonical" href="{CANONICAL}"',
        ),
        "built index",
    )
    if "/src/main.tsx" in built:
        raise MarketingContractError("built index still points at the Vite source entrypoint")
    if not re.search(rf'(?:src|href)="{re.escape(BASE_PATH)}assets/', built):
        raise MarketingContractError("built index does not reference assets under the GitHub Pages repository base")
    for relative in ("favicon.svg", "robots.txt", "sitemap.xml"):
        if not (dist / relative).is_file():
            raise MarketingContractError(f"built artifact missing {relative}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist", type=Path)
    args = parser.parse_args()
    try:
        verify_source()
        if args.dist:
            verify_dist(args.dist.resolve())
    except MarketingContractError as error:
        print(f"marketing_public_url=FAIL: {error}", file=sys.stderr)
        return 1
    print(f"marketing_public_url=pass canonical={CANONICAL} public_runtime_calls=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
