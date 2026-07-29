from __future__ import annotations

from typing import Mapping, Sequence

from .models import MissionBrief
from .semantic_evals import find_text_risks, unsupported_numeric_tokens
from .utils import stable_id


def claim_ledger(brief: MissionBrief, run_id: str) -> list[dict[str, object]]:
    return [
        {
            "claim_id": stable_id(
                "claim",
                run_id,
                str(claim["statement"]).strip(),
                str(claim["source"]).strip(),
                str(claim["locator"]).strip(),
                length=24,
            ),
            "statement": str(claim["statement"]).strip(),
            "source": str(claim["source"]).strip(),
            "locator": str(claim["locator"]).strip(),
            "verification_status": str(
                claim.get("verification_status", "unverified")
            ),
            "reviewed_by": str(claim.get("reviewed_by", "")).strip(),
            "supported": (
                str(claim.get("verification_status", "unverified")) == "verified"
                and bool(str(claim.get("reviewed_by", "")).strip())
            ),
        }
        for claim in brief.evidence_claims
    ]


def strategy_payload(brief: MissionBrief) -> dict[str, object]:
    if brief.campaign_type == "political":
        pillars = [
            "Problema: describir la tensión local sin exageración",
            "Propuesta: explicar una acción dentro de las competencias del cargo",
            "Prueba: mostrar fuente y locator de cada afirmación",
            "Acción: invitar a consultar el plan y formular preguntas",
        ]
        architecture = {
            "audience_tension": brief.problem,
            "campaign_thesis": brief.proposal,
            "office_relevance": "{} · {}".format(brief.office, brief.locality),
            "proof_strategy": "claim ledger visible y revisable",
            "desired_action": brief.desired_action,
        }
    else:
        pillars = [
            "Evidencia: partir de una tensión verificable",
            "Expresión: adaptar el ritmo a cada plataforma",
            "Acción: mantener una llamada a la acción medible",
        ]
        architecture = {
            "audience_tension": brief.objective,
            "campaign_thesis": brief.title,
            "proof_strategy": "revisión humana de afirmaciones",
            "desired_action": "Conoce la propuesta y participa.",
        }
    return {"pillars": pillars, "message_architecture": architecture}


def growth_payload(
    brief: MissionBrief, synthetic_fixture: Mapping[str, object]
) -> dict[str, object]:
    if brief.campaign_type != "political":
        return dict(synthetic_fixture)
    return {
        "mode": "organic_only",
        "primary_metric": "qualified_replies_and_plan_views",
        "guardrails": [
            "no paid activation",
            "no inferred voter targeting",
            "no fabricated reach or conversion forecast",
            "stop on legal, factual or account-scope uncertainty",
        ],
        "forecast_status": "not_claimed_without_live_authorized_data",
        "synthetic_fixture": dict(synthetic_fixture),
    }


def copy_payload(
    brief: MissionBrief, claims: Sequence[Mapping[str, object]]
) -> dict[str, object]:
    supported_ids = [
        str(item["claim_id"])
        for item in claims
        if item.get("supported") is True and item.get("claim_id")
    ]
    if brief.campaign_type == "political":
        sources = " ".join(
            "Fuente: {} ({}).".format(claim["source"], claim["locator"])
            for claim in brief.evidence_claims
        )
        body = "{} propone: {}\n\n{}\n\n{}".format(
            brief.candidate_name.strip(),
            brief.proposal.strip(),
            sources,
            brief.disclosure.strip(),
        )
        variants = {}
        office = brief.office.strip().lower()
        for platform in brief.platforms:
            if office == "alcalde":
                locality = brief.locality.strip()
                municipal_subject = (
                    "el {}".format(locality)
                    if locality.lower().startswith("municipio")
                    else "el municipio de {}".format(locality)
                )
                hook = (
                    "¿Cómo puede {} rendir cuentas con información clara?"
                ).format(municipal_subject)
            elif office == "diputado":
                hook = (
                    "Una propuesta legislativa verificable para representar y fiscalizar en {}."
                ).format(brief.locality)
            else:
                hook = "Una propuesta verificable para {} en {}.".format(
                    brief.office.strip(), brief.locality
                )
            variants[platform.value] = {
                "hook": hook,
                "body": body,
                "cta": brief.desired_action.strip(),
                "claim_map": supported_ids,
                "language": brief.locale,
                "candidate": brief.candidate_name,
                "office": brief.office,
            }
        status = "grounded_requires_human_review"
        prohibited = [
            "resultados garantizados",
            "encuestas o respaldos no documentados",
            "ataques personales",
            "urgencia o miedo artificial",
        ]
    else:
        variants = {
            platform.value: {
                "hook": "{}: una propuesta clara para {}.".format(
                    brief.title, brief.audience
                ),
                "body": brief.objective,
                "cta": "Conoce la propuesta y participa.",
                "claim_map": supported_ids,
                "language": brief.locale,
            }
            for platform in brief.platforms
        }
        status = "draft_requires_human_review"
        prohibited = []
    return {
        "variants": variants,
        "claims_status": status,
        "prohibited_claims": prohibited,
    }


