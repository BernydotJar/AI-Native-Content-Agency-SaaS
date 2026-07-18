import type { ComponentType } from "react";
import {
  Aperture,
  BookOpen,
  Compass,
  Crown,
  Download,
  Megaphone,
  PenTool,
  Send,
  ShieldCheck,
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
  index: string;
  name: string;
  role: string;
  x: number;
  y: number;
  tone: "green" | "blue" | "violet" | "orange" | "rose";
  icon: ComponentType<{ size?: number; className?: string }>;
}

const NODES: NodeConfig[] = [
  { id: "ingestion", index: "00", name: "Signal Intake", role: "X · FB · TikTok · IG · files", x: 10, y: 50, tone: "green", icon: Download },
  { id: "ceo", index: "01", name: "CEO Director", role: "Brief · budget · gates", x: 31, y: 50, tone: "blue", icon: Crown },
  { id: "research", index: "02", name: "Research", role: "Scholar + Context7", x: 31, y: 18, tone: "blue", icon: BookOpen },
  { id: "strategist", index: "03", name: "Strategist", role: "Trend-mixing loop", x: 53, y: 18, tone: "violet", icon: Compass },
  { id: "growth", index: "04", name: "Growth", role: "Territory · distribution", x: 53, y: 50, tone: "green", icon: Megaphone },
  { id: "writer", index: "05", name: "Writer", role: "Narrative · channel copy", x: 53, y: 82, tone: "violet", icon: PenTool },
  { id: "media", index: "06", name: "Media Studio", role: "Video · image · motion", x: 31, y: 82, tone: "orange", icon: Aperture },
  { id: "risk", index: "07", name: "Risk & QA", role: "Truth · brand · policy", x: 75, y: 28, tone: "rose", icon: ShieldCheck },
  { id: "publisher", index: "08", name: "Publisher", role: "Organic · Meta Ads", x: 89, y: 63, tone: "orange", icon: Send },
];

interface EdgeConfig {
  from: string;
  to: string;
  bend?: number;
}

const EDGES: EdgeConfig[] = [
  { from: "ingestion", to: "ceo" },
  { from: "ceo", to: "research", bend: -8 },
  { from: "research", to: "strategist" },
  { from: "strategist", to: "growth" },
  { from: "growth", to: "writer" },
  { from: "writer", to: "media" },
  { from: "media", to: "risk", bend: 12 },
  { from: "risk", to: "publisher" },
  { from: "publisher", to: "ceo", bend: 31 },
];

const TONE_CLASSES: Record<NodeConfig["tone"], string> = {
  green: "pipeline-node--green",
  blue: "pipeline-node--blue",
  violet: "pipeline-node--violet",
  orange: "pipeline-node--orange",
  rose: "pipeline-node--rose",
};

const STATUS_LABELS: Record<NodeState["status"], string> = {
  idle: "Standby",
  running: "Processing",
  success: "Complete",
  error: "Attention",
};

