import React from "react";
import { 
  Download, 
  UserCheck, 
  BookOpen, 
  Compass, 
  FileText, 
  Video, 
  ShieldAlert, 
  Share2
} from "lucide-react";


export interface NodeState {
  status: "idle" | "running" | "success" | "error";
  progress: number;
  itemsCount: number;
  itemsLabel: string;
}

interface PipelineGraphProps {
  activeStep: string;
  nodeStates: Record<string, NodeState>;
  selectedNodeId: string | null;
  onNodeSelect: (id: string) => void;
}

interface NodeConfig {
  id: string;
  name: string;
  role: string;
  x: number; // grid x coordinate
  y: number; // grid y coordinate
  colorClass: string;
  icon: React.ComponentType<any>;
}

const NODES: NodeConfig[] = [
  { id: "ingestion", name: "Real-Time Ingestion", role: "Sensor / Ingestion", x: 8, y: 50, colorClass: "node-bar-green", icon: Download },
  { id: "ceo", name: "CEO / Jefe de Campaña", role: "Orchestration & Target", x: 30, y: 50, colorClass: "node-bar-blue", icon: UserCheck },
  { id: "research", name: "Research / Scholar", role: "Theory & NLP Scholar", x: 30, y: 15, colorClass: "node-bar-blue", icon: BookOpen },
  { id: "media", name: "Media / Storytelling", role: "Runway & Cap Cut", x: 30, y: 85, colorClass: "node-bar-orange", icon: Video },
  { id: "strategist", name: "Strategist Agent", role: "Trend-Mixer Strategy", x: 55, y: 32, colorClass: "node-bar-purple", icon: Compass },
  { id: "writer", name: "Writer Agent", role: "Content Copywriter", x: 55, y: 68, colorClass: "node-bar-purple", icon: FileText },
  { id: "risk", name: "Risk Agent", role: "Seguimiento & Compliance", x: 78, y: 32, colorClass: "node-bar-red", icon: ShieldAlert },
  { id: "publisher", name: "Publisher / Meta Ads", role: "Pauta & Meta Ads MCP", x: 78, y: 68, colorClass: "node-bar-orange", icon: Share2 }
];

// Connection definition: source -> target
interface EdgeConfig {
  from: string;
  to: string;
  curvature?: number; // positive = curves down, negative = curves up
}

const EDGES: EdgeConfig[] = [
  { from: "ingestion", to: "ceo" },
  { from: "ingestion", to: "research", curvature: -20 },
  { from: "ingestion", to: "media", curvature: 20 },
  { from: "ceo", to: "research" },
  { from: "research", to: "strategist", curvature: 10 },
  { from: "ceo", to: "strategist", curvature: -10 },
  { from: "strategist", to: "writer" },
  { from: "writer", to: "risk", curvature: -10 },
  { from: "media", to: "writer", curvature: -10 },
  { from: "risk", to: "publisher" },
  { from: "publisher", to: "ceo", curvature: 30 } // Loopback
];

