from __future__ import annotations

import copy
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .models import ExecutionRun

BUNDLE_SCHEMA = "agency.semantic-eval-bundle.v1"
CORPUS_SCHEMA = "agency.semantic-adversarial-corpus.v1"
REPORT_SCHEMA = "agency.semantic-eval-report.v1"
_ID = re.compile(r"^[a-z0-9][a-z0-9._:-]{0,127}$")
_NUMBER = re.compile(r"(?<![\w])\d+(?:[.,]\d+)?%?")
_MAX_TEXT = 16_384
_MAX_TOTAL_TEXT = 65_536
_INJECTION = (
    "ignore previous instructions", "ignore all previous instructions",
    "reveal the system prompt", "show the system prompt", "developer message",
    "system message", "execute this command", "call the tool", "exfiltrate",
    "ignora las instrucciones anteriores", "ignora todas las instrucciones",
    "muestra el prompt del sistema", "revela el prompt del sistema",
    "mensaje del desarrollador", "mensaje del sistema", "ejecuta este comando",
    "llama a la herramienta", "extrae los secretos", "<system>", "</system>",
)
_OVERCLAIM = (
    "resultados garantizados", "resultado garantizado", "garantiza la victoria",
    "garantiza el resultado", "todos apoyan", "todo el mundo apoya",
    "100% de apoyo", "cumple con todas las leyes",
    "legalmente aprobado en todas partes", "sin ningún riesgo legal",
    "no legal risk", "complies with every law", "guaranteed victory",
    "everyone supports",
)


class SemanticEvalInputError(ValueError):
    pass


@dataclass(frozen=True, order=True)
class SemanticFinding:
    code: str
    path: str
    severity: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "path": self.path, "severity": self.severity, "detail": self.detail}


@dataclass(frozen=True)
class SemanticEvalResult:
    passed: bool
    findings: tuple[SemanticFinding, ...]
    metrics: Mapping[str, int]

    def as_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "findings": [item.as_dict() for item in self.findings],
            "metrics": dict(sorted(self.metrics.items())),
        }


def normalize_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def find_text_risks(value: str) -> tuple[str, ...]:
    text = normalize_text(value)
    risks: list[str] = []
    if any(pattern in text for pattern in _INJECTION):
        risks.append("instruction_injection")
    if any(pattern in text for pattern in _OVERCLAIM):
        risks.append("unsupported_overclaim")
    return tuple(risks)


def unsupported_numeric_tokens(rendered_text: str, claims: Sequence[Mapping[str, object]]) -> tuple[str, ...]:
    evidence = " ".join(
        str(claim.get(field, ""))
        for claim in claims
        for field in ("statement", "source", "locator")
    )
    return tuple(sorted(set(_NUMBER.findall(normalize_text(rendered_text))) - set(_NUMBER.findall(normalize_text(evidence)))))


def bundle_from_run(run: ExecutionRun, *, producer_subject: str, greenlight_reviewer: str) -> dict[str, object]:
    claims = copy.deepcopy(list(run.artifact("research_dossier").payload.get("claim_ledger", [])))
    variants = copy.deepcopy(dict(run.artifact("copy_deck").payload.get("variants", {})))
    risk = run.artifact("risk_report").payload
    return {
        "schema_version": BUNDLE_SCHEMA,
        "campaign_type": run.brief.campaign_type,
        "disclosure": run.brief.disclosure,
        "actors": {
            "producer": producer_subject.strip(),
            "fact_reviewers": sorted({str(item.get("reviewed_by", "")).strip() for item in claims if str(item.get("reviewed_by", "")).strip()}),
            "legal_reviewer": run.brief.legal_reviewed_by.strip(),
            "greenlight_reviewer": greenlight_reviewer.strip(),
        },
        "claims": claims,
        "variants": variants,
        "risk": {
            "passed": risk.get("passed") is True,
            "publication_eligible": risk.get("publication_eligible") is True,
            "decision": str(risk.get("decision", "")),
        },
        "authority": {
            "external_effects_enabled": False,
            "model_effects_enabled": False,
            "publication_enabled": False,
        },
    }


