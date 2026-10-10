"""Read-only, fail-closed video generation provider catalog.

This module deliberately has no execution methods, network client, secret persistence,
or billable calls. It is separate from model-text providers and the reviewed-disabled
browser-use/video-use integration. A future effect worker needs its own authority,
idempotency/fencing, per-tenant encrypted credentials, cost budget, and receipts.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class VideoProvider:
    provider_id: str
    display_name: str
    connection: str
    capabilities: tuple[str, ...]
    suited_for: str
    credential_environment: str | None
    setup: str
    documentation_url: str


_DEFINITIONS = (
    VideoProvider(
        provider_id="heygen",
        display_name="HeyGen",
        connection="hosted_api",
        capabilities=("avatar_video", "prompt_to_video", "translation", "templates"),
        suited_for="Presenters, product explainers, localization, branded variants",
        credential_environment="HEYGEN_API_KEY",
        setup="Set HEYGEN_API_KEY in the server secret manager; API credits and explicit generation approval are separate.",
        documentation_url="https://developers.heygen.com/reference/create-video-agent-session",
    ),
    VideoProvider(
        provider_id="freevideo",
        display_name="FreeVideo / ComfyUI",
        connection="local_gpu_worker",
        capabilities=("text_to_video", "image_to_video", "reference_guided_video"),
        suited_for="Local generative video with compatible GPU and commercial model-license review",
        credential_environment=None,
        setup="Bind a tenant-isolated ComfyUI worker with approved model weights and hardware; no worker is bundled.",
        documentation_url="https://github.com/FlashML-org/FreeVideo",
    ),
    VideoProvider(
        provider_id="ltx25",
        display_name="LTX-2.5 / ComfyUI",
        connection="local_gpu_worker",
        capabilities=("text_to_video", "image_to_video", "first_last_frame", "synchronized_audio"),
        suited_for="Cinematic shot generation, motion continuity and controllable first/last frames",
        credential_environment=None,
        setup="Bind approved ComfyUI LTX-2.5 worker and pin model license/revision; no worker is bundled.",
        documentation_url="https://docs.ltx.io/open-source-model/integration-tools/comfy-ui/",
    ),
    VideoProvider(
        provider_id="h3ddle",
        display_name="H3ddle",
        connection="native_mac_worker",
        capabilities=("text_to_video", "image_to_video", "timeline_editing", "audio"),
        suited_for="Apple Silicon desktop creative experiments and editing",
        credential_environment=None,
        setup="Install on an authorized Apple Silicon Mac and supply a scoped application bridge; browser tab control is not native app control.",
        documentation_url="https://github.com/AlexanderIstomin/h3ddle",
    ),
    VideoProvider(
        provider_id="computer_use",
        display_name="Computer Use / Browser Bridge",
        connection="assisted_browser",
        capabilities=("browser_assisted_generation",),
        suited_for="Approved interactive generation using supported authenticated web tabs",
        credential_environment=None,
        setup="Per-action native approval and allowlisted origins; do not imply unrestricted desktop application control.",
        documentation_url="https://github.com/BernydotJar/AI-Native-Content-Agency-SaaS",
    ),
)


class VideoProviderCatalog:
    """Expose only presence/absence of secret configuration, never secret values."""

    def __init__(self, environment: Mapping[str, str]) -> None:
        self._has_heygen_key = bool(
            str(environment.get("HEYGEN_API_KEY", "")).strip()
        )

    def list(self) -> list[dict[str, object]]:
        return [self.get(provider.provider_id) for provider in _DEFINITIONS]

    def get(self, provider_id: str) -> dict[str, object]:
        definition = next(
            (item for item in _DEFINITIONS if item.provider_id == provider_id),
            None,
        )
        if definition is None:
            raise KeyError("unknown video provider")

        if definition.provider_id == "heygen":
            configured = self._has_heygen_key
            state = "configured_execution_disabled" if configured else "missing_credential"
        else:
            configured = False
            state = "worker_not_bound"

        return {
            "provider_id": definition.provider_id,
            "display_name": definition.display_name,
            "connection": definition.connection,
            "capabilities": list(definition.capabilities),
            "suited_for": definition.suited_for,
            "configured": configured,
            "configuration_state": state,
            "execution_enabled": False,
            "requires_human_authorization": True,
            "credential_environment": definition.credential_environment,
            "setup": definition.setup,
            "documentation_url": definition.documentation_url,
        }


def heygen_video_agent_draft(prompt: str, *, mode: str = "generate") -> dict[str, str]:
    """Build a provider-correct, network-free v3 Video Agent draft.

    No API key, headers, callback URL, generated job, or cost is created.
    """
    if not isinstance(prompt, str) or not 1 <= len(prompt.strip()) <= 10_000:
        raise ValueError("video agent prompt must contain 1..10000 characters")
    if mode not in ("generate", "chat"):
        raise ValueError("unsupported video agent mode")
    return {"prompt": prompt.strip(), "mode": mode}