export const PipelineGraph: React.FC<PipelineGraphProps> = ({
  activeStep,
  nodeStates,
  selectedNodeId,
  onNodeSelect
}) => {
  // Find node coordinate by ID
  const getNodeCoords = (id: string) => {
    const node = NODES.find(n => n.id === id);
    return node ? { x: node.x, y: node.y } : { x: 0, y: 0 };
  };

  return (
    <div className="relative w-full h-[520px] glass-panel border border-white/5 rounded-2xl bg-zinc-950/20 overflow-hidden select-none">
      {/* Background cyber grid overlay */}
      <div className="absolute inset-0 pixel-grid pointer-events-none opacity-25" />

      {/* SVG Connecting Edges */}
      <svg className="absolute inset-0 w-full h-full pointer-events-none z-10">
        <defs>
          {/* Arrow marker */}
          <marker
            id="arrow"
            viewBox="0 0 10 10"
            refX="6"
            refY="5"
            markerWidth="6"
            markerHeight="6"
            orient="auto-start-reverse"
          >
            <path d="M 0 1 L 10 5 L 0 9 z" fill="rgba(255, 255, 255, 0.15)" />
          </marker>
          {/* Glowing arrow marker */}
          <marker
            id="arrow-glow"
            viewBox="0 0 10 10"
            refX="6"
            refY="5"
            markerWidth="6"
            markerHeight="6"
            orient="auto-start-reverse"
          >
            <path d="M 0 1 L 10 5 L 0 9 z" fill="var(--primary-color)" />
          </marker>
        </defs>

        {/* Draw all connection lines */}
        {EDGES.map((edge, index) => {
          const fromCoords = getNodeCoords(edge.from);
          const toCoords = getNodeCoords(edge.to);



          // Control point for curve
          const midX = (fromCoords.x + toCoords.x) / 2;
          const midY = (fromCoords.y + toCoords.y) / 2 + (edge.curvature || 0);
          const pathD = `M ${fromCoords.x} ${fromCoords.y} Q ${midX} ${midY} ${toCoords.x} ${toCoords.y}`;

          // Is this path active?
          const isEdgeActive = activeStep === edge.from;

          return (
            <g key={index}>
              {/* Static background path */}
              <path
                d={pathD}
                pathLength="100"
                className="transition-all duration-300"
                style={{
                  fill: "none",
                  stroke: isEdgeActive ? "rgba(96, 165, 250, 0.2)" : "rgba(255, 255, 255, 0.05)",
                  strokeWidth: isEdgeActive ? 2 : 1.5,
                  markerEnd: isEdgeActive ? "url(#arrow-glow)" : "url(#arrow)"
                }}
                transform="scale(1)" // coordinates are percentages directly relative to viewBox
                vectorEffect="non-scaling-stroke"
              />

              {/* Pulsing overlay path for active transmission */}
              {isEdgeActive && (
                <path
                  d={pathD}
                  pathLength="100"
                  fill="none"
                  stroke="var(--primary-color)"
                  strokeWidth={2}
                  className="pulsing-edge"
                  vectorEffect="non-scaling-stroke"
                />
              )}
            </g>
          );
        })}
      </svg>

      {/* Nodes Container */}
      <div className="absolute inset-0 w-full h-full z-20">
        {NODES.map((node) => {
          const state = nodeStates[node.id] || { status: "idle", progress: 0, itemsCount: 0, itemsLabel: "elementos" };
          const isActive = activeStep === node.id;
          const isSelected = selectedNodeId === node.id;
          const Icon = node.icon;

          // Compute styles based on state
          let statusBorder = "border-white/5";
          let statusBg = "bg-zinc-950/70";
          let glowStyle = {};

          if (isActive) {
            statusBorder = "border-sky-500/40";
            statusBg = "bg-zinc-900/80 shadow-[0_0_25px_rgba(56,189,248,0.15)]";
          } else if (state.status === "success") {
            statusBorder = "border-emerald-500/20";
          } else if (isSelected) {
            statusBorder = "border-white/20";
            statusBg = "bg-zinc-900/80";
          }

          return (
            <div
              key={node.id}
              onClick={() => onNodeSelect(node.id)}
              className={`absolute -translate-x-1/2 -translate-y-1/2 flex flex-col w-[170px] rounded-lg border overflow-hidden transition-all duration-300 cursor-pointer ${node.colorClass} ${statusBorder} ${statusBg} hover:scale-[1.03] hover:border-white/20`}
              style={{
                left: `${node.x}%`,
                top: `${node.y}%`,
                ...glowStyle
              }}
            >
              {/* Node Header */}
              <div className="flex items-center gap-2 px-3 py-2 bg-white/[0.02] border-b border-white/5">
                <div className={`p-1 rounded-md ${isActive ? 'bg-sky-500/10 text-sky-400' : 'bg-white/5 text-zinc-400'}`}>
                  <Icon size={14} />
                </div>
                <div className="flex-1 min-w-0">
                  <h4 className="text-[11px] font-semibold text-zinc-100 truncate">{node.name}</h4>
                  <p className="text-[9px] text-zinc-500 truncate">{node.role}</p>
                </div>
              </div>

              {/* Node Body / Status */}
              <div className="p-2.5 flex flex-col gap-1.5">
                <div className="flex justify-between items-center text-[10px]">
                  <span className="text-zinc-500">Estado</span>
                  <span className={`font-semibold capitalize ${
                    isActive ? 'text-sky-400 animate-pulse' : 
                    state.status === 'success' ? 'text-emerald-400' : 
                    state.status === 'error' ? 'text-rose-400' : 'text-zinc-500'
                  }`}>
                    {isActive ? 'Procesando' : state.status === 'success' ? 'Listo' : 'Inactivo'}
                  </span>
                </div>

                {/* Progress bar */}
                <div className="w-full h-1 bg-white/5 rounded-full overflow-hidden">
                  <div 
                    className={`h-full transition-all duration-300 ${
                      isActive ? 'bg-sky-500' : 
                      state.status === 'success' ? 'bg-emerald-500' : 'bg-zinc-700'
                    }`}
                    style={{ width: `${state.progress}%` }}
                  />
                </div>

                {/* Bottom stats info */}
                <div className="flex justify-between items-center text-[9px] text-zinc-400">
                  <span>{state.itemsCount} {state.itemsLabel}</span>
                  <span className="font-medium text-zinc-300">{state.progress}%</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Floating help tags */}
      <div className="absolute bottom-3 left-4 flex gap-3 text-[10px] text-zinc-500 z-30">
        <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-emerald-500" /> Ingestión</span>
        <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-sky-500" /> Estrategia</span>
        <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-purple-500" /> Contenido</span>
        <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-orange-500" /> Pauta</span>
      </div>
    </div>
  );
};
