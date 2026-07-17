import { useState, useEffect } from "react";
import { CanvasBackground } from "./components/CanvasBackground";
import { ControlPanel } from "./components/ControlPanel";
import { PipelineGraph } from "./components/PipelineGraph";
import type { NodeState } from "./components/PipelineGraph";
import { InteractiveSidebar } from "./components/InteractiveSidebar";
import { MetaAdsDashboard } from "./components/MetaAdsDashboard";
import type { MetaAdsCampaign } from "./components/MetaAdsDashboard";
import { GlowCard } from "./components/GlowCard";
import { 
  Terminal, 
  Cpu, 
  Layers, 
  Wifi, 
  ShieldCheck,
  Sliders
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

const DEFAULT_NODE_STATES: Record<string, NodeState> = {
  ingestion: { status: "idle", progress: 0, itemsCount: 0, itemsLabel: "archivos" },
  ceo: { status: "idle", progress: 0, itemsCount: 0, itemsLabel: "briefs" },
  research: { status: "idle", progress: 0, itemsCount: 0, itemsLabel: "conceptos" },
  media: { status: "idle", progress: 0, itemsCount: 0, itemsLabel: "assets" },
  strategist: { status: "idle", progress: 0, itemsCount: 0, itemsLabel: "canales" },
  writer: { status: "idle", progress: 0, itemsCount: 0, itemsLabel: "copys" },
  risk: { status: "idle", progress: 0, itemsCount: 0, itemsLabel: "alertas" },
  publisher: { status: "idle", progress: 0, itemsCount: 0, itemsLabel: "campañas" }
};

export default function App() {
  const [activeStep, setActiveStep] = useState<string>("");
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>("ingestion");
  const [isApproved, setIsApproved] = useState<boolean>(false);
  const [isAdsSyncing, setIsAdsSyncing] = useState<boolean>(false);
  
  // Terminal log messages
  const [systemLogs, setSystemLogs] = useState<string[]>([
    "System booted. Obsidian-slate design system loaded.",
    "Sensors active: X API, Instagram Scraping, TikTok Trends.",
    "MCP connections resolved: Meta Ads, Puppeteer, Slack, GitHub.",
    "War Room awaiting campaign briefing input..."
  ]);

  // Accent Color Theme Hue state
  const [accentHue, setAccentHue] = useState<number>(200);

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
      role: "Runway & Cap Cut",
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

  // Effect to update CSS variable when accentHue shifts
  useEffect(() => {
    document.documentElement.style.setProperty("--primary-hue", accentHue.toString());
    const saturation = accentHue === 200 ? "80%" : accentHue === 260 ? "85%" : accentHue === 145 ? "75%" : "85%";
    const lightness = accentHue === 200 ? "60%" : accentHue === 260 ? "65%" : accentHue === 145 ? "50%" : "60%";
    document.documentElement.style.setProperty("--primary-saturation", saturation);
    document.documentElement.style.setProperty("--primary-lightness", lightness);
  }, [accentHue]);

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

  // Run simulated flow for the three Use Cases
  const handleRunSimulation = (useCaseId: number, params: any) => {
    if (isRunning) return;
    setIsRunning(true);
    setIsApproved(false);
    setSelectedNodeId("ingestion");
    addSystemLog(`Iniciando simulación del Caso de Uso ${useCaseId}...`);

    // Reset node progress states to idle
    const cleanStates = { ...DEFAULT_NODE_STATES };
    setNodeStates(cleanStates);

    if (useCaseId === 1) {
      runUseCase1(params);
    } else if (useCaseId === 2) {
      runUseCase2(params);
    } else {
      runUseCase3(params);
    }
  };

  const handleManualSync = () => {
    setIsAdsSyncing(true);
    addSystemLog("Invocando Meta Ads MCP Server para jalar métricas de rendimiento y CTR...");
    setTimeout(() => {
      setIsAdsSyncing(false);
      // Boost campaigns metrics slightly to represent optimization
      setMetaCampaigns(prev => prev.map(c => ({
        ...c,
        spent: Math.min(c.budget, c.spent + 120),
        impressions: c.impressions + 5400,
        conversions: c.conversions + 12,
        ctr: parseFloat((c.ctr + 0.12).toFixed(2)),
        cac: parseFloat((c.cac - 0.25).toFixed(2))
      })));
      addSystemLog("Sincronización de Meta Ads finalizada. CTR optimizado y CAC reducido.");
    }, 1800);
  };

  /* ==========================================
     SIMULATION RUNNERS FOR THE 3 USE CASES
     ========================================== */

  // Use Case 1: Video Input & Optimization
  const runUseCase1 = (params: any) => {
    const videoName = params.videoName;
    const platform = params.platform;
    const timeScale = 1200;

    // Step 1: Ingestion
    setTimeout(() => {
      setActiveStep("ingestion");
      setSelectedNodeId("ingestion");
      addSystemLog(`Ingestando archivo de video: ${videoName}`);
      updateNodeProgressState("ingestion", { status: "running", progress: 40, itemsCount: 1 });
      updateNodeDataMap("ingestion", {
        status: "running",
        progress: 40,
        files: [{ name: videoName, type: "video/mp4", size: "24.5 MB" }],
        logs: [{
          sender: "Sensor Ingestion",
          message: `Ingestando video en crudo '${videoName}'. Extrayendo pistas de audio.`,
          timestamp: new Date().toLocaleTimeString()
        }]
      });
    }, 100);

    setTimeout(() => {
      updateNodeProgressState("ingestion", { status: "success", progress: 100, itemsCount: 1 });
      updateNodeDataMap("ingestion", { status: "success", progress: 100 });
      addSystemLog("Video cargado en base de datos. Transfiriendo a Research para transcripción.");
    }, 1 * timeScale);

    // Step 2: Research (Audio parsing & transcription)
    setTimeout(() => {
      setActiveStep("research");
      setSelectedNodeId("research");
      addSystemLog("ResearchAgent procesando audio y extrayendo transcripción.");
      updateNodeProgressState("research", { status: "running", progress: 50, itemsCount: 1 });
      updateNodeDataMap("research", {
        status: "running",
        progress: 50,
        logs: [{
          sender: "ResearchAgent",
          message: "Analizando canal de audio. Transcribiendo y buscando anclas teóricas sobre arquitectura de sistemas...",
          timestamp: new Date().toLocaleTimeString()
        }]
      });
    }, 2 * timeScale);

    setTimeout(() => {
      updateNodeProgressState("research", { status: "success", progress: 100, itemsCount: 2 });
      updateNodeDataMap("research", {
        status: "success",
        progress: 100,
        logs: [
          {
            sender: "ResearchAgent",
            message: "Transcripción de audio finalizada. Aplicando capa académica (Scholar Layer).",
            timestamp: new Date().toLocaleTimeString()
          },
          {
            sender: "ResearchAgent (Scholar Layer)",
            message: "He detectado que el video habla sobre 'fallas de red en bases de datos'. He generado el análisis NLP Persuasivo:",
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
    setTimeout(() => {
      setActiveStep("media");
      setSelectedNodeId("media");
      addSystemLog(`MediaAgent aplicando re-framing y auto-captions para ${platform}.`);
      updateNodeProgressState("media", { status: "running", progress: 45, itemsCount: 1 });
      updateNodeDataMap("media", {
        status: "running",
        progress: 45,
        logs: [{
          sender: "MediaAgent",
          message: `Iniciando VideoOptimizerTool. Modificando relación de aspecto a vertical (9:16) y quemando subtítulos automáticos estilizados.`,
          timestamp: new Date().toLocaleTimeString()
        }]
      });
    }, 5 * timeScale);

    setTimeout(() => {
      updateNodeProgressState("media", { status: "success", progress: 100, itemsCount: 2 });
      updateNodeDataMap("media", {
        status: "success",
        progress: 100,
        assets: [{
          name: "clip_vertical_optimizado.mp4",
          type: "video",
          content: "https://media.simulated-cdn.com/assets/clip_vertical_optimizado.mp4"
        }],
        logs: [
          {
            sender: "MediaAgent",
            message: `Autocaptions añadidas. Video recortado en formato vertical. Listo para redes móviles.`,
            timestamp: new Date().toLocaleTimeString()
          }
        ]
      });
      addSystemLog("Video optimizado visualmente. Transfiriendo a Writer.");
    }, 7 * timeScale);

    // Step 4: Writer (Copywriting)
    setTimeout(() => {
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

    setTimeout(() => {
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
    setTimeout(() => {
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

    setTimeout(() => {
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
      setIsApproved(true); // Auto greenlight simulated
    }, 13 * timeScale);

    // Step 6: Publisher
    setTimeout(() => {
      setActiveStep("publisher");
      setSelectedNodeId("publisher");
      addSystemLog(`PublisherAgent publicando video y copy en ${platform}.`);
      updateNodeProgressState("publisher", { status: "running", progress: 50, itemsCount: 1 });
      updateNodeDataMap("publisher", {
        status: "running",
        progress: 50,
        logs: [{
          sender: "PublisherAgent",
          message: `Estableciendo conexión API con ${platform} Ingestion. Subiendo video...`,
          timestamp: new Date().toLocaleTimeString()
        }]
      });
    }, 14 * timeScale);

    setTimeout(() => {
      updateNodeProgressState("publisher", { status: "success", progress: 100, itemsCount: 1 });
      updateNodeDataMap("publisher", {
        status: "success",
        progress: 100,
        logs: [{
          sender: "PublisherAgent",
          message: `✅ Video publicado exitosamente en ${platform} orgánico. URL simulada: https://tiktok.com/@growth_agency/video/739192841`,
          timestamp: new Date().toLocaleTimeString()
        }]
      });
      addSystemLog("Publicación exitosa.");
    }, 16 * timeScale);

    // Step 7: CEO (Review)
    setTimeout(() => {
      setActiveStep("ceo");
      setSelectedNodeId("ceo");
      addSystemLog("CEO Agent finalizando ciclo de campaña. Reportando estado.");
      updateNodeProgressState("ceo", { status: "success", progress: 100, itemsCount: 1 });
      updateNodeDataMap("ceo", {
        status: "success",
        progress: 100,
        logs: [{
          sender: "CEOAgent",
          message: `Campaña de video '${videoName}' completada en ${platform}. Sensores listos para monitorear vistas.`,
          timestamp: new Date().toLocaleTimeString()
        }]
      });
      setIsRunning(false);
      setActiveStep("");
      addSystemLog("Caso de Uso 1 finalizado con éxito.");
    }, 17 * timeScale);
  };

  // Use Case 2: Image-to-Video Motion Generation
  const runUseCase2 = (params: any) => {
    const imageName = params.imageName;
    const duration = params.duration;
    const style = params.style;
    const timeScale = 1200;

    // Step 1: Ingestion
    setTimeout(() => {
      setActiveStep("ingestion");
      setSelectedNodeId("ingestion");
      addSystemLog(`Ingestando imagen base: ${imageName}`);
      updateNodeProgressState("ingestion", { status: "running", progress: 50, itemsCount: 1 });
      updateNodeDataMap("ingestion", {
        status: "running",
        progress: 50,
        files: [{ name: imageName, type: "image/png", size: "3.8 MB" }],
        logs: [{
          sender: "Sensor Ingestion",
          message: `Cargando imagen '${imageName}'. Validando resolución y capas cromáticas.`,
          timestamp: new Date().toLocaleTimeString()
        }]
      });
    }, 100);

    setTimeout(() => {
      updateNodeProgressState("ingestion", { status: "success", progress: 100, itemsCount: 1 });
      updateNodeDataMap("ingestion", { status: "success", progress: 100 });
      addSystemLog("Imagen cargada. Enviando a Media para render de animación Runway.");
    }, 1 * timeScale);

    // Step 2: Media (Image-to-Video API)
    setTimeout(() => {
      setActiveStep("media");
      setSelectedNodeId("media");
      addSystemLog(`Invocando API de Runway con estilo '${style}' para renderizar ${duration}s.`);
      updateNodeProgressState("media", { status: "running", progress: 30, itemsCount: 1 });
      updateNodeDataMap("media", {
        status: "running",
        progress: 30,
        logs: [{
          sender: "MediaAgent",
          message: `Iniciando ImageToVideoTool. Generando vector de interpolación con el prompt de estilo '${style}' por ${duration} segundos.`,
          timestamp: new Date().toLocaleTimeString()
        }]
      });
    }, 2 * timeScale);

    setTimeout(() => {
      updateNodeProgressState("media", { status: "success", progress: 100, itemsCount: 2 });
      updateNodeDataMap("media", {
        status: "success",
        progress: 100,
        assets: [{
          name: `motion_clip_${duration}s.mp4`,
          type: "video",
          content: "https://media.runway-sim.com/outputs/motion_clip_9281.mp4"
        }],
        logs: [{
          sender: "MediaAgent",
          message: `Render finalizado. Video de ${duration} segundos generado con éxito en estilo ${style}.`,
          timestamp: new Date().toLocaleTimeString()
        }]
      });
      addSystemLog("Video renderizado por Runway. Enviando a Strategist para segmentación.");
    }, 5 * timeScale);

    // Step 3: Strategist (Audience mapping)
    setTimeout(() => {
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

    setTimeout(() => {
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
    setTimeout(() => {
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

    setTimeout(() => {
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
    setTimeout(() => {
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

    setTimeout(() => {
      updateNodeProgressState("risk", { status: "success", progress: 100, itemsCount: 0 });
      updateNodeDataMap("risk", {
        status: "success",
        progress: 100,
        logs: [{
          sender: "RiskAgent",
          message: "✅ Aprobado. El video renderizado no incumple ninguna directriz visual de Ads.",
          timestamp: new Date().toLocaleTimeString()
        }]
      });
      addSystemLog("Cumplimiento verificado. Listo para publicar.");
      setIsApproved(true);
    }, 14 * timeScale);

    // Step 6: Publisher
    setTimeout(() => {
      setActiveStep("publisher");
      setSelectedNodeId("publisher");
      addSystemLog("PublisherAgent publicando asset de video en canales...");
      updateNodeProgressState("publisher", { status: "running", progress: 40, itemsCount: 1 });
      updateNodeDataMap("publisher", {
        status: "running",
        progress: 40,
        logs: [{
          sender: "PublisherAgent",
          message: "Subiendo clip vertical a X API. Programando publicación para hora pico.",
          timestamp: new Date().toLocaleTimeString()
        }]
      });
    }, 15 * timeScale);

    setTimeout(() => {
      updateNodeProgressState("publisher", { status: "success", progress: 100, itemsCount: 1 });
      updateNodeDataMap("publisher", {
        status: "success",
        progress: 100,
        logs: [{
          sender: "PublisherAgent",
          message: "✅ Publicado en X. Programado en LinkedIn para mañana a las 8:00 AM.",
          timestamp: new Date().toLocaleTimeString()
        }]
      });
      addSystemLog("Flujo de publicación completado.");
    }, 17 * timeScale);

    // Step 7: CEO
    setTimeout(() => {
      setActiveStep("ceo");
      setSelectedNodeId("ceo");
      addSystemLog("CEO Agent cerrando simulación.");
      updateNodeProgressState("ceo", { status: "success", progress: 100, itemsCount: 1 });
      updateNodeDataMap("ceo", {
        status: "success",
        progress: 100,
        logs: [{
          sender: "CEOAgent",
          message: "Caso 2 exitoso. El asset de video ya está en circulación.",
          timestamp: new Date().toLocaleTimeString()
        }]
      });
      setIsRunning(false);
      setActiveStep("");
      addSystemLog("Caso de Uso 2 finalizado con éxito.");
    }, 18 * timeScale);
  };

  // Use Case 3: Text Prompt to Full Campaign & Paid Ad Pack (Kleppmann campaign)
  const runUseCase3 = (params: any) => {
    const promptText = params.prompt;
    const audience = params.audience;
    const budget = params.budget;
    const timeScale = 1200;

    // Step 1: Ingestion
    setTimeout(() => {
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

    setTimeout(() => {
      updateNodeProgressState("ingestion", { status: "success", progress: 100, itemsCount: 1 });
      updateNodeDataMap("ingestion", { status: "success", progress: 100 });
      addSystemLog("Prompt ingestado. Transfiriendo a CEO para definir presupuesto y canales.");
    }, 1 * timeScale);

    // Step 2: CEO (Brief definition)
    setTimeout(() => {
      setActiveStep("ceo");
      setSelectedNodeId("ceo");
      addSystemLog("CEO Agent estructurando metas de la campaña y presupuesto.");
      updateNodeProgressState("ceo", { status: "running", progress: 40, itemsCount: 1 });
      updateNodeDataMap("ceo", {
        status: "running",
        progress: 40,
        logs: [{
          sender: "CEOAgent",
          message: `Estructurando campaña: 'Kleppmann No Silver Bullets'. Presupuesto asignado: $${budget}. Audiencia: ${audience}. Canales: X y Meta Ads (Paid).`,
          timestamp: new Date().toLocaleTimeString()
        }]
      });
    }, 2 * timeScale);

    setTimeout(() => {
      updateNodeProgressState("ceo", { status: "success", progress: 100, itemsCount: 1 });
      updateNodeDataMap("ceo", { status: "success", progress: 100 });
      addSystemLog("Objetivos de campaña validados. Enviando a Research para extraer base teórica del libro.");
    }, 3 * timeScale);

    // Step 3: Research (Scholar Layer - DDIA concepts)
    setTimeout(() => {
      setActiveStep("research");
      setSelectedNodeId("research");
      addSystemLog("ResearchAgent indexando libro 'Designing Data-Intensive Applications' de Kleppmann.");
      updateNodeProgressState("research", { status: "running", progress: 60, itemsCount: 3 });
      updateNodeDataMap("research", {
        status: "running",
        progress: 60,
        logs: [{
          sender: "ResearchAgent",
          message: "Buscando referencias sobre 'soluciones universales' y 'dilemas de replicación' en Kleppmann. Extrayendo citas clave...",
          timestamp: new Date().toLocaleTimeString()
        }]
      });
    }, 4 * timeScale);

    setTimeout(() => {
      updateNodeProgressState("research", { status: "success", progress: 100, itemsCount: 3 });
      updateNodeDataMap("research", {
        status: "success",
        progress: 100,
        logs: [
          {
            sender: "ResearchAgent",
            message: "Cita extraída: 'There are no simple answers; every design is a trade-off.' (Capítulo 1). Capa Scholar NLP activada:",
            timestamp: new Date().toLocaleTimeString()
          },
          {
            sender: "ResearchAgent (Scholar Layer)",
            message: "Análisis conceptual estructurado bajo el patrón NLP de 3 balas:",
            timestamp: new Date().toLocaleTimeString(),
            isScholar: true,
            nlpExplanation: {
              reencuadre: "Los ingenieros buscan la 'base de datos perfecta' (ej. MongoDB vs PostgreSQL). Reencuadramos esto demostrando que elegir una base de datos sin analizar los trade-offs es apostar al fracaso técnico de la startup.",
              tradeoff: "El dilema persistente: Consistencia fuerte vs Escalabilidad de escritura. No puedes tener ambas en un entorno distribuido sin pagar con latencia o riesgo de partición. Kleppmann lo deja claro.",
              resolucion: "Deja de discutir en Twitter sobre qué base de datos es mejor. Diseña una matriz de decisión técnica basada en los requerimientos específicos de carga de tu negocio (Lectura/Escritura)."
            }
          }
        ]
      });
      addSystemLog("Teoría académica de Kleppmann lista. Enviando a Strategist para mezclar con tendencias sociales.");
    }, 6 * timeScale);

    // Step 4: Strategist (Trend-Mixing Loop)
    setTimeout(() => {
      setActiveStep("strategist");
      setSelectedNodeId("strategist");
      addSystemLog("StrategistAgent ejecutando MultiPlatformTrendsTool...");
      updateNodeProgressState("strategist", { status: "running", progress: 50, itemsCount: 2 });
      updateNodeDataMap("strategist", {
        status: "running",
        progress: 50,
        logs: [{
          sender: "StrategistAgent",
          message: "Buscando tendencias en X y LinkedIn. Tendencia detectada: debates sobre costes de migración a la nube y abandono de Kubernetes. Mezclando tendencia con Kleppmann...",
          timestamp: new Date().toLocaleTimeString()
        }]
      });
    }, 7 * timeScale);

    setTimeout(() => {
      updateNodeProgressState("strategist", { status: "success", progress: 100, itemsCount: 2 });
      updateNodeDataMap("strategist", {
        status: "success",
        progress: 100,
        logs: [{
          sender: "StrategistAgent",
          message: "Estrategia de mezcla formulada. Campaña enfocada en 'La ilusión del Serverless y las bases de datos auto-escalables'. Enviando brief a Writer.",
          timestamp: new Date().toLocaleTimeString()
        }]
      });
      addSystemLog("Estrategia de tendencia lista. Enviando a Writer.");
    }, 9 * timeScale);

    // Step 5: Writer (Redacción Copy & Ad Creatives)
    setTimeout(() => {
      setActiveStep("writer");
      setSelectedNodeId("writer");
      addSystemLog("WriterAgent estructurando el pack de contenidos persuasivos.");
      updateNodeProgressState("writer", { status: "running", progress: 45, itemsCount: 1 });
      updateNodeDataMap("writer", {
        status: "running",
        progress: 45,
        logs: [{
          sender: "WriterAgent",
          message: "Redactando hilo para X y copy para Meta Ads integrando el patrón de persuasión NLP...",
          timestamp: new Date().toLocaleTimeString()
        }]
      });
    }, 10 * timeScale);

    setTimeout(() => {
      const xThread = `🧵 1/5 ¿Por qué tu startup morirá por culpa de una base de datos 'universal'?\n\nTodos buscan la arquitectura mágica. Pero en sistemas complejos, no hay balas de plata. Cada decisión es un compromiso de ingeniería.\n\n2/5 Martin Kleppmann en su libro 'Designing Data-Intensive Applications' explica el trade-off clásico: si buscas consistencia instantánea en toda tu red, estás sacrificando disponibilidad y velocidad de respuesta.\n\n3/5 Intentar meter tu lógica relacional en una base de datos NoSQL sin modelar trade-offs causa fallos catastróficos al escalar.\n\n4/5 Reencuadra tu visión: la base de datos perfecta no existe. Deja de seguir modas de influencers de código. Define tu throughput real primero.\n\n5/5 ¿Quieres diseñar sistemas robustos basados en teoría dura y no en marketing? Síguenos.`;
      const metaCopy = `🚨 DEJA de buscar la base de datos perfecta.\n\nEn ingeniería, no hay balas de plata. Cada base de datos tiene un trade-off oculto. Si escalas sin entenderlo, tu sistema colapsará.\n\n👉 Aprende los principios de sistemas distribuidos y reduce tus costes en la nube.\n\n[Registrarme al Webinar de Arquitectura Tech]`;

      updateNodeProgressState("writer", { status: "success", progress: 100, itemsCount: 2 });
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
          }
        ],
        logs: [{
          sender: "WriterAgent",
          message: "Pack de textos de campaña creados exitosamente.",
          timestamp: new Date().toLocaleTimeString()
        }]
      });
      addSystemLog("Copia generada con éxito. Enviando a Media para los diseños del ad pack.");
    }, 12 * timeScale);

    // Step 6: Media (Visual assets)
    setTimeout(() => {
      setActiveStep("media");
      setSelectedNodeId("media");
      addSystemLog("MediaAgent renderizando imagen conceptual del anuncio.");
      updateNodeProgressState("media", { status: "running", progress: 50, itemsCount: 1 });
      updateNodeDataMap("media", {
        status: "running",
        progress: 50,
        logs: [{
          sender: "MediaAgent",
          message: "Diseñando imagen técnica: Diagrama de transacciones y bases de datos con estilo cinematic dark slate.",
          timestamp: new Date().toLocaleTimeString()
        }]
      });
    }, 13 * timeScale);

    setTimeout(() => {
      updateNodeProgressState("media", { status: "success", progress: 100, itemsCount: 1 });
      updateNodeDataMap("media", {
        status: "success",
        progress: 100,
        assets: [{
          name: "diagrama_tradeoffs_anuncio.png",
          type: "image",
          content: "https://media.agency-sim.com/diagram_dark_slate.png"
        }],
        logs: [{
          sender: "MediaAgent",
          message: "Imagen de anuncio generada en alta resolución.",
          timestamp: new Date().toLocaleTimeString()
        }]
      });
      addSystemLog("Creativo de anuncio listo. Enviando todo a Risk para la auditoría de políticas.");
    }, 15 * timeScale);

    // Step 7: Risk (Compliance Check)
    setTimeout(() => {
      setActiveStep("risk");
      setSelectedNodeId("risk");
      addSystemLog("RiskAgent auditando campaña completa y código de ad set.");
      updateNodeProgressState("risk", { status: "running", progress: 65, itemsCount: 0 });
      updateNodeDataMap("risk", {
        status: "running",
        progress: 65,
        logs: [{
          sender: "RiskAgent",
          message: "Validando que el copy no infrinja políticas de Meta Ads (sin promesas engañosas, sin lenguaje agresivo). Verificando enlaces.",
          timestamp: new Date().toLocaleTimeString()
        }]
      });
    }, 16 * timeScale);

    setTimeout(() => {
      updateNodeProgressState("risk", { status: "success", progress: 100, itemsCount: 0 });
      updateNodeDataMap("risk", {
        status: "success",
        progress: 100,
        logs: [{
          sender: "RiskAgent",
          message: "✅ Campaña aprobada al 100%. No hay violaciones de política de Meta Ads. Listo para pauta.",
          timestamp: new Date().toLocaleTimeString()
        }]
      });
      addSystemLog("Aprobación regulatoria y de marca otorgada. Activando switch de pauta.");
      setIsApproved(true);
    }, 18 * timeScale);

    // Step 8: Publisher (Meta Ads MCP integration)
    setTimeout(() => {
      setActiveStep("publisher");
      setSelectedNodeId("publisher");
      addSystemLog("PublisherAgent llamando al Meta Ads MCP Server para provisionar campaña...");
      updateNodeProgressState("publisher", { status: "running", progress: 30, itemsCount: 1 });
      updateNodeDataMap("publisher", {
        status: "running",
        progress: 30,
        logs: [{
          sender: "PublisherAgent",
          message: `Llamando a las herramientas del Meta Ads MCP. Creando campaña 'Kleppmann No Silver Bullets'. Presupuesto: $${budget}. Configurando audiencias interesadas en Rust, Next.js y DDIA.`,
          timestamp: new Date().toLocaleTimeString()
        }]
      });
    }, 19 * timeScale);

    setTimeout(() => {
      // Create new dynamic campaign in MetaAds panel
      const newCamp: MetaAdsCampaign = {
        id: `camp-${Date.now()}`,
        name: "Meta Ads: Kleppmann Trade-offs (Automated)",
        budget: budget,
        spent: 0,
        ctr: 0.00,
        cac: 0.00,
        impressions: 0,
        conversions: 0,
        status: "active",
        targeting: {
          demographics: "Software Engineers (24-45)",
          interests: ["Rust", "Next.js", "System Design", "Kubernetes"],
          locations: ["Latam", "US"]
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
            message: "✅ Publicado en X orgánico con éxito.",
            timestamp: new Date().toLocaleTimeString()
          },
          {
            sender: "PublisherAgent (Meta Ads MCP)",
            message: `✅ Campaña registrada en Meta Ads Manager. Estado: Activa. Puja configurada para maximizar leads.`,
            timestamp: new Date().toLocaleTimeString()
          }
        ]
      });
      addSystemLog("Campaña pagada y orgánica sincronizada correctamente.");
    }, 21 * timeScale);

    // Step 9: CEO (Confirmation & Feedback loop)
    setTimeout(() => {
      setActiveStep("ceo");
      setSelectedNodeId("ceo");
      addSystemLog("CEO Agent finalizando flujo. Iniciando sensor de recolección de CTR.");
      updateNodeProgressState("ceo", { status: "success", progress: 100, itemsCount: 2 });
      updateNodeDataMap("ceo", {
        status: "success",
        progress: 100,
        logs: [{
          sender: "CEOAgent",
          message: `Campaña 'Kleppmann' iniciada. Presupuesto de $${budget} en distribución. Sensores sincronizados con el Meta Ads MCP.`,
          timestamp: new Date().toLocaleTimeString()
        }]
      });

      // Simulate first metrics update on the campaign
      setTimeout(() => {
        setMetaCampaigns(prev => prev.map(c => {
          if (c.name.includes("Automated")) {
            return {
              ...c,
              spent: 120,
              impressions: 4500,
              conversions: 18,
              ctr: 2.34,
              cac: 6.67
            };
          }
          return c;
        }));
        addSystemLog("Primer pulso de métricas recibido de Meta Ads MCP: CTR 2.34%, CAC $6.67.");
      }, 1500);

      setIsRunning(false);
      setActiveStep("");
      addSystemLog("Caso de Uso 3 finalizado con éxito.");
    }, 22 * timeScale);
  };

  return (
    <div className="relative min-h-screen w-full bg-[#070708] text-[#f4f4f5] overflow-hidden flex flex-col font-sans">
      {/* 2D Canvas Mesh Background */}
      <CanvasBackground />

      {/* Dotted Pixel Grid Overlay */}
      <div className="absolute inset-0 pixel-grid pointer-events-none opacity-20 z-0" />

      {/* Header Bar */}
      <header className="relative z-10 w-full px-6 py-4 border-b border-white/5 bg-zinc-950/40 backdrop-blur-md flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center text-sky-400">
            <Cpu size={20} className="animate-pulse" />
          </div>
          <div>
            <h1 className="text-base font-bold tracking-tight text-white flex items-center gap-2">
              War Room Campaign Board
              <span className="text-[10px] bg-sky-500/10 text-sky-400 border border-sky-500/20 px-2 py-0.5 rounded-full font-mono font-medium">
                Autonomous multi-agent SaaS
              </span>
            </h1>
            <p className="text-[10px] text-zinc-500">
              Orquestador digital de contenido y pauta optimizada por IA
            </p>
          </div>
        </div>

        {/* System status display */}
        <div className="flex items-center gap-4 text-xs">
          <div className="hidden md:flex items-center gap-1.5 text-zinc-400">
            <Layers size={12} className="text-zinc-500" />
            <span>Schema: PostgreSQL Campaign db</span>
          </div>
          <div className="h-4 w-px bg-white/10 hidden md:block" />
          <div className="flex items-center gap-1.5 text-emerald-400 font-medium">
            <Wifi size={12} className="animate-pulse" />
            <span>Conectores MCP activos</span>
          </div>
        </div>
      </header>

      {/* Main Core Layout Grid */}
      <main className="relative z-10 flex-1 grid grid-cols-1 lg:grid-cols-12 gap-6 p-6 overflow-hidden">
        {/* Left Column (Width 4/12) - Configuration & Ads */}
        <section className="lg:col-span-4 flex flex-col gap-6 overflow-y-auto max-h-[calc(100vh-130px)] pr-2">
          {/* Controls Card */}
          <GlowCard className="bg-zinc-950/60 border border-white/5 flex flex-col gap-4">
            <div className="flex items-center gap-2 border-b border-white/5 pb-2.5">
              <div className="p-1 rounded bg-white/5 text-sky-400">
                <Sliders size={14} />
              </div>
              <h3 className="text-xs font-semibold text-zinc-200 uppercase tracking-wider">Lanzador de Campañas</h3>
            </div>
            <ControlPanel 
              onRunSimulation={handleRunSimulation} 
              isRunning={isRunning} 
              onAccentChange={setAccentHue}
            />
          </GlowCard>

          {/* Meta Ads Panel */}
          <GlowCard className="bg-zinc-950/60 border border-white/5 flex flex-col gap-4">
            <MetaAdsDashboard 
              campaigns={metaCampaigns} 
              isSyncing={isAdsSyncing} 
              onSync={handleManualSync}
            />
          </GlowCard>
        </section>

        {/* Middle Column (Width 5/12) - In-process Graph & Live Logs */}
        <section className="lg:col-span-5 flex flex-col gap-6 overflow-y-auto max-h-[calc(100vh-130px)]">
          {/* Node Graph Container */}
          <div className="flex flex-col gap-2">
            <div className="flex justify-between items-center px-1">
              <span className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">Flujo de Datos (Microsoft Fabric Layout)</span>
              {activeStep && (
                <span className="text-[9px] text-sky-400 flex items-center gap-1.5 animate-pulse">
                  <span className="w-1.5 h-1.5 rounded-full bg-sky-500" />
                  Transfiriendo datos...
                </span>
              )}
            </div>
            <PipelineGraph 
              activeStep={activeStep}
              nodeStates={nodeStates}
              selectedNodeId={selectedNodeId}
              onNodeSelect={setSelectedNodeId}
            />
          </div>

          {/* Core System Log Terminal Console */}
          <GlowCard className="p-4 bg-zinc-950/70 border border-white/5 flex flex-col gap-2.5 flex-1 min-h-[220px]">
            <div className="flex justify-between items-center border-b border-white/5 pb-2">
              <div className="flex items-center gap-1.5 text-zinc-300">
                <Terminal size={13} className="text-sky-400" />
                <span className="text-[10px] font-semibold uppercase tracking-wider">Consola del War Room</span>
              </div>
              <span className="text-[8px] font-mono text-zinc-600">v1.2.0-stable</span>
            </div>
            
            <div className="flex-1 font-mono text-[10px] text-zinc-400 flex flex-col gap-1.5 overflow-y-auto max-h-[280px] leading-relaxed">
              {systemLogs.map((log, index) => (
                <div key={index} className="flex gap-1.5 items-start">
                  <span className="text-sky-500/80 flex-shrink-0">&gt;</span>
                  <span className="break-all">{log}</span>
                </div>
              ))}
            </div>
          </GlowCard>
        </section>

        {/* Right Column (Width 3/12) - Sidebar Details */}
        <section className="lg:col-span-3 flex flex-col overflow-y-auto max-h-[calc(100vh-130px)]">
          <InteractiveSidebar 
            nodeData={selectedNodeId ? nodeDataMap[selectedNodeId] : null}
            onClose={() => setSelectedNodeId(null)}
            isApproved={isApproved}
            onApproveToggle={() => {
              setIsApproved(!isApproved);
              addSystemLog(isApproved ? "Campaña pausada por operador." : "Aprobación manual (Greenlight) concedida por operador.");
            }}
          />
        </section>
      </main>
      
      {/* Footer System Status Bar */}
      <footer className="relative z-10 py-2.5 px-6 border-t border-white/5 bg-zinc-950/60 backdrop-blur-md flex items-center justify-between text-[10px] text-zinc-500">
        <div className="flex items-center gap-1.5">
          <ShieldCheck size={12} className="text-sky-400/80" />
          <span>Cumplimiento del Acuerdo de Licencia de Marca SaaS y Auditoría de Riesgos</span>
        </div>
        <div className="font-mono">
          © 2026 AI-Native Content Agency
        </div>
      </footer>
    </div>
  );
}