def _mapping(value: object, path: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise SemanticEvalInputError(f"{path} must be an object")
    return value


def _text(value: object, path: str, *, empty: bool = False) -> str:
    if not isinstance(value, str) or len(value) > _MAX_TEXT or (not empty and not value.strip()):
        raise SemanticEvalInputError(f"{path} must be a bounded string")
    return value


def _keys(value: Mapping[str, object], expected: set[str], path: str) -> None:
    if set(value) != expected:
        raise SemanticEvalInputError(f"{path} keys mismatch")


def _finding(code: str, path: str, detail: str, severity: str = "HIGH") -> SemanticFinding:
    return SemanticFinding(code, path, severity, detail)


def _text_size(value: object) -> int:
    if isinstance(value, str):
        return len(value)
    if isinstance(value, Mapping):
        return sum(_text_size(item) for item in value.values())
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return sum(_text_size(item) for item in value)
    return 0


def evaluate_bundle(bundle: Mapping[str, object]) -> SemanticEvalResult:
    root = _mapping(bundle, "bundle")
    _keys(root, {"schema_version", "campaign_type", "disclosure", "actors", "claims", "variants", "risk", "authority"}, "bundle")
    if root.get("schema_version") != BUNDLE_SCHEMA:
        raise SemanticEvalInputError("unsupported bundle schema")
    if _text(root.get("campaign_type"), "campaign_type") != "political":
        raise SemanticEvalInputError("campaign_type must be political")
    disclosure = _text(root.get("disclosure"), "disclosure", empty=True)
    if _text_size(root) > _MAX_TOTAL_TEXT:
        raise SemanticEvalInputError("bundle text is unbounded")

    findings: list[SemanticFinding] = []
    actors = _mapping(root.get("actors"), "actors")
    _keys(actors, {"producer", "fact_reviewers", "legal_reviewer", "greenlight_reviewer"}, "actors")
    producer = _text(actors.get("producer"), "actors.producer", empty=True).strip()
    legal = _text(actors.get("legal_reviewer"), "actors.legal_reviewer", empty=True).strip()
    greenlight = _text(actors.get("greenlight_reviewer"), "actors.greenlight_reviewer", empty=True).strip()
    fact_raw = actors.get("fact_reviewers")
    if not isinstance(fact_raw, list) or not all(isinstance(item, str) for item in fact_raw):
        raise SemanticEvalInputError("actors.fact_reviewers must be a string list")
    fact_reviewers = [item.strip() for item in fact_raw]

    claims_raw = root.get("claims")
    if not isinstance(claims_raw, list) or not 1 <= len(claims_raw) <= 64:
        raise SemanticEvalInputError("claims must contain 1..64 entries")
    claims: list[Mapping[str, object]] = []
    claim_by_id: dict[str, Mapping[str, object]] = {}
    for index, raw in enumerate(claims_raw):
        claim = _mapping(raw, f"claims[{index}]")
        _keys(claim, {"claim_id", "statement", "source", "locator", "verification_status", "reviewed_by", "supported"}, f"claims[{index}]")
        claim_id = _text(claim.get("claim_id"), f"claims[{index}].claim_id")
        if not _ID.fullmatch(claim_id) or claim_id in claim_by_id:
            raise SemanticEvalInputError("claim IDs must be unique and bounded")
        for field in ("statement", "source", "locator"):
            _text(claim.get(field), f"claims[{index}].{field}")
            if find_text_risks(str(claim[field])):
                findings.append(_finding("untrusted_instruction_text", f"claims/{index}/{field}", "Evidence text contains instruction-like or unsupported authority language."))
        status = _text(claim.get("verification_status"), f"claims[{index}].verification_status")
        reviewer = _text(claim.get("reviewed_by"), f"claims[{index}].reviewed_by", empty=True).strip()
        if not isinstance(claim.get("supported"), bool):
            raise SemanticEvalInputError("claim.supported must be boolean")
        if status != "verified" or not reviewer or claim.get("supported") is not True:
            findings.append(_finding("claim_not_verified", f"claims/{index}", "Political claims require verified status, reviewer and supported=true."))
        claim_by_id[claim_id] = claim
        claims.append(claim)

    supported_ids = {
        str(item["claim_id"])
        for item in claims
        if item.get("verification_status") == "verified"
        and str(item.get("reviewed_by", "")).strip()
        and item.get("supported") is True
    }
    if not supported_ids:
        findings.append(_finding("no_supported_claims", "claims", "No supported political claim exists."))

    variants = _mapping(root.get("variants"), "variants")
    if not 1 <= len(variants) <= 8:
        raise SemanticEvalInputError("variants must contain 1..8 entries")
    mapped_ids: set[str] = set()
    rendered_chars = 0
    for platform, raw in sorted(variants.items()):
        if not isinstance(platform, str) or not _ID.fullmatch(platform):
            raise SemanticEvalInputError("invalid platform key")
        variant = _mapping(raw, f"variants.{platform}")
        _keys(variant, {"hook", "body", "cta", "claim_map", "language", "candidate", "office"}, f"variants.{platform}")
        hook = _text(variant.get("hook"), f"variants.{platform}.hook")
        body = _text(variant.get("body"), f"variants.{platform}.body")
        cta = _text(variant.get("cta"), f"variants.{platform}.cta")
        for field in ("language", "candidate", "office"):
            _text(variant.get(field), f"variants.{platform}.{field}")
        claim_map = variant.get("claim_map")
        if not isinstance(claim_map, list) or not all(isinstance(item, str) for item in claim_map):
            raise SemanticEvalInputError("claim_map must be a string list")
        if len(claim_map) != len(set(claim_map)):
            findings.append(_finding("duplicate_claim_mapping", f"variants/{platform}/claim_map", "Claim mappings must be unique."))
        variant_ids = set(claim_map)
        if variant_ids - set(claim_by_id):
            findings.append(_finding("unknown_claim_mapping", f"variants/{platform}/claim_map", "Variant references unknown claim IDs."))
        if variant_ids != supported_ids:
            findings.append(_finding("claim_coverage_mismatch", f"variants/{platform}/claim_map", "Every variant must map exactly the supported claim set."))
        normalized_body = normalize_text(body)
        for claim_id in sorted(variant_ids & set(claim_by_id)):
            claim = claim_by_id[claim_id]
            if normalize_text(str(claim["source"])) not in normalized_body or normalize_text(str(claim["locator"])) not in normalized_body:
                findings.append(_finding("citation_not_visible", f"variants/{platform}/body", "Mapped source and locator must be visible."))
        if not disclosure.strip() or normalize_text(disclosure) not in normalized_body:
            findings.append(_finding("disclosure_missing", f"variants/{platform}/body", "Political disclosure must be visible."))
        combined = " ".join((hook, body, cta))
        for code in find_text_risks(combined):
            findings.append(_finding(code, f"variants/{platform}", "Rendered copy contains prohibited semantic content."))
        if unsupported_numeric_tokens(combined, claims):
            findings.append(_finding("unsupported_numeric_claim", f"variants/{platform}", "Rendered numbers are absent from verified evidence."))
        mapped_ids.update(variant_ids)
        rendered_chars += len(combined)

    if not producer:
        findings.append(_finding("producer_missing", "actors/producer", "Producer identity is required."))
    if not legal:
        findings.append(_finding("legal_review_missing", "actors/legal_reviewer", "Legal review is required."))
    if not greenlight:
        findings.append(_finding("greenlight_reviewer_missing", "actors/greenlight_reviewer", "Greenlight reviewer is required."))
    reviewer_set = {item for item in fact_reviewers if item}
    claim_reviewers = {str(item.get("reviewed_by", "")).strip() for item in claims if str(item.get("reviewed_by", "")).strip()}
    if reviewer_set != claim_reviewers:
        findings.append(_finding("fact_reviewer_set_mismatch", "actors/fact_reviewers", "Actor and claim reviewers differ."))
    if producer and producer in reviewer_set | {legal, greenlight}:
        findings.append(_finding("producer_reviewer_conflict", "actors", "Producer cannot self-attest review."))
    if legal and legal == greenlight:
        findings.append(_finding("legal_greenlight_conflict", "actors", "Legal and Greenlight reviewers must differ."))

    authority = _mapping(root.get("authority"), "authority")
    _keys(authority, {"external_effects_enabled", "model_effects_enabled", "publication_enabled"}, "authority")
    for key, value in authority.items():
        if not isinstance(value, bool):
            raise SemanticEvalInputError("authority values must be boolean")
        if value:
            findings.append(_finding("external_authority_enabled", f"authority/{key}", "Evaluation cannot enable external authority.", "CRITICAL"))

    risk = _mapping(root.get("risk"), "risk")
    _keys(risk, {"passed", "publication_eligible", "decision"}, "risk")
    if not isinstance(risk.get("passed"), bool) or not isinstance(risk.get("publication_eligible"), bool):
        raise SemanticEvalInputError("risk booleans are invalid")
    decision = _text(risk.get("decision"), "risk.decision")
    eligible = not findings
    if risk.get("passed") is not eligible or risk.get("publication_eligible") is not eligible:
        findings.append(_finding("risk_report_mismatch", "risk", "Runtime risk report disagrees with evaluation."))
    if decision != ("pass" if eligible else "revise"):
        findings.append(_finding("risk_decision_mismatch", "risk/decision", "Runtime risk decision is inconsistent."))

    unique = tuple(sorted(set(findings)))
    return SemanticEvalResult(
        passed=not unique,
        findings=unique,
        metrics={"claims": len(claims), "mapped_claims": len(mapped_ids), "rendered_characters": rendered_chars, "variants": len(variants)},
    )


def apply_mutations(bundle: Mapping[str, object], mutations: Sequence[Mapping[str, object]]) -> dict[str, object]:
    result = copy.deepcopy(dict(bundle))
    for index, raw in enumerate(mutations):
        mutation = _mapping(raw, f"mutations[{index}]")
        _keys(mutation, {"op", "path", "value"}, f"mutations[{index}]")
        operation = _text(mutation.get("op"), f"mutations[{index}].op")
        if operation not in {"set", "append", "delete"}:
            raise SemanticEvalInputError("unsupported mutation operation")
        path = _text(mutation.get("path"), f"mutations[{index}].path")
        if not path.startswith("/") or ".." in path:
            raise SemanticEvalInputError("invalid mutation path")
        parts = [part.replace("~1", "/").replace("~0", "~") for part in path[1:].split("/")]
        cursor: Any = result
        for part in parts[:-1]:
            if isinstance(cursor, list) and part.isdigit() and int(part) < len(cursor):
                cursor = cursor[int(part)]
            elif isinstance(cursor, dict) and part in cursor:
                cursor = cursor[part]
            else:
                raise SemanticEvalInputError("mutation path does not exist")
        leaf = parts[-1]
        if isinstance(cursor, list) and leaf.isdigit() and int(leaf) < len(cursor):
            target: Any = int(leaf)
        elif isinstance(cursor, dict) and leaf in cursor:
            target = leaf
        else:
            raise SemanticEvalInputError("mutation path does not exist")
        if operation == "set":
            cursor[target] = copy.deepcopy(mutation.get("value"))
        elif operation == "delete":
            del cursor[target]
        else:
            sequence = cursor[target]
            if not isinstance(sequence, list):
                raise SemanticEvalInputError("append target is not a list")
            sequence.append(copy.deepcopy(mutation.get("value")))
    return result
