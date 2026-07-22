import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { CanvasBackground } from "./components/CanvasBackground";
import { ControlPanel } from "./components/ControlPanel";
import type {
  CampaignSimulationParams,
  ImageSimulationParams,
  SimulationParams,
  UseCaseId,
  VideoSimulationParams,
} from "./components/ControlPanel";
import { PipelineGraph } from "./components/PipelineGraph";
import type { NodeState } from "./components/PipelineGraph";
import { InteractiveSidebar } from "./components/InteractiveSidebar";
import {
  MemorySkillsPanel,
} from "./components/MemorySkillsPanel";
import type {
  SessionMemoryFlag,
  SkillId,
} from "./components/MemorySkillsPanel";
import { MetaAdsDashboard } from "./components/MetaAdsDashboard";
import type { MetaAdsCampaign } from "./components/MetaAdsDashboard";
import { ToolFabricPanel } from "./components/ToolFabricPanel";
import { ProductionRuntimePanel } from "./components/ProductionRuntimePanel";
import { packageCampaign } from "./lib/simulationRuntime";
import { DEFAULT_THEME_ID, THEME_CATALOG, applyTheme, isThemeAvailable } from "./lib/themeCatalog";
import type { ThemeId } from "./lib/themeCatalog";
import { 
  Terminal, 
  Cpu, 
  Layers, 
  Wifi, 
  ShieldCheck,
  Sliders,
  Sparkles,
} from "lucide-react";


interface LogMessage {
  sender: string;
  message: string;
  timestamp: string;
  isScholar?: boolean;
  nlpExplanation?: {
    reencuadre: string;
    tradeoff: string;
    resolucion: string;
  };
}

interface IngestedFile {
  name: string;
  type: string;
  size: string;
}

interface GeneratedAsset {
  name: string;
  type: "text" | "video" | "image" | "ad_campaign";
  content: string;
}

interface NodeData {
  id: string;
  name: string;
  role: string;
  status: "idle" | "running" | "success" | "error";
  progress: number;
  logs: LogMessage[];
  files: IngestedFile[];
  assets: GeneratedAsset[];
}

interface DeferredApprovalTask {
  task: () => void;
  delay: number;
}

const DEFAULT_NODE_STATES: Record<string, NodeState> = {
  ingestion: { status: "idle", progress: 0, itemsCount: 0, itemsLabel: "archivos" },
  ceo: { status: "idle", progress: 0, itemsCount: 0, itemsLabel: "briefs" },
  research: { status: "idle", progress: 0, itemsCount: 0, itemsLabel: "conceptos" },
  media: { status: "idle", progress: 0, itemsCount: 0, itemsLabel: "assets" },
  strategist: { status: "idle", progress: 0, itemsCount: 0, itemsLabel: "canales" },
  growth: { status: "idle", progress: 0, itemsCount: 0, itemsLabel: "rutas" },
  writer: { status: "idle", progress: 0, itemsCount: 0, itemsLabel: "copys" },
  risk: { status: "idle", progress: 0, itemsCount: 0, itemsLabel: "alertas" },
  publisher: { status: "idle", progress: 0, itemsCount: 0, itemsLabel: "campañas" }
};

