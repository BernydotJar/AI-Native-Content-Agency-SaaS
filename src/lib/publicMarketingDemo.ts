import type {
  RuntimeArtifact,
  RuntimeBrief,
  RuntimeRun,
  RuntimeTrendSnapshot,
  RuntimeTrendTopic,
} from "./runtimeApi";

const DEMO_TIMESTAMP = "2026-08-11T18:00:00.000Z";

const STATION_DETAILS: Record<string, string> = {
  ceo: "Objetivo, restricciones y criterio de éxito alineados.",
  research: "Señales y supuestos separados para revisión humana.",
  strategist: "Narrativa, audiencia y secuencia editorial definidas.",
  growth: "Canales, aprendizaje y métricas de prueba organizados.",
  writer: "Borradores multicanal preparados para revisión.",
  media: "Concepto visual y requisitos de formato documentados.",
  risk: "Riesgos, claims y límites de publicación identificados.",
  publisher: "Paquete final preparado; publicación externa deshabilitada.",
};

function demoArtifacts(brief: RuntimeBrief): RuntimeArtifact[] {
  const title = brief.title.trim() || "Campaña demo";
  const audience = brief.audience.trim() || "audiencia objetivo";
  const objective = brief.objective.trim() || "explicar una propuesta con claridad";
  const channels = brief.platforms.join(", ") || "canales seleccionados";

  return [
    {
      artifact_id: "demo-ceo-brief",
      kind: "mission_brief",
      title: "Mission brief",
      payload: {
        objective,
        audience,
        channels,
        budget_cents: 0,
        execution_mode: "local_marketing_demo",
      },
      evidence_ids: ["demo-evidence-brief"],
    },
    {
      artifact_id: "demo-research-dossier",
      kind: "research_dossier",
      title: "Research dossier",
      payload: {
        insight: `La demostración organiza la investigación alrededor de ${audience}.`,
        evidence_policy: "sample_only_requires_runtime_verification",
        source_mode: "local_demo",
      },
      evidence_ids: ["demo-evidence-research"],
    },
    {
      artifact_id: "demo-strategy",
      kind: "strategy_memo",
      title: "Strategy memo",
      payload: {
        narrative: `${title}: convertir una señal en una historia clara, verificable y accionable.`,
        objective,
        audience,
      },
      evidence_ids: ["demo-evidence-strategy"],
    },
    {
      artifact_id: "demo-growth-plan",
      kind: "growth_plan",
      title: "Growth plan",
      payload: {
        channels: brief.platforms,
        experiment: "Comparar claridad del mensaje y respuesta cualitativa sin pauta ni publicación real.",
        spend_enabled: false,
      },
      evidence_ids: ["demo-evidence-growth"],
    },
    {
      artifact_id: "demo-copy-deck",
      kind: "copy_deck",
      title: "Platform copy deck",
      payload: {
        variants: {
          x: {
            hook: `Una señal puede convertirse en una campaña: ${title}.`,
            body: `${objective}. La demo muestra cómo ocho estaciones coordinan investigación, estrategia, contenido, riesgo y aprobación sin publicar nada fuera del navegador.`,
            cta: "Explora el flujo y revisa cada estación.",
          },
          instagram: {
            hook: `De la idea a una campaña gobernada: ${title}.`,
            body: `Para ${audience}: investigación, estrategia, copy, media y revisión humana en una sola experiencia. Esta es una simulación local; no publica ni usa credenciales reales.`,
            cta: "Recorre la demo completa.",
          },
          facebook: {
            hook: `${title}: una campaña coordinada de punta a punta.`,
            body: `${objective}. La experiencia pública simula el flujo completo sin conectarse al runtime privado.`,
            cta: "Conoce cómo funciona la orquestación.",
          },
          tiktok: {
            hook: `${title} en ocho estaciones.`,
            body: "Señal, estrategia, contenido, riesgo y aprobación humana en una simulación local sin efectos externos.",
            cta: "Explora el mapa de ejecución.",
          },
        },
        claims_status: "demo_sample_requires_human_review",
      },
      evidence_ids: ["demo-evidence-copy"],
    },
    {
      artifact_id: "demo-media-plan",
      kind: "media_plan",
      title: "Media concept",
      payload: {
        format: "4:5 social visual",
        concept: "Sistema de ocho estaciones conectadas alrededor de una misión central.",
        generated_media: false,
      },
      evidence_ids: ["demo-evidence-media"],
    },
    {
      artifact_id: "demo-risk-review",
      kind: "risk_review",
      title: "Risk & claims review",
      payload: {
        status: "demo_review_complete",
        external_publication_allowed: false,
        notes: [
          "Los datos mostrados en el radar público son ejemplos de producto.",
          "La publicación, pauta y proveedores reales permanecen deshabilitados.",
        ],
      },
      evidence_ids: ["demo-evidence-risk"],
    },
    {
      artifact_id: "demo-publication-plan",
      kind: "publication_plan",
      title: "Publication package",
      payload: {
        channels: brief.platforms,
        publication_enabled: false,
        mode: "local_marketing_demo",
      },
      evidence_ids: ["demo-evidence-publisher"],
    },
  ];
}