def media_payload(
    brief: MissionBrief,
    *,
    video: Mapping[str, object],
    image_to_video: Mapping[str, object],
) -> dict[str, object]:
    payload: dict[str, object] = {
        "video": dict(video),
        "image_to_video": dict(image_to_video),
        "source_asset_read": False,
        "media_rendered": False,
    }
    if brief.campaign_type == "political":
        payload["instagram"] = {
            "format": "carousel",
            "dimensions": {"width": 1080, "height": 1350},
            "slides": [
                {"index": 1, "purpose": "problema", "copy": brief.problem},
                {"index": 2, "purpose": "propuesta", "copy": brief.proposal},
                {
                    "index": 3,
                    "purpose": "evidencia",
                    "copy": "Fuentes: "
                    + "; ".join(
                        "{} ({})".format(item["source"], item["locator"])
                        for item in brief.evidence_claims
                    ),
                },
                {
                    "index": 4,
                    "purpose": "acción",
                    "copy": brief.desired_action,
                },
            ],
            "alt_text": (
                "Carrusel sobre una propuesta de {} en {}; presenta problema, "
                "propuesta, fuentes y llamada a la participación."
            ).format(brief.office, brief.locality),
            "rights_status": "operator_must_confirm",
        }
    return payload


def critique_payload(
    brief: MissionBrief,
    *,
    claims: Sequence[Mapping[str, object]],
    variants: Mapping[str, object],
) -> dict[str, object]:
    checks: list[dict[str, object]] = [
        {"name": "sandbox_only", "passed": True},
        {"name": "human_greenlight_required", "passed": True},
        {"name": "publisher_not_run", "passed": True},
        {"name": "media_not_rendered", "passed": True},
    ]
    publication_eligible = True
    if brief.campaign_type == "political":
        supported_ids = {
            str(item["claim_id"])
            for item in claims
            if item.get("supported") is True and item.get("claim_id")
        }
        mapped_ids = {
            str(claim_id)
            for variant in variants.values()
            if isinstance(variant, Mapping)
            for claim_id in variant.get("claim_map", [])
        }
        rendered_text = " ".join(
            str(value)
            for variant in variants.values()
            if isinstance(variant, Mapping)
            for value in (
                variant.get("hook", ""),
                variant.get("body", ""),
                variant.get("cta", ""),
            )
        ).lower()
        source_visible = all(
            str(claim["source"]).strip().lower() in rendered_text
            for claim in brief.evidence_claims
        )
        disclosure_visible = all(
            brief.disclosure.strip().lower()
            in str(variant.get("body", "")).lower()
            for variant in variants.values()
            if isinstance(variant, Mapping)
        )
        office = brief.office.strip().lower()
        if office == "alcalde":
            office_message_alignment = any(
                term in rendered_text for term in ("municipio", "municipal")
            )
        elif office == "diputado":
            office_message_alignment = any(
                term in rendered_text
                for term in (
                    "legislativa",
                    "legislativo",
                    "congreso",
                    "fiscalizar",
                    "fiscalización",
                )
            )
        else:
            office_message_alignment = office in rendered_text
        political_checks = [
            {
                "name": "language_consistency",
                "passed": brief.locale.lower().startswith("es"),
            },
            {
                "name": "office_message_alignment",
                "passed": office_message_alignment,
            },
            {
                "name": "evidence_verified",
                "passed": len(supported_ids) == len(brief.evidence_claims),
            },
            {
                "name": "evidence_coverage",
                "passed": bool(supported_ids) and mapped_ids == supported_ids,
            },
            {"name": "source_visibility", "passed": source_visible},
            {
                "name": "office_relevance",
                "passed": bool(brief.office.strip() and brief.locality.strip()),
            },
            {"name": "disclosure_present", "passed": disclosure_visible},
            {
                "name": "legal_review_approved",
                "passed": (
                    brief.legal_review_status == "approved"
                    and bool(brief.legal_reviewed_by.strip())
                ),
            },
            {
                "name": "instruction_injection_absent",
                "passed": "instruction_injection" not in find_text_risks(rendered_text)
                and all(
                    "instruction_injection"
                    not in find_text_risks(str(claim.get(field, "")))
                    for claim in claims
                    for field in ("statement", "source", "locator")
                ),
            },
            {
                "name": "unsupported_promotion_absent",
                "passed": "unsupported_overclaim" not in find_text_risks(rendered_text),
            },
            {
                "name": "unsupported_numeric_claim_absent",
                "passed": not unsupported_numeric_tokens(rendered_text, claims),
            },
            {"name": "legal_review_gate_present", "passed": True},
        ]
        checks.extend(political_checks)
        publication_eligible = all(bool(item["passed"]) for item in political_checks)
    passed = all(bool(item["passed"]) for item in checks)
    return {
        "passed": passed,
        "publication_eligible": publication_eligible,
        "decision": "pass" if passed and publication_eligible else "revise",
        "checks": checks,
        "human_greenlight_required": True,
        "legal_review_required": brief.campaign_type == "political",
        "limitations": [
            "language_consistency validates the declared locale and deterministic copy rules; it is not full linguistic review",
            "source visibility does not independently prove source authenticity",
            "jurisdiction-specific legal review remains an external human gate",
        ] if brief.campaign_type == "political" else [],
    }