export const PipelineGraph = ({
  activeStep,
  nodeStates,
  selectedNodeId,
  onNodeSelect,
}: PipelineGraphProps) => {
  const coords = (id: string) => {
    const node = NODES.find((candidate) => candidate.id === id);
    return node ? { x: node.x, y: node.y } : { x: 0, y: 0 };
  };

  return (
    <div className="pipeline-scroll" aria-label="Topología de orquestación multiagente">
      <div className="pipeline-stage">
        <div className="pipeline-grid" aria-hidden="true" />
        <div className="pipeline-horizon" aria-hidden="true" />

        <svg
          className="absolute inset-0 z-10 h-full w-full pointer-events-none"
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          <defs>
            <filter id="edge-glow" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="0.55" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            <marker id="edge-arrow" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
              <path d="M 1 1 L 9 5 L 1 9 z" fill="rgba(161, 161, 170, 0.45)" />
            </marker>
            <marker id="edge-arrow-live" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
              <path d="M 1 1 L 9 5 L 1 9 z" fill="var(--primary-color)" />
            </marker>
          </defs>

          {EDGES.map((edge) => {
            const start = coords(edge.from);
            const end = coords(edge.to);
            const midX = (start.x + end.x) / 2;
            const midY = (start.y + end.y) / 2 + (edge.bend ?? 0);
            const path = `M ${start.x} ${start.y} Q ${midX} ${midY} ${end.x} ${end.y}`;
            const isLive = activeStep === edge.from || activeStep === edge.to;

            return (
              <g key={`${edge.from}-${edge.to}`}>
                <path
                  d={path}
                  pathLength="100"
                  fill="none"
                  stroke={isLive ? "rgba(125, 211, 252, 0.3)" : "rgba(161, 161, 170, 0.18)"}
                  strokeWidth={isLive ? 0.35 : 0.18}
                  vectorEffect="non-scaling-stroke"
                  markerEnd={isLive ? "url(#edge-arrow-live)" : "url(#edge-arrow)"}
                />
                {isLive && (
                  <path
                    d={path}
                    pathLength="100"
                    fill="none"
                    stroke="var(--primary-color)"
                    strokeWidth="0.28"
                    vectorEffect="non-scaling-stroke"
                    className="pulsing-edge"
                    filter="url(#edge-glow)"
                  />
                )}
              </g>
            );
          })}
        </svg>

        <div className="pipeline-nodes">
          {NODES.map((node) => {
            const state = nodeStates[node.id] ?? {
              status: "idle" as const,
              progress: 0,
              itemsCount: 0,
              itemsLabel: "items",
            };
            const isActive = activeStep === node.id;
            const isSelected = selectedNodeId === node.id;
            const Icon = node.icon;

            return (
              <button
                key={node.id}
                type="button"
                onClick={() => onNodeSelect(node.id)}
                aria-pressed={isSelected}
                aria-controls="agent-detail"
                aria-label={`${node.name}. ${node.role}. ${STATUS_LABELS[state.status]}, ${state.progress}%`}
                className={`pipeline-node ${TONE_CLASSES[node.tone]} ${isActive ? "is-active" : ""} ${isSelected ? "is-selected" : ""} ${state.status === "success" ? "is-complete" : ""}`}
                style={{ left: `${node.x}%`, top: `${node.y}%` }}
              >
                <span className="pipeline-node__rail" aria-hidden="true" />
                <span className="pipeline-node__header">
                  <span className="pipeline-node__index">{node.index}</span>
                  <span className="pipeline-node__icon"><Icon size={15} /></span>
                  <span className="min-w-0 flex-1">
                    <span className="pipeline-node__name">{node.name}</span>
                    <span className="pipeline-node__role">{node.role}</span>
                  </span>
                  <span className={`pipeline-node__status status-${state.status}`}>
                    <span className="pipeline-node__status-dot" />
                    {isActive ? "Live" : STATUS_LABELS[state.status]}
                  </span>
                </span>
                <span className="pipeline-node__body">
                  <span className="pipeline-node__progress-track">
                    <span className="pipeline-node__progress" style={{ width: `${state.progress}%` }} />
                  </span>
                  <span className="pipeline-node__meta">
                    <span>{state.itemsCount} {state.itemsLabel}</span>
                    <span>{String(state.progress).padStart(2, "0")}%</span>
                  </span>
                </span>
              </button>
            );
          })}
        </div>

        <div className="pipeline-legend" aria-hidden="true">
          <span><i className="bg-emerald-400" />Signal</span>
          <span><i className="bg-sky-400" />Intelligence</span>
          <span><i className="bg-violet-400" />Transform</span>
          <span><i className="bg-orange-400" />Delivery</span>
          <span className="ml-auto font-mono text-zinc-600">CANONICAL / 08-STATION LOOP</span>
        </div>
      </div>
    </div>
  );
};