export default function App() {
  const [activeStep, setActiveStep] = useState<string>("");
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>("ingestion");
  const [isApproved, setIsApproved] = useState<boolean>(false);
  const [approvalReady, setApprovalReady] = useState<boolean>(false);
  const [isAdsSyncing, setIsAdsSyncing] = useState<boolean>(false);
  const [enabledSkills, setEnabledSkills] = useState<Record<SkillId, boolean>>({
    "scholar-nlp": true,
    "ai-seo": true,
    "churn-prevention": false,
    "brand-guard": true,
  });
  const [memoryFlags, setMemoryFlags] = useState<SessionMemoryFlag[]>([]);
  
  // Terminal log messages
  const [systemLogs, setSystemLogs] = useState<string[]>([
    "Simulation kernel booted. Obsidian-slate scene loaded.",
    "Sensor adapters staged in mock mode: X, Facebook, TikTok and Instagram.",
    "MCP contracts available for demo: Meta Ads, browser, GitHub and Context7.",
    "War Room is awaiting a campaign brief. No live actions will be executed."
  ]);

  const [themeId, setThemeId] = useState<ThemeId>(DEFAULT_THEME_ID);
  const [runtimeEntitlements, setRuntimeEntitlements] = useState<readonly string[]>([]);
  const premiumThemeEntitled = runtimeEntitlements.includes("theme:premium");
  const scheduledWorkRef = useRef<number[]>([]);
  const deferredApprovalWorkRef = useRef<DeferredApprovalTask[]>([]);
  const approvalRef = useRef(false);

  const clearScheduledWork = () => {
    scheduledWorkRef.current.forEach((timerId) => window.clearTimeout(timerId));
    scheduledWorkRef.current = [];
    deferredApprovalWorkRef.current = [];
  };

  const schedule = (task: () => void, delay: number) => {
    const timerId = window.setTimeout(() => {
      scheduledWorkRef.current = scheduledWorkRef.current.filter((candidate) => candidate !== timerId);
      task();
    }, delay);
    scheduledWorkRef.current.push(timerId);
  };

  const deferUntilApproval = (task: () => void, delay: number) => {
    deferredApprovalWorkRef.current.push({ task, delay });
  };

  useEffect(() => () => clearScheduledWork(), []);

  // Dynamic node states tracking percentages and active items count
  const [nodeStates, setNodeStates] = useState<Record<string, NodeState>>(DEFAULT_NODE_STATES);

  // Deep detail data stored for each node (for the sidebar)
  const [nodeDataMap, setNodeDataMap] = useState<Record<string, NodeData>>({
    ingestion: {
      id: "ingestion",
      name: "Real-Time Ingestion",
      role: "Sensor / Ingestion",
      status: "idle",
      progress: 0,
      logs: [],
      files: [],
      assets: []
    },
    ceo: {
      id: "ceo",
      name: "CEO / Jefe de Campaña",
      role: "Orchestration & Target",
      status: "idle",
      progress: 0,
      logs: [],
      files: [],
      assets: []
    },
    research: {
      id: "research",
      name: "Research / Scholar",
      role: "Theory & NLP Scholar",
      status: "idle",
      progress: 0,
      logs: [],
      files: [],
      assets: []
    },
    media: {
      id: "media",
      name: "Media / Storytelling",
      role: "Video Planning / Sandbox",
      status: "idle",
      progress: 0,
      logs: [],
      files: [],
      assets: []
    },
    strategist: {
      id: "strategist",
      name: "Strategist Agent",
      role: "Trend-Mixer Strategy",
      status: "idle",
      progress: 0,
      logs: [],
      files: [],
      assets: []
    },
    growth: {
      id: "growth",
      name: "Growth / Territorio",
      role: "Distribution & Community",
      status: "idle",
      progress: 0,
      logs: [],
      files: [],
      assets: []
    },
    writer: {
      id: "writer",
      name: "Writer Agent",
      role: "Content Copywriter",
      status: "idle",
      progress: 0,
      logs: [],
      files: [],
      assets: []
    },
    risk: {
      id: "risk",
      name: "Risk Agent",
      role: "Seguimiento & Compliance",
      status: "idle",
      progress: 0,
      logs: [],
      files: [],
      assets: []
    },
    publisher: {
      id: "publisher",
      name: "Publisher / Meta Ads",
      role: "Pauta & Meta Ads MCP",
      status: "idle",
      progress: 0,
      logs: [],
      files: [],
      assets: []
    }
  });

  // Meta Ads campaigns state
  const [metaCampaigns, setMetaCampaigns] = useState<MetaAdsCampaign[]>([
    {
      id: "camp-0",
      name: "Simulated Campaign: Kleppmann Trade-offs",
      budget: 1500,
      spent: 850,
      ctr: 2.14,
      cac: 9.85,
      impressions: 42000,
      conversions: 86,
      status: "active",
      targeting: {
        demographics: "Software Engineers (24-45)",
        interests: ["Rust", "Next.js", "Docker", "Database Design"],
        locations: ["Worldwide"]
      }
    }
  ]);

  useEffect(() => {
    applyTheme(themeId);
  }, [themeId]);

  useLayoutEffect(() => {
    if (themeId === "premium" && !premiumThemeEntitled) {
      setThemeId(DEFAULT_THEME_ID);
    }
  }, [premiumThemeEntitled, themeId]);

  const changeTheme = (nextThemeId: ThemeId) => {
    const theme = THEME_CATALOG.find((candidate) => candidate.id === nextThemeId);
    if (!theme || !isThemeAvailable(theme, premiumThemeEntitled)) return;
    setThemeId(nextThemeId);
  };

  const addSystemLog = (msg: string) => {
    setSystemLogs(prev => [...prev.slice(-30), `[${new Date().toLocaleTimeString()}] ${msg}`]);
  };

  const updateNodeProgressState = (nodeId: string, updates: Partial<NodeState>) => {
    setNodeStates(prev => ({
      ...prev,
      [nodeId]: {
        ...prev[nodeId],
        ...updates
      }
    }));
  };

  const updateNodeDataMap = (nodeId: string, updates: Partial<NodeData>) => {
    setNodeDataMap(prev => ({
      ...prev,
      [nodeId]: {
        ...prev[nodeId],
        ...updates
      }
    }));
  };

  const handleApprovalToggle = () => {
    if (!approvalReady && !approvalRef.current) {
      addSystemLog("Greenlight bloqueado: Risk Agent todavía no ha completado la auditoría.");
      return;
    }

    const nextApproved = !approvalRef.current;
    approvalRef.current = nextApproved;
    setIsApproved(nextApproved);

    if (nextApproved) {
      const releaseQueue = deferredApprovalWorkRef.current;
      deferredApprovalWorkRef.current = [];
      setApprovalReady(false);
      addSystemLog("Greenlight concedido. Liberando la cola de Publisher en el sandbox.");
      releaseQueue.forEach(({ task, delay }) => schedule(task, delay));
      return;
    }

    clearScheduledWork();
    setIsAdsSyncing(false);

    if (isRunning) {
      setIsRunning(false);
      setActiveStep("");
      updateNodeProgressState("publisher", { status: "error" });
      updateNodeDataMap("publisher", {
        status: "error",
        logs: [{
          sender: "Operator Gate",
          message: "Publicación cancelada: el operador revocó el greenlight.",
          timestamp: new Date().toLocaleTimeString(),
        }],
      });
      addSystemLog("Greenlight revocado. El trabajo pendiente de Publisher fue cancelado.");
      return;
    }

    addSystemLog("Greenlight retirado después del ensayo. Se canceló cualquier pulso local pendiente; no había acciones externas que revertir.");
  };

  // Run simulated flow for the three Use Cases
  const handleRunSimulation = (useCaseId: UseCaseId, params: SimulationParams) => {
    if (isRunning) return;
    clearScheduledWork();
    setIsAdsSyncing(false);
    setIsRunning(true);
    approvalRef.current = false;
    setIsApproved(false);
    setApprovalReady(false);
    setSelectedNodeId("ingestion");
    addSystemLog(`Iniciando simulación del Caso de Uso ${useCaseId}...`);

    // Reset node progress states to idle
    const cleanStates = { ...DEFAULT_NODE_STATES };
    setNodeStates(cleanStates);
    setNodeDataMap((current) => Object.fromEntries(
      Object.entries(current).map(([nodeId, node]) => [
        nodeId,
        { ...node, status: "idle", progress: 0, logs: [], files: [], assets: [] },
      ]),
    ) as Record<string, NodeData>);

    if (useCaseId === 1 && "videoName" in params) {
      runUseCase1(params);
    } else if (useCaseId === 2 && "imageName" in params) {
      runUseCase2(params);
    } else if (useCaseId === 3 && "prompt" in params) {
      runUseCase3(params);
    }
  };

  const handleManualSync = () => {
    setIsAdsSyncing(true);
    addSystemLog("Ejecutando fixture local del contrato Meta Ads para simular CTR, gasto y conversiones...");
    schedule(() => {
      setIsAdsSyncing(false);
      setMetaCampaigns(prev => prev.map((campaign) => {
        if (campaign.status !== "active" || campaign.spent >= campaign.budget) return campaign;
        const nextSpent = Math.min(campaign.budget, campaign.spent + 120);
        const spendDelta = nextSpent - campaign.spent;
        const nextConversions = campaign.conversions + Math.max(1, Math.round(spendDelta / 10));
        return {
          ...campaign,
          spent: nextSpent,
          impressions: campaign.impressions + Math.round(spendDelta * 45),
          conversions: nextConversions,
          ctr: Math.min(9.99, Number((campaign.ctr + 0.12).toFixed(2))),
          cac: Number((nextSpent / nextConversions).toFixed(2)),
        };
      }));
      addSystemLog("Pulso de Meta Ads simulado: gasto acotado al presupuesto y CAC recalculado desde conversiones.");
    }, 1800);
  };

  const handleSkillToggle = (skillId: SkillId) => {
    setEnabledSkills((current) => ({
      ...current,
      [skillId]: !current[skillId],
    }));
    addSystemLog(`Skill ${skillId} actualizado. El cambio afectará el próximo Caso de Uso 3.`);
  };

  const handleAddMemoryFlag = (content: string) => {
    const memoryFlag: SessionMemoryFlag = {
      id: `session-memory-${Date.now()}`,
      content,
      provenance: "Operator input · Memory Console · Browser session",
      confidence: 100,
    };
    setMemoryFlags((current) => [...current, memoryFlag]);
    addSystemLog("Memory flag observada y almacenada en la sesión; se recuperará en el próximo pack de campaña.");
  };

  /* ==========================================
     SIMULATION RUNNERS FOR THE 3 USE CASES
     ========================================== */

  // Use Case 1: Video Input & Optimization
  const runUseCase1 = (params: VideoSimulationParams) => {
    const videoName = params.videoName;
    const platform = params.platform;
    const targetFormat = platform === "X" ? "cuadrado (1:1)" : "vertical (9:16)";
    const outputSlug = platform.toLowerCase().replace(/[^a-z0-9]+/g, "-");
    const publicationReference = `sandbox://${outputSlug}/growth-agency/video-739192841`;
    const timeScale = 1200;

    // Step 1: Ingestion
    schedule(() => {
      setActiveStep("ingestion");
      setSelectedNodeId("ingestion");
      addSystemLog(`Ingestando archivo de video: ${videoName}`);
      updateNodeProgressState("ingestion", { status: "running", progress: 40, itemsCount: 1 });
      updateNodeDataMap("ingestion", {
        status: "running",
        progress: 40,
        files: [{ name: videoName, type: "video/*", size: "Filename only" }],
        logs: [{
          sender: "Sensor Ingestion",
          message: `Registrando '${videoName}'. La demo sólo recibe el nombre; no sube ni decodifica el archivo.`,
          timestamp: new Date().toLocaleTimeString()
        }]
      });
    }, 100);

    schedule(() => {
      updateNodeProgressState("ingestion", { status: "success", progress: 100, itemsCount: 1 });
      updateNodeDataMap("ingestion", { status: "success", progress: 100 });
      addSystemLog("Manifiesto local creado. Research usará una transcripción fixture; no se almacenó el video.");
    }, 1 * timeScale);

    // Step 2: Research (Audio parsing & transcription)
    schedule(() => {
      setActiveStep("research");
      setSelectedNodeId("research");
      addSystemLog("ResearchAgent cargando una transcripción fixture del sandbox.");
      updateNodeProgressState("research", { status: "running", progress: 50, itemsCount: 1 });
      updateNodeDataMap("research", {
        status: "running",
        progress: 50,
        logs: [{
          sender: "ResearchAgent",
          message: "Simulando la salida de transcripción para demostrar el contrato de VideoOptimizerTool; no se leyó audio real.",
          timestamp: new Date().toLocaleTimeString()
        }]
      });
    }, 2 * timeScale);

    schedule(() => {
      updateNodeProgressState("research", { status: "success", progress: 100, itemsCount: 2 });
      updateNodeDataMap("research", {
        status: "success",
        progress: 100,
        logs: [
          {
            sender: "ResearchAgent",
            message: "Fixture de transcripción listo. Aplicando capa académica (Scholar Layer).",
            timestamp: new Date().toLocaleTimeString()
          },
          {
            sender: "ResearchAgent (Scholar Layer)",
            message: "El fixture representa una conversación sobre fallas de red en bases de datos. Scholar produjo este análisis de demostración:",
            timestamp: new Date().toLocaleTimeString(),
            isScholar: true,
            nlpExplanation: {
              reencuadre: "Los desarrolladores asumen que las transacciones SQL son mágicas. Reencuadramos esto mostrando que la red siempre falla en el peor momento posible.",
              tradeoff: "El dilema de la consistencia contra la disponibilidad (Teorema PACELC). Si quieres consistencia estricta, la latencia se dispara. No hay solución universal.",
              resolucion: "Configura timeouts correctos y retries con backoff exponencial. Aplica esto hoy para evitar la caída de tu base de datos de producción."
            }
          }
        ]
      });
      addSystemLog("Transcripción y Scholar NLP listos. Transfiriendo a Media para reframing.");
    }, 4 * timeScale);

    // Step 3: Media (Video Reframing)
    schedule(() => {
      setActiveStep("media");
      setSelectedNodeId("media");
      addSystemLog(`MediaAgent planificando re-framing y auto-captions para ${platform} en modo mock.`);
      updateNodeProgressState("media", { status: "running", progress: 45, itemsCount: 1 });
      updateNodeDataMap("media", {
        status: "running",
        progress: 45,
        logs: [{
          sender: "MediaAgent",
          message: `VideoOptimizerTool crea un manifiesto: relación ${targetFormat}, captions fixture y referencia sandbox. No renderiza el archivo.`,
          timestamp: new Date().toLocaleTimeString()
        }]
      });
    }, 5 * timeScale);

    schedule(() => {
      updateNodeProgressState("media", { status: "success", progress: 100, itemsCount: 2 });
      updateNodeDataMap("media", {
        status: "success",
        progress: 100,
        assets: [{
          name: `clip_${outputSlug}_optimizado.mp4`,
          type: "video",
          content: `sandbox://media/${outputSlug}/clip-optimized.mp4`
        }],
        logs: [
          {
            sender: "MediaAgent",
            message: `Plan de autocaptions y recorte ${targetFormat} completado como manifiesto sandbox para ${platform}.`,
            timestamp: new Date().toLocaleTimeString()
          }
        ]
      });
      addSystemLog("Manifiesto de optimización listo. Transfiriendo el fixture a Writer.");
    }, 7 * timeScale);

    // Step 4: Writer (Copywriting)
    schedule(() => {
      setActiveStep("writer");
      setSelectedNodeId("writer");
      addSystemLog("WriterAgent redactando copia persuasiva de acompañamiento.");
      updateNodeProgressState("writer", { status: "running", progress: 50, itemsCount: 1 });
      updateNodeDataMap("writer", {
        status: "running",
        progress: 50,
        logs: [{
          sender: "WriterAgent",
          message: "Integrando transcripción del Scholar y redactando el copy promocional...",
          timestamp: new Date().toLocaleTimeString()
        }]
      });
    }, 8 * timeScale);

    schedule(() => {
      const copyText = `🔥 ¿Confías ciegamente en tus transacciones SQL?\n\nTu base de datos está a un parpadeo de red de fallar. En sistemas distribuidos, la red no es confiable. Es el gran trade-off que Martin Kleppmann detalla en DDIA.\n\n👇 Entiende el dilema en este video y por qué no existen soluciones mágicas.\n\n#SoftwareEngineering #BasesDeDatos #SystemDesign #Coding`;
      updateNodeProgressState("writer", { status: "success", progress: 100, itemsCount: 1 });
      updateNodeDataMap("writer", {
        status: "success",
        progress: 100,
        assets: [{
          name: `Copy Promocional para ${platform}`,
          type: "text",
          content: copyText
        }],
        logs: [
          {
            sender: "WriterAgent",
            message: "Copy generado exitosamente incorporando el NLP Scholar Hook.",
            timestamp: new Date().toLocaleTimeString()
          }
        ]
      });
      addSystemLog("Copia de contenido creada. Enviando a Risk para auditoría de cumplimiento.");
    }, 10 * timeScale);

    // Step 5: Risk (Compliance Check)
    schedule(() => {
      setActiveStep("risk");
      setSelectedNodeId("risk");
      addSystemLog("RiskAgent auditando contenido.");
      updateNodeProgressState("risk", { status: "running", progress: 60, itemsCount: 0 });
      updateNodeDataMap("risk", {
        status: "running",
        progress: 60,
        logs: [{
          sender: "RiskAgent",
          message: "Escaneando copy por ortografía, políticas de plataforma y veracidad técnica.",
          timestamp: new Date().toLocaleTimeString()
        }]
      });
    }, 11 * timeScale);

    schedule(() => {
      updateNodeProgressState("risk", { status: "success", progress: 100, itemsCount: 0 });
      updateNodeDataMap("risk", {
        status: "success",
        progress: 100,
        logs: [{
          sender: "RiskAgent",
          message: "✅ Verificación Técnica y de Brand Safety superada. Video y copy aprobados.",
          timestamp: new Date().toLocaleTimeString()
        }]
      });
      addSystemLog("Aprobación de marca otorgada. Pendiente de greenlight del operador.");
      setApprovalReady(true);
    }, 13 * timeScale);

    // Step 6: Publisher
    deferUntilApproval(() => {
      setActiveStep("publisher");
      setSelectedNodeId("publisher");
      addSystemLog(`PublisherAgent preparando la cola sandbox para ${platform}.`);
      updateNodeProgressState("publisher", { status: "running", progress: 50, itemsCount: 1 });
      updateNodeDataMap("publisher", {
        status: "running",
        progress: 50,
        logs: [{
          sender: "PublisherAgent",
          message: `Modelando el contrato de ${platform} Ingestion. No se abrió una conexión ni se subió el video.`,
          timestamp: new Date().toLocaleTimeString()
        }]
      });
    }, 0.25 * timeScale);

    deferUntilApproval(() => {
      updateNodeProgressState("publisher", { status: "success", progress: 100, itemsCount: 1 });
      updateNodeDataMap("publisher", {
        status: "success",
        progress: 100,
        logs: [{
          sender: "PublisherAgent",
          message: `✅ Publicación simulada completada en ${platform}. Referencia local: ${publicationReference}`,
          timestamp: new Date().toLocaleTimeString()
        }]
      });
      addSystemLog("Referencia sandbox creada; no hubo publicación externa.");
    }, 2 * timeScale);

    // Step 7: CEO (Review)
    deferUntilApproval(() => {
      setActiveStep("ceo");
      setSelectedNodeId("ceo");
      addSystemLog("CEO Agent finalizando ciclo de campaña. Reportando estado.");
      updateNodeProgressState("ceo", { status: "success", progress: 100, itemsCount: 1 });
      updateNodeDataMap("ceo", {
        status: "success",
        progress: 100,
        logs: [{
          sender: "CEOAgent",
          message: `Ensayo de '${videoName}' completado para ${platform}. No existen vistas ni sensores externos en esta demo.`,
          timestamp: new Date().toLocaleTimeString()
        }]
      });
      setIsRunning(false);
      setActiveStep("");
      setApprovalReady(false);
      addSystemLog("Caso de Uso 1 finalizado con éxito.");
    }, 3 * timeScale);
  };

  // Use Case 2: Image-to-Video Motion Generation
  const runUseCase2 = (params: ImageSimulationParams) => {
    const imageName = params.imageName;
    const duration = params.duration;
    const style = params.style;
    const timeScale = 1200;

    // Step 1: Ingestion
    schedule(() => {
      setActiveStep("ingestion");
      setSelectedNodeId("ingestion");
      addSystemLog(`Ingestando imagen base: ${imageName}`);
      updateNodeProgressState("ingestion", { status: "running", progress: 50, itemsCount: 1 });
      updateNodeDataMap("ingestion", {
        status: "running",
        progress: 50,
        files: [{ name: imageName, type: "image/*", size: "Filename only" }],
        logs: [{
          sender: "Sensor Ingestion",
          message: `Registrando '${imageName}'. La demo sólo usa el nombre y no inspecciona píxeles ni resolución.`,
          timestamp: new Date().toLocaleTimeString()
        }]
      });
    }, 100);

    schedule(() => {
      updateNodeProgressState("ingestion", { status: "success", progress: 100, itemsCount: 1 });
      updateNodeDataMap("ingestion", { status: "success", progress: 100 });
      addSystemLog("Manifiesto de imagen listo. Media simulará un plan de motion; Runway no será contactado.");
    }, 1 * timeScale);

    // Step 2: Media (Image-to-Video API)
    schedule(() => {
      setActiveStep("media");
      setSelectedNodeId("media");
      addSystemLog(`ImageToVideoTool modelando ${duration}s con estilo '${style}' en modo mock.`);
      updateNodeProgressState("media", { status: "running", progress: 30, itemsCount: 1 });
      updateNodeDataMap("media", {
        status: "running",
        progress: 30,
        logs: [{
          sender: "MediaAgent",
          message: `Creando storyboard y referencia sandbox para '${style}' por ${duration}s. No se invoca una API de video.`,
          timestamp: new Date().toLocaleTimeString()
        }]
      });
    }, 2 * timeScale);

    schedule(() => {
      updateNodeProgressState("media", { status: "success", progress: 100, itemsCount: 2 });
      updateNodeDataMap("media", {
        status: "success",
        progress: 100,
        assets: [{
          name: `motion_clip_${duration}s.mp4`,
          type: "video",
          content: "sandbox://media/motion-clip-9281.mp4"
        }],
        logs: [{
          sender: "MediaAgent",
          message: `Manifiesto de motion de ${duration}s listo en estilo ${style}. No se generó media real.`,
          timestamp: new Date().toLocaleTimeString()
        }]
      });
      addSystemLog("Plan de motion sandbox listo. Enviando a Strategist para segmentación.");
    }, 5 * timeScale);

    // Step 3: Strategist (Audience mapping)
    schedule(() => {
      setActiveStep("strategist");
      setSelectedNodeId("strategist");
      addSystemLog("StrategistAgent mapeando audiencias y canales de distribución.");
      updateNodeProgressState("strategist", { status: "running", progress: 50, itemsCount: 1 });
      updateNodeDataMap("strategist", {
        status: "running",
        progress: 50,
        logs: [{
          sender: "StrategistAgent",
          message: `Analizando similitud de marca del video con segmentos tech. Target principal: Emprendedores y Builders.`,
          timestamp: new Date().toLocaleTimeString()
        }]
      });
    }, 6 * timeScale);

    schedule(() => {
      updateNodeProgressState("strategist", { status: "success", progress: 100, itemsCount: 2 });
      updateNodeDataMap("strategist", {
        status: "success",
        progress: 100,
        logs: [{
          sender: "StrategistAgent",
          message: "Canales seleccionados: LinkedIn (Profesional), X (Developer Relations). Estrategia de pauta validada.",
          timestamp: new Date().toLocaleTimeString()
        }]
      });
      addSystemLog("Estrategia aprobada. Enviando a Writer.");
    }, 8 * timeScale);

    // Step 4: Writer (Copia)
    schedule(() => {
      setActiveStep("writer");
      setSelectedNodeId("writer");
      addSystemLog("WriterAgent redactando copia para LinkedIn y X.");
      updateNodeProgressState("writer", { status: "running", progress: 50, itemsCount: 1 });
      updateNodeDataMap("writer", {
        status: "running",
        progress: 50,
        logs: [{
          sender: "WriterAgent",
          message: "Redactando hooks enfocados en la velocidad y el valor estético de las marcas tech...",
          timestamp: new Date().toLocaleTimeString()
        }]
      });
    }, 9 * timeScale);

    schedule(() => {
      const copyText = `La estética es el nuevo código de barras de tu SaaS.\n\nSi tu software se ve anticuado, tus clientes asumirán que tu infraestructura también lo está. Diseña con intención. Construye para impactar.\n\nDescubre cómo unificamos estética premium y robustez técnica en este clip.`;
      updateNodeProgressState("writer", { status: "success", progress: 100, itemsCount: 1 });
      updateNodeDataMap("writer", {
        status: "success",
        progress: 100,
        assets: [{
          name: "Copy de Marca Premium (LinkedIn)",
          type: "text",
          content: copyText
        }],
        logs: [{
          sender: "WriterAgent",
          message: "Textos promocionales creados con éxito.",
          timestamp: new Date().toLocaleTimeString()
        }]
      });
      addSystemLog("Copia lista. Enviando a Risk.");
    }, 11 * timeScale);

    // Step 5: Risk (Compliance)
    schedule(() => {
      setActiveStep("risk");
      setSelectedNodeId("risk");
      addSystemLog("RiskAgent evaluando cumplimiento.");
      updateNodeProgressState("risk", { status: "running", progress: 70, itemsCount: 0 });
      updateNodeDataMap("risk", {
        status: "running",
        progress: 70,
        logs: [{
          sender: "RiskAgent",
          message: "Validando derechos de imagen base y consistencia tipográfica del copy.",
          timestamp: new Date().toLocaleTimeString()
        }]
      });
    }, 12 * timeScale);

    schedule(() => {
      updateNodeProgressState("risk", { status: "success", progress: 100, itemsCount: 0 });
      updateNodeDataMap("risk", {
        status: "success",
        progress: 100,
        logs: [{
          sender: "RiskAgent",
          message: "QA local completado sobre el manifiesto y el copy. No se validó media renderizada ni una política externa.",
          timestamp: new Date().toLocaleTimeString()
        }]
      });
      addSystemLog("Cumplimiento verificado. Publisher espera el greenlight del operador.");
      setApprovalReady(true);
    }, 14 * timeScale);

    // Step 6: Publisher
    deferUntilApproval(() => {
      setActiveStep("publisher");
      setSelectedNodeId("publisher");
      addSystemLog("PublisherAgent preparando referencias locales de entrega...");
      updateNodeProgressState("publisher", { status: "running", progress: 40, itemsCount: 1 });
      updateNodeDataMap("publisher", {
        status: "running",
        progress: 40,
        logs: [{
          sender: "PublisherAgent",
          message: "Modelando una cola para X y LinkedIn. No se contactaron APIs ni se programaron publicaciones reales.",
          timestamp: new Date().toLocaleTimeString()
        }]
      });
    }, 0.25 * timeScale);

    deferUntilApproval(() => {
      updateNodeProgressState("publisher", { status: "success", progress: 100, itemsCount: 1 });
      updateNodeDataMap("publisher", {
        status: "success",
        progress: 100,
        logs: [{
          sender: "PublisherAgent",
          message: "Pack marcado sandbox-queued para X y LinkedIn; sin publicación externa.",
          timestamp: new Date().toLocaleTimeString()
        }]
      });
      addSystemLog("Ensayo de publicación completado dentro del sandbox.");
    }, 2 * timeScale);

    // Step 7: CEO
    deferUntilApproval(() => {
      setActiveStep("ceo");
      setSelectedNodeId("ceo");
      addSystemLog("CEO Agent cerrando simulación.");
      updateNodeProgressState("ceo", { status: "success", progress: 100, itemsCount: 1 });
      updateNodeDataMap("ceo", {
        status: "success",
        progress: 100,
        logs: [{
          sender: "CEOAgent",
          message: "Caso 2 completado como ensayo. El manifiesto permanece local y no está en circulación.",
          timestamp: new Date().toLocaleTimeString()
        }]
      });
      setIsRunning(false);
      setActiveStep("");
      setApprovalReady(false);
      addSystemLog("Caso de Uso 2 finalizado con éxito.");
    }, 3 * timeScale);
  };

  // Use Case 3: Text Prompt to Full Campaign & Paid Ad Pack
  const runUseCase3 = (params: CampaignSimulationParams) => {
    const promptText = params.prompt;
    const audience = params.audience;
    const budget = params.budget;
    const durationDays = params.durationDays;
    const channels = params.channels;
    const activeSkills = (Object.entries(enabledSkills) as Array<[SkillId, boolean]>)
      .filter(([, isEnabled]) => isEnabled)
      .map(([skillId]) => skillId);
    const campaignPackage = packageCampaign({
      thesis: promptText,
      audience,
      channels,
      durationDays,
      budget,
      enabledSkills: activeSkills,
    });
    const campaignId = `${campaignPackage.campaignId}-${Date.now()}`;
    const campaignLabel = campaignPackage.thesis.slice(0, 54);
    const channelsLabel = channels.join(", ");
    const recalledMemory = memoryFlags.at(-1)?.content
      ?? "No operator flag stored; use evidence-led tone and reversible decisions.";
    const trendSummary = campaignPackage.trendMix.insights
      .map((insight) => `${insight.platform}: ${insight.topic} (${insight.momentum}%)`)
      .join(" · ");
    const [reframe, tradeoff, resolution] = campaignPackage.trendMix.scholar;
    const timeScale = 1200;

    // Step 1: Ingestion
    schedule(() => {
      setActiveStep("ingestion");
      setSelectedNodeId("ingestion");
      addSystemLog(`Ingestando prompt de campaña: '${promptText}'`);
      updateNodeProgressState("ingestion", { status: "running", progress: 50, itemsCount: 1 });
      updateNodeDataMap("ingestion", {
        status: "running",
        progress: 50,
        files: [{ name: "brief_prompt.txt", type: "text/plain", size: `${promptText.length} bytes` }],
        logs: [{
          sender: "Sensor Ingestion",
          message: `Registrando prompt de entrada. Analizando requerimientos de pauta publicitaria.`,
          timestamp: new Date().toLocaleTimeString()
        }]
      });
    }, 100);

    schedule(() => {
      updateNodeProgressState("ingestion", { status: "success", progress: 100, itemsCount: 1 });
      updateNodeDataMap("ingestion", { status: "success", progress: 100 });
      addSystemLog("Prompt ingestado. Transfiriendo a CEO para definir presupuesto y canales.");
    }, 1 * timeScale);

    // Step 2: CEO (Brief definition)
    schedule(() => {
      setActiveStep("ceo");
      setSelectedNodeId("ceo");
      addSystemLog("CEO Agent estructurando metas de la campaña y presupuesto.");
      updateNodeProgressState("ceo", { status: "running", progress: 40, itemsCount: 1 });
      updateNodeDataMap("ceo", {
        status: "running",
        progress: 40,
        logs: [{
          sender: "CEOAgent",
          message: `Estructurando '${campaignLabel}' para ${durationDays} días. Presupuesto sandbox: $${budget}. Audiencia: ${audience}. Canales: ${channelsLabel}.`,
          timestamp: new Date().toLocaleTimeString()
        }]
      });
    }, 2 * timeScale);

    schedule(() => {
      updateNodeProgressState("ceo", { status: "success", progress: 100, itemsCount: 1 });
      updateNodeDataMap("ceo", { status: "success", progress: 100 });
      addSystemLog("Objetivos de campaña validados. Enviando a Research para extraer base teórica del libro.");
    }, 3 * timeScale);

    // Step 3: Research (Scholar Layer)
    schedule(() => {
      setActiveStep("research");
      setSelectedNodeId("research");
      addSystemLog("ResearchAgent recuperando los resúmenes locales de AI-native y DDIA para la tesis indicada.");
      updateNodeProgressState("research", { status: "running", progress: 60, itemsCount: 3 });
      updateNodeDataMap("research", {
        status: "running",
        progress: 60,
        logs: [{
          sender: "ResearchAgent",
          message: `Buscando modelos aplicables a '${campaignLabel}' sin atribuir citas textuales no verificadas. Memoria recuperada: ${recalledMemory}`,
          timestamp: new Date().toLocaleTimeString()
        }]
      });
    }, 4 * timeScale);

    schedule(() => {
      updateNodeProgressState("research", { status: "success", progress: 100, itemsCount: 3 });
      updateNodeDataMap("research", {
        status: "success",
        progress: 100,
        logs: [
          {
            sender: "ResearchAgent",
            message: `Ancla conceptual seleccionada para '${campaignLabel}': las decisiones de arquitectura y negocio desplazan costes; no existe una solución universal. Memoria recuperada: ${recalledMemory}. Capa Scholar activada:`,
            timestamp: new Date().toLocaleTimeString()
          },
          {
            sender: "ResearchAgent (Scholar Layer)",
            message: "Análisis conceptual estructurado bajo el patrón NLP de 3 balas:",
            timestamp: new Date().toLocaleTimeString(),
            isScholar: true,
            nlpExplanation: {
              reencuadre: reframe.explanation,
              tradeoff: tradeoff.explanation,
              resolucion: resolution.explanation,
            }
          }
        ]
      });
      addSystemLog("Scholar de tres puntos listo. Enviando a Strategist para mezclar cuatro señales sociales sintéticas.");
    }, 6 * timeScale);

    // Step 4: Strategist (Trend-Mixing Loop)
    schedule(() => {
      setActiveStep("strategist");
      setSelectedNodeId("strategist");
      addSystemLog("StrategistAgent ejecutando MultiPlatformTrendsTool...");
      updateNodeProgressState("strategist", { status: "running", progress: 50, itemsCount: 4 });
      updateNodeDataMap("strategist", {
        status: "running",
        progress: 50,
        logs: [{
          sender: "StrategistAgent",
          message: `MultiPlatformTrendsTool en modo fixture, sin red. Señales: ${trendSummary}. Skills: ${activeSkills.join(", ") || "baseline"}.`,
          timestamp: new Date().toLocaleTimeString()
        }]
      });
    }, 7 * timeScale);

    schedule(() => {
      updateNodeProgressState("strategist", { status: "success", progress: 100, itemsCount: 4 });
      updateNodeDataMap("strategist", {
        status: "success",
        progress: 100,
        logs: [{
          sender: "StrategistAgent",
          message: `Mix formulado para '${campaignLabel}' en ${channelsLabel}. Cada señal conserva formato nativo y Scholar; ninguna tendencia fue consultada en vivo.`,
          timestamp: new Date().toLocaleTimeString()
        }]
      });
      addSystemLog("Estrategia de tendencia lista. Enviando a Growth para diseñar distribución.");
    }, 9 * timeScale);

    // Step 5: Growth (Territory & distribution routes)
    schedule(() => {
      setActiveStep("growth");
      setSelectedNodeId("growth");
      addSystemLog("GrowthAgent priorizando comunidades, canales y ventanas de distribución.");
      updateNodeProgressState("growth", { status: "running", progress: 58, itemsCount: 3 });
      updateNodeDataMap("growth", {
        status: "running",
        progress: 58,
        logs: [{
          sender: "GrowthAgent",
          message: `Modelando ${campaignPackage.schedule.length} rutas sandbox para ${channelsLabel}, distribuidas durante ${durationDays} días y sin automatizar DMs reales.`,
          timestamp: new Date().toLocaleTimeString()
        }]
      });
    }, 9.2 * timeScale);

    schedule(() => {
      updateNodeProgressState("growth", { status: "success", progress: 100, itemsCount: 3 });
      updateNodeDataMap("growth", {
        status: "success",
        progress: 100,
        logs: [{
          sender: "GrowthAgent",
          message: `Ruta lista: ${campaignPackage.schedule.map((slot) => `${slot.channel}@+${slot.offsetHours}h`).join(" → ")}.`,
          timestamp: new Date().toLocaleTimeString()
        }]
      });
      addSystemLog("Growth route validada. Entregando contexto de canal al Writer.");
    }, 9.8 * timeScale);

    // Step 6: Writer (Redacción Copy & Ad Creatives)
    schedule(() => {
      setActiveStep("writer");
      setSelectedNodeId("writer");
      addSystemLog("WriterAgent estructurando el pack de contenidos persuasivos.");
      updateNodeProgressState("writer", { status: "running", progress: 45, itemsCount: 1 });
      updateNodeDataMap("writer", {
        status: "running",
        progress: 45,
        logs: [{
          sender: "WriterAgent",
          message: `CampaignPackagerTool componiendo thread de 3 partes, newsletter, video hook y paid concept. Recall aplicado: ${recalledMemory}`,
          timestamp: new Date().toLocaleTimeString()
        }]
      });
    }, 10 * timeScale);

    schedule(() => {
      const xThread = campaignPackage.thread.map((part) => part.copy).join("\n\n");
      const metaCopy = `${campaignPackage.paidConcept.primaryText}\n\n${campaignPackage.paidConcept.headline}\nCTA: ${campaignPackage.paidConcept.callToAction}\nDaily sandbox budget: $${campaignPackage.paidConcept.dailyBudget}`;
      const newsletter = `${campaignPackage.newsletter.subject}\n${campaignPackage.newsletter.preheader}\n\n${campaignPackage.newsletter.introduction}\n\n${campaignPackage.newsletter.sections.map((section) => `${section.label}: ${section.explanation}`).join("\n\n")}\n\n${campaignPackage.newsletter.closing}`;

      updateNodeProgressState("writer", { status: "success", progress: 100, itemsCount: 3 });
      updateNodeDataMap("writer", {
        status: "success",
        progress: 100,
        assets: [
          {
            name: "Hilo de X (Orgánico)",
            type: "text",
            content: xThread
          },
          {
            name: "Ad Copy para Meta Ads (Pagado)",
            type: "text",
            content: metaCopy
          },
          {
            name: "Newsletter / Scholar Edition",
            type: "text",
            content: newsletter
          }
        ],
        logs: [{
          sender: "WriterAgent",
          message: `Pack sandbox creado con 3 partes de thread, newsletter y paid concept para ${channelsLabel}.`,
          timestamp: new Date().toLocaleTimeString()
        }]
      });
      addSystemLog("Copia generada con éxito. Enviando a Media para los diseños del ad pack.");
    }, 12 * timeScale);

    // Step 6: Media (Visual assets)
    schedule(() => {
      setActiveStep("media");
      setSelectedNodeId("media");
      addSystemLog("MediaAgent creando manifiestos locales para imagen y video hook; no invocará un generador externo.");
      updateNodeProgressState("media", { status: "running", progress: 50, itemsCount: 2 });
      updateNodeDataMap("media", {
        status: "running",
        progress: 50,
        logs: [{
          sender: "MediaAgent",
          message: `Planificando visual para '${campaignLabel}' y video hook de ${campaignPackage.videoHook.durationSeconds}s: ${campaignPackage.videoHook.visualDirection}`,
          timestamp: new Date().toLocaleTimeString()
        }]
      });
    }, 13 * timeScale);

    schedule(() => {
      updateNodeProgressState("media", { status: "success", progress: 100, itemsCount: 2 });
      updateNodeDataMap("media", {
        status: "success",
        progress: 100,
        assets: [
          {
            name: "paid-concept-dark-slate.image-manifest",
            type: "image",
            content: `${campaignPackage.campaignId}/image-concept`
          },
          {
            name: "campaign-hook.video-manifest",
            type: "video",
            content: `${campaignPackage.campaignId}/video-hook`
          }
        ],
        logs: [{
          sender: "MediaAgent",
          message: "Manifiestos de preview generados localmente. No se renderizó ni descargó media real.",
          timestamp: new Date().toLocaleTimeString()
        }]
      });
      addSystemLog("Creativo de anuncio listo. Enviando todo a Risk para la auditoría de políticas.");
    }, 15 * timeScale);

    // Step 7: Risk (Compliance Check)
    schedule(() => {
      setActiveStep("risk");
      setSelectedNodeId("risk");
      addSystemLog("RiskAgent auditando campaña completa y código de ad set.");
      updateNodeProgressState("risk", { status: "running", progress: 65, itemsCount: 0 });
      updateNodeDataMap("risk", {
        status: "running",
        progress: 65,
        logs: [{
          sender: "RiskAgent",
          message: `${enabledSkills["brand-guard"] ? "Brand Guard activo" : "Baseline QA activo"}: revisando precisión, promesas, tono y referencias sandbox. Constraint recuperado: ${recalledMemory}`,
          timestamp: new Date().toLocaleTimeString()
        }]
      });
    }, 16 * timeScale);

    schedule(() => {
      updateNodeProgressState("risk", { status: "success", progress: 100, itemsCount: 0 });
      updateNodeDataMap("risk", {
        status: "success",
        progress: 100,
        logs: [{
          sender: "RiskAgent",
          message: "QA sandbox completado sin hallazgos en las reglas locales. Esto no sustituye una revisión legal ni una validación real de Meta Ads.",
          timestamp: new Date().toLocaleTimeString()
        }]
      });
      addSystemLog("QA sandbox completado; apto para decisión humana, sin validación regulatoria externa.");
      setApprovalReady(true);
    }, 18 * timeScale);

    // Step 8: Publisher (Meta Ads MCP integration)
    deferUntilApproval(() => {
      setActiveStep("publisher");
      setSelectedNodeId("publisher");
      addSystemLog("PublisherAgent preparando un borrador local mediante el contrato MetaAdsMcpTool...");
      updateNodeProgressState("publisher", { status: "running", progress: 30, itemsCount: 1 });
      updateNodeDataMap("publisher", {
        status: "running",
        progress: 30,
        logs: [{
          sender: "PublisherAgent",
          message: `MetaAdsMcpTool permanece en mock. Modelando '${campaignLabel}', $${budget} durante ${durationDays} días, audiencia '${audience}', canales ${campaignPackage.paidConcept.channels.join(", ")}.`,
          timestamp: new Date().toLocaleTimeString()
        }]
      });
    }, 0.25 * timeScale);

    deferUntilApproval(() => {
      const topicInterests = campaignPackage.thesis
        .split(/[^\p{L}\p{N}]+/u)
        .map((token) => token.trim())
        .filter((token) => token.length >= 4)
        .slice(0, 4);
      // Create a sandbox-only campaign record in the local dashboard.
      const newCamp: MetaAdsCampaign = {
        id: campaignId,
        name: `Scholar Campaign: ${campaignLabel}`,
        budget: budget,
        spent: 0,
        ctr: 0.00,
        cac: 0.00,
        impressions: 0,
        conversions: 0,
        status: "active",
        targeting: {
          demographics: audience,
          interests: topicInterests.length > 0 ? topicInterests : ["Decision systems"],
          locations: ["Sandbox / not geo-targeted"]
        }
      };
      
      setMetaCampaigns(prev => [newCamp, ...prev]);
      updateNodeProgressState("publisher", { status: "success", progress: 100, itemsCount: 2 });
      updateNodeDataMap("publisher", {
        status: "success",
        progress: 100,
        logs: [
          {
            sender: "PublisherAgent",
            message: `Pack marcado como sandbox-queued para ${channelsLabel}. No se publicó contenido externo.`,
            timestamp: new Date().toLocaleTimeString()
          },
          {
            sender: "PublisherAgent (Meta Ads MCP)",
            message: `Borrador local ${campaignPackage.campaignId} creado. Puja modelada; Meta Ads Manager no fue contactado y no existe gasto real.`,
            timestamp: new Date().toLocaleTimeString()
          }
        ]
      });
      addSystemLog("Pack orgánico y paid-ad draft registrados en el estado local del sandbox.");
    }, 2 * timeScale);

    // Step 9: CEO (Confirmation & Feedback loop)
    deferUntilApproval(() => {
      setActiveStep("ceo");
      setSelectedNodeId("ceo");
      addSystemLog("CEO Agent cerrando el flujo y aplicando un pulso sintético de métricas.");
      updateNodeProgressState("ceo", { status: "success", progress: 100, itemsCount: 2 });
      updateNodeDataMap("ceo", {
        status: "success",
        progress: 100,
        logs: [{
          sender: "CEOAgent",
          message: `Campaña '${campaignLabel}' quedó activa sólo en el dashboard local. Plan: ${durationDays} días, $${budget}, ${channelsLabel}. El feedback sintético alimentará una memoria para el siguiente ciclo.`,
          timestamp: new Date().toLocaleTimeString()
        }]
      });

      // Apply the deterministic feedback before the run closes so the next cycle cannot cancel it.
      const simulatedSpend = Math.min(120, budget);
      const simulatedConversions = Math.max(1, Math.round(simulatedSpend / 8));
      const simulatedCac = Number((simulatedSpend / simulatedConversions).toFixed(2));
      setMetaCampaigns(prev => prev.map(c => {
        if (c.id === campaignId) {
          return {
            ...c,
            spent: simulatedSpend,
            impressions: 4500,
            conversions: simulatedConversions,
            ctr: 2.34,
            cac: simulatedCac
          };
        }
        return c;
      }));
      const feedbackMemory: SessionMemoryFlag = {
        id: `feedback-${campaignId}`,
        content: `Priorizar el hook de ${campaignPackage.videoHook.channels.join("/")} y mantener un CAC sandbox de referencia cercano a $${simulatedCac}.`,
        provenance: "Synthetic Meta metrics → CEO feedback · Current session",
        confidence: 82,
      };
      setMemoryFlags((current) => [...current, feedbackMemory]);
      addSystemLog(`Pulso sintético: CTR 2.34%, CAC $${simulatedCac}. CEO lo almacenó como memoria de optimización para el siguiente ciclo.`);

      setIsRunning(false);
      setActiveStep("");
      setApprovalReady(false);
      addSystemLog("Caso de Uso 3 finalizado con éxito.");
    }, 3 * timeScale);
  };

  const completedNodes = Object.values(nodeStates).filter((node) => node.status === "success").length;
  const overallProgress = Math.round(
    Object.values(nodeStates).reduce((total, node) => total + node.progress, 0) /
      Object.keys(nodeStates).length,
  );
  const activeNodeName = activeStep ? nodeDataMap[activeStep]?.name : "Awaiting mission";

  return (
    <div className="relative min-h-screen w-full overflow-x-clip bg-[var(--bg-obsidian)] font-sans text-[var(--text-light)]">
      <a href="#main-content" className="skip-link">Saltar al contenido principal</a>
      <CanvasBackground />
      <div className="scene-vignette" aria-hidden="true" />
      <div className="scene-noise" aria-hidden="true" />

      <header className="app-header relative z-40 border-b border-white/[0.06] backdrop-blur-xl">
        <div className="mx-auto flex w-full max-w-[1840px] flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
          <div className="flex min-w-0 items-center gap-3">
            <div className="brand-glyph" aria-hidden="true">
              <span /><span /><Cpu size={17} />
            </div>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-sm font-extrabold tracking-[-0.02em] text-white">NATIVE / WAR ROOM</p>
                <span className="rounded-full border border-white/[0.08] bg-white/[0.035] px-2 py-0.5 font-mono text-[9px] text-zinc-400">ALPHA 02</span>
              </div>
              <p className="mt-0.5 truncate text-[11px] text-zinc-500">Sandbox content operations · local simulation workspace</p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2 text-[11px]">
            <span className="status-pill">
              <Layers size={12} aria-hidden="true" /> 8-station architecture
            </span>
            <span className="status-pill status-pill--amber">
              <Wifi size={12} aria-hidden="true" /> MCP adapters simulated
            </span>
            <span className={`status-pill ${isRunning ? "status-pill--live" : ""}`}>
              <span className={`h-1.5 w-1.5 rounded-full ${isRunning ? "animate-pulse bg-emerald-300" : "bg-zinc-500"}`} />
              {isRunning ? "Cycle running" : "Local standby"}
            </span>
          </div>
        </div>
      </header>

      <main id="main-content" tabIndex={-1} className="relative z-10 mx-auto w-full max-w-[1840px] px-4 pb-12 pt-5 sm:px-6 lg:px-8 lg:pb-16">
        <section aria-labelledby="hero-title" className="hero-stage">
          <div className="hero-copy">
            <div className="coordinate-tag">
              <span>OPS / GT-14.63</span>
              <i />
              <span>SESSION 0248</span>
            </div>
            <p className="mt-8 flex items-center gap-2 font-mono text-[10px] font-semibold uppercase tracking-[0.22em] text-[var(--primary-color)]">
              <Sparkles size={13} aria-hidden="true" /> AI-native campaign intelligence
            </p>
            <h1 id="hero-title" className="hero-title">
              Convierte una señal en una <span>campaña completa.</span>
            </h1>
            <p className="mt-5 max-w-2xl text-sm leading-7 text-zinc-400 sm:text-base sm:leading-8">
              Ocho agentes especializados investigan, diseñan, producen, auditan y distribuyen contenido desde una sola sala de operaciones. Cada decisión conserva contexto, trade-offs y un gate humano visible.
            </p>

            <div className="mt-7 grid max-w-2xl grid-cols-2 gap-px overflow-hidden rounded-xl border border-white/[0.07] bg-white/[0.07] sm:grid-cols-4">
              <div className="hero-stat"><strong>08</strong><span>agents</span></div>
              <div className="hero-stat"><strong>03</strong><span>missions</span></div>
              <div className="hero-stat"><strong>{String(completedNodes).padStart(2, "0")}</strong><span>complete</span></div>
              <div className="hero-stat"><strong>{String(overallProgress).padStart(2, "0")}%</strong><span>cycle</span></div>
            </div>
          </div>

          <div className="orchestration-visual" aria-hidden="true">
            <div className="orchestration-halo" />
            <div className="orbit-ring orbit-ring--outer"><span /><span /><span /></div>
            <div className="orbit-ring orbit-ring--inner"><span /><span /></div>
            <div className="orchestration-core">
              <Cpu size={24} />
              <strong>08</strong>
              <small>AGENTS / SANDBOX</small>
            </div>
            <span className="orbit-tag orbit-tag--one">SCHOLAR / 02</span>
            <span className="orbit-tag orbit-tag--two">MEDIA / 06</span>
            <span className="orbit-tag orbit-tag--three">RISK / 07</span>
          </div>
        </section>

        <section aria-labelledby="mission-control-title" className="mt-10 lg:mt-14">
          <div className="section-heading">
            <div>
              <p className="section-kicker">01 / COMMAND</p>
              <h2 id="mission-control-title">Define la misión. Observa el sistema.</h2>
            </div>
            <p>El pipeline usa datos simulados para demostrar la interacción end-to-end sin ejecutar publicaciones ni gasto real.</p>
          </div>

          <div className="mt-5 grid items-start gap-5 xl:grid-cols-[minmax(330px,0.72fr)_minmax(0,1.65fr)] 2xl:gap-6">
            <div className="surface-panel p-4 sm:p-5">
              <div className="mb-5 flex items-center justify-between border-b border-white/[0.07] pb-4">
                <div className="flex items-center gap-3">
                  <span className="grid h-10 w-10 place-items-center rounded-xl border border-white/[0.08] bg-white/[0.035] text-[var(--primary-color)]">
                    <Sliders size={16} aria-hidden="true" />
                  </span>
                  <div>
                    <p className="text-sm font-bold text-zinc-100">Mission launcher</p>
                    <p className="mt-0.5 font-mono text-[9px] uppercase tracking-[0.12em] text-zinc-500">Compose / configure / launch</p>
                  </div>
                </div>
                <span className="font-mono text-[9px] text-zinc-600">CMD-01</span>
              </div>
              <ControlPanel
                onRunSimulation={handleRunSimulation}
                isRunning={isRunning}
                activeTheme={themeId}
                premiumThemeEntitled={premiumThemeEntitled}
                onThemeChange={changeTheme}
              />
            </div>

            <div className="min-w-0">
              <div className="mb-3 flex flex-wrap items-end justify-between gap-3 px-1">
                <div>
                  <p className="section-kicker">LIVE TOPOLOGY / FABRIC FLOW</p>
                  <h3 className="mt-1 text-base font-bold text-zinc-100">Eight-station orchestration map</h3>
                </div>
                <div className="flex items-center gap-2 rounded-full border border-white/[0.07] bg-black/20 px-3 py-1.5 font-mono text-[10px] text-zinc-400" aria-live="polite">
                  <span className={`h-1.5 w-1.5 rounded-full ${activeStep ? "animate-pulse bg-[var(--primary-color)]" : "bg-zinc-600"}`} />
                  {activeNodeName}
                </div>
              </div>
              <PipelineGraph
                activeStep={activeStep}
                nodeStates={nodeStates}
                selectedNodeId={selectedNodeId}
                onNodeSelect={setSelectedNodeId}
              />
            </div>
          </div>
        </section>

        <section aria-labelledby="operations-title" className="mt-10 lg:mt-14">
          <div className="section-heading">
            <div>
              <p className="section-kicker">02 / OBSERVE & APPROVE</p>
              <h2 id="operations-title">Trazabilidad, entregables y feedback loop.</h2>
            </div>
            <p>Inspecciona decisiones por agente, revisa outputs y observa la simulación de métricas antes del greenlight.</p>
          </div>

          <div className="mt-5 grid items-start gap-5 2xl:grid-cols-[minmax(330px,0.82fr)_minmax(380px,1fr)_minmax(390px,0.92fr)] 2xl:gap-6">
            <InteractiveSidebar
              nodeData={selectedNodeId ? nodeDataMap[selectedNodeId] : null}
              onClose={() => setSelectedNodeId(null)}
              isApproved={isApproved}
              canApprove={approvalReady || isApproved}
              onApproveToggle={handleApprovalToggle}
            />

            <div className="surface-panel overflow-hidden">
              <header className="flex items-center justify-between gap-3 border-b border-white/[0.07] px-4 py-4 sm:px-5">
                <div className="flex items-center gap-3">
                  <span className="grid h-9 w-9 place-items-center rounded-lg bg-sky-400/[0.08] text-sky-300">
                    <Terminal size={14} aria-hidden="true" />
                  </span>
                  <div>
                    <h3 className="text-sm font-bold text-zinc-100">War Room transmission</h3>
                    <p className="mt-0.5 font-mono text-[9px] uppercase tracking-[0.12em] text-zinc-500">Local event stream</p>
                  </div>
                </div>
                <span className="rounded-full border border-white/[0.07] px-2 py-1 font-mono text-[9px] text-zinc-500">v2.0-sim</span>
              </header>
              <div className="system-terminal max-h-[540px] min-h-[360px] overflow-y-auto p-4 sm:p-5" aria-live="polite" aria-label="Eventos recientes del War Room">
                {systemLogs.slice(-18).map((log, index) => (
                  <div key={`${index}-${log}`} className="terminal-line">
                    <span>{String(index + 1).padStart(2, "0")}</span>
                    <i />
                    <p>{log}</p>
                  </div>
                ))}
              </div>
            </div>

            <div className="surface-panel p-4 sm:p-5">
              <MetaAdsDashboard
                campaigns={metaCampaigns}
                isSyncing={isAdsSyncing}
                onSync={handleManualSync}
              />
            </div>
          </div>
        </section>

        <div className="mt-10 lg:mt-14">
          <ProductionRuntimePanel onEntitlementsChange={setRuntimeEntitlements} />
        </div>

        <div className="mt-10 lg:mt-14">
          <MemorySkillsPanel
            enabledSkills={enabledSkills}
            memoryFlags={memoryFlags}
            onToggleSkill={handleSkillToggle}
            onAddMemoryFlag={handleAddMemoryFlag}
          />
        </div>

        <div className="mt-10 lg:mt-14">
          <ToolFabricPanel />
        </div>
      </main>

      <footer className="relative z-10 border-t border-white/[0.06] bg-black/20">
        <div className="mx-auto flex w-full max-w-[1840px] flex-col gap-3 px-4 py-4 text-[11px] text-zinc-500 sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
          <div className="flex items-center gap-2">
            <ShieldCheck size={13} className="text-[var(--primary-color)]" aria-hidden="true" />
            <span>Risk, brand and operator gates remain visible throughout the cycle.</span>
          </div>
          <div className="flex flex-wrap gap-x-4 gap-y-1 font-mono text-[9px] uppercase tracking-[0.1em] text-zinc-600">
            <span>Local simulation</span><span>No live spend</span><span>© 2026 Native Agency OS</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