export function createPublicMarketingDemoRun(brief: RuntimeBrief): RuntimeRun {
  const artifacts = demoArtifacts(brief);
  const artifactByStation: Record<string, string> = {
    ceo: "demo-ceo-brief",
    research: "demo-research-dossier",
    strategist: "demo-strategy",
    growth: "demo-growth-plan",
    writer: "demo-copy-deck",
    media: "demo-media-plan",
    risk: "demo-risk-review",
    publisher: "demo-publication-plan",
  };

  return {
    run_id: `demo-local-${Date.now()}`,
    tenant_id: "public-demo",
    brief: {
      ...brief,
      platforms: [...brief.platforms],
      budget_cents: 0,
      evidence_claims: brief.evidence_claims?.map((claim) => ({ ...claim })),
    },
    status: "completed",
    agent_states: Object.fromEntries(
      Object.entries(STATION_DETAILS).map(([station, detail]) => [
        station,
        {
          status: "ready",
          progress: 100,
          detail,
          artifact_ids: [artifactByStation[station]],
        },
      ]),
    ),
    artifacts,
    greenlight: {
      greenlight_id: "demo-greenlight-local",
      decision: "approved",
      reviewer: "public-demo-review",
      note: "Simulación visual aprobada localmente. No concede autoridad de publicación.",
      approved_artifact_ids: artifacts.map((artifact) => artifact.artifact_id),
      approved_artifact_hashes: artifacts.map((_, index) => `demo-hash-${index + 1}`),
      authorized_channels: [...brief.platforms],
      authorized_budget_cents: 0,
      fencing_token: 8,
      revoked_at: null,
      revoked_by: "",
      revocation_reason: "",
    },
    sandbox: true,
    external_side_effects_enabled: false,
    execution: {
      state: "completed",
      next_station: "",
      lease_owner: "local-browser-demo",
      lease_expires_at: null,
      fencing_token: 8,
      attempts: 8,
      checkpointed_at: DEMO_TIMESTAMP,
      failure_detail: "",
    },
  };
}

function sampleSnapshot(topic: RuntimeTrendTopic, titles: string[]): RuntimeTrendSnapshot {
  return {
    tenant_id: "public-demo",
    geo: "GT",
    topic,
    source: "Google Trends RSS",
    source_url: "https://trends.google.com/trending?geo=GT",
    fetched_at: DEMO_TIMESTAMP,
    trends: titles.map((title, index) => ({
      title,
      approx_traffic: "muestra local",
      published_at: new Date(Date.parse(DEMO_TIMESTAMP) - index * 3_600_000).toISOString(),
      news_source: "",
      news_items: [],
      signal_type: "search_trend",
    })),
  };
}

export const PUBLIC_DEMO_TRENDS: Record<RuntimeTrendTopic, RuntimeTrendSnapshot> = {
  general: sampleSnapshot("general", [
    "Cómo explicar propuestas complejas con claridad",
    "Experiencias digitales con revisión humana visible",
    "Contenido multicanal coordinado desde una sola misión",
  ]),
  ai: sampleSnapshot("ai", [
    "Asistentes AI para flujos de trabajo supervisados",
    "Automatización con checkpoints y aprobación humana",
    "Orquestación de especialistas AI por objetivos",
  ]),
  marketing: sampleSnapshot("marketing", [
    "Contenido educativo de formato corto",
    "Pruebas creativas multicanal sin duplicar trabajo",
    "Campañas guiadas por señales y evidencia",
  ]),
  business: sampleSnapshot("business", [
    "Digitalización de operaciones para equipos pequeños",
    "Automatización de procesos comerciales repetitivos",
    "Sistemas de decisión con trazabilidad operativa",
  ]),
};
