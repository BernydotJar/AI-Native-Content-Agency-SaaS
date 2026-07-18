import { useEffect, useState } from "react";
import {
  Activity,
  AlertCircle,
  CheckCircle2,
  FileText,
  Image as ImageIcon,
  Lock,
  MessageSquare,
  PackageOpen,
  Play,
  Sparkles,
  Unlock,
  X,
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
  previewUrl?: string;
}

interface SidebarNodeData {
  id: string;
  name: string;
  role: string;
  status: "idle" | "running" | "success" | "error";
  progress: number;
  logs: LogMessage[];
  files: IngestedFile[];
  assets: GeneratedAsset[];
}

interface InteractiveSidebarProps {
  nodeData: SidebarNodeData | null;
  onClose: () => void;
  isApproved: boolean;
  canApprove?: boolean;
  onApproveToggle: () => void;
}

type InspectorTab = "activity" | "outputs";

const statusCopy: Record<SidebarNodeData["status"], string> = {
  idle: "Standby",
  running: "Executing",
  success: "Complete",
  error: "Attention",
};

export const InteractiveSidebar = ({
  nodeData,
  onClose,
  isApproved,
  canApprove = true,
  onApproveToggle,
}: InteractiveSidebarProps) => {
  const [tab, setTab] = useState<InspectorTab>("activity");

  useEffect(() => {
    setTab("activity");
  }, [nodeData?.id]);

  if (!nodeData) {
    return (
      <aside id="agent-detail" className="inspector-panel grid min-h-80 place-items-center p-8 text-center">
        <div>
          <span className="mx-auto grid h-12 w-12 place-items-center rounded-2xl border border-white/[0.08] bg-white/[0.03] text-zinc-500">
            <MessageSquare size={20} aria-hidden="true" />
          </span>
          <h2 className="mt-4 text-base font-bold text-zinc-300">No agent selected</h2>
          <p className="mx-auto mt-2 max-w-64 text-sm leading-6 text-zinc-500">
            Select a node in the orchestration map to inspect its live dialogue, inputs and deliverables.
          </p>
        </div>
      </aside>
    );
  }

  return (
    <aside id="agent-detail" aria-labelledby="agent-detail-title" className="inspector-panel flex min-h-[540px] flex-col overflow-hidden">
      <header className="border-b border-white/[0.07] px-4 pb-3 pt-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="font-mono text-[10px] font-semibold uppercase tracking-[0.16em] text-[var(--primary-color)]">
              AGENT / {nodeData.id.toUpperCase()}
            </p>
            <h2 id="agent-detail-title" className="mt-1 truncate text-lg font-bold tracking-tight text-white">{nodeData.name}</h2>
            <p className="mt-1 text-xs text-zinc-500">{nodeData.role}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Cerrar detalle del agente"
            className="grid h-11 w-11 shrink-0 place-items-center rounded-xl text-zinc-500 transition-colors hover:bg-white/[0.05] hover:text-zinc-200"
          >
            <X size={17} aria-hidden="true" />
          </button>
        </div>

        <div className="mt-4 rounded-xl border border-white/[0.07] bg-black/20 p-3" role="status" aria-live="polite">
          <div className="flex items-center justify-between gap-3 text-xs">
            <span className="flex items-center gap-2 font-semibold text-zinc-300">
              <span className={`h-2 w-2 rounded-full ${nodeData.status === "running" ? "animate-pulse bg-sky-400" : nodeData.status === "success" ? "bg-emerald-400" : nodeData.status === "error" ? "bg-rose-400" : "bg-zinc-600"}`} />
              {statusCopy[nodeData.status]}
            </span>
            <span className="font-mono font-semibold text-zinc-300">{nodeData.progress}%</span>
          </div>
          <div className="mt-2 h-1 overflow-hidden rounded-full bg-white/[0.06]">
            <div
              role="progressbar"
              aria-label={`Progreso de ${nodeData.name}`}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={nodeData.progress}
              className="h-full rounded-full bg-[var(--primary-color)] shadow-[0_0_12px_var(--primary-color)] transition-[width] duration-300"
              style={{ width: `${nodeData.progress}%` }}
            />
          </div>
        </div>
      </header>

      <div className="grid grid-cols-2 border-b border-white/[0.07] p-1.5" role="tablist" aria-label="Contenido del inspector">
        <button
          type="button"
          role="tab"
          id="inspector-activity-tab"
          aria-controls="inspector-activity"
          aria-selected={tab === "activity"}
          onClick={() => setTab("activity")}
          className={`inspector-tab ${tab === "activity" ? "is-active" : ""}`}
        >
          <Activity size={13} aria-hidden="true" /> Activity
        </button>
        <button
          type="button"
          role="tab"
          id="inspector-outputs-tab"
          aria-controls="inspector-outputs"
          aria-selected={tab === "outputs"}
          onClick={() => setTab("outputs")}
          className={`inspector-tab ${tab === "outputs" ? "is-active" : ""}`}
        >
          <PackageOpen size={13} aria-hidden="true" /> Outputs <span className="font-mono text-[10px] opacity-60">{nodeData.assets.length}</span>
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {tab === "activity" && (
          <div id="inspector-activity" role="tabpanel" aria-labelledby="inspector-activity-tab" className="space-y-5">
            {nodeData.files.length > 0 && (
              <section aria-labelledby="agent-inputs-title">
                <h3 id="agent-inputs-title" className="inspector-eyebrow">Input signals</h3>
                <div className="mt-2 space-y-2">
                  {nodeData.files.map((file) => (
                    <div key={`${file.name}-${file.size}`} className="flex items-center gap-3 rounded-xl border border-white/[0.07] bg-black/20 p-3">
                      <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-sky-400/[0.08] text-sky-300">
                        <FileText size={14} aria-hidden="true" />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-xs font-semibold text-zinc-200">{file.name}</span>
                        <span className="mt-0.5 block font-mono text-[10px] text-zinc-500">{file.type}</span>
                      </span>
                      <span className="font-mono text-[10px] text-zinc-500">{file.size}</span>
                    </div>
                  ))}
                </div>
              </section>
            )}

            <section aria-labelledby="agent-dialogue-title">
              <div className="flex items-center justify-between gap-3">
                <h3 id="agent-dialogue-title" className="inspector-eyebrow">Agent transmission</h3>
                <span className="font-mono text-[9px] text-zinc-600">LIVE / LOCAL</span>
              </div>
              {nodeData.logs.length === 0 ? (
                <p className="mt-3 rounded-xl border border-dashed border-white/[0.08] p-5 text-center text-xs leading-5 text-zinc-500">
                  No activity recorded for this node yet.
                </p>
              ) : (
                <ol className="agent-timeline mt-3 space-y-3">
                  {nodeData.logs.map((log, index) => (
                    <li key={`${log.sender}-${index}`} className="relative pl-5">
                      <span className="agent-timeline__dot" aria-hidden="true" />
                      <article className="rounded-xl border border-white/[0.07] bg-black/20 p-3.5">
                        <div className="flex items-center justify-between gap-3">
                          <span className="text-[11px] font-bold text-[var(--primary-color)]">{log.sender}</span>
                          <time className="font-mono text-[9px] text-zinc-600">{log.timestamp}</time>
                        </div>
                        <p className="mt-2 whitespace-pre-wrap text-xs leading-5 text-zinc-300">{log.message}</p>

                        {log.isScholar && log.nlpExplanation && (
                          <div className="mt-3 rounded-xl border border-sky-400/15 bg-sky-400/[0.045] p-3">
                            <p className="flex items-center gap-2 font-mono text-[9px] font-semibold uppercase tracking-[0.14em] text-sky-300">
                              <Sparkles size={11} aria-hidden="true" /> Scholar / 3-point NLP
                            </p>
                            <ol className="mt-3 space-y-2 text-[11px] leading-5 text-zinc-300">
                              <li><strong className="text-sky-300">01 Reencuadre:</strong> {log.nlpExplanation.reencuadre}</li>
                              <li><strong className="text-violet-300">02 Trade-off:</strong> {log.nlpExplanation.tradeoff}</li>
                              <li><strong className="text-emerald-300">03 Resolución:</strong> {log.nlpExplanation.resolucion}</li>
                            </ol>
                          </div>
                        )}
                      </article>
                    </li>
                  ))}
                </ol>
              )}
            </section>
          </div>
        )}

        {tab === "outputs" && (
          <div id="inspector-outputs" role="tabpanel" aria-labelledby="inspector-outputs-tab">
            <h3 className="inspector-eyebrow">Generated deliverables</h3>
            {nodeData.assets.length === 0 ? (
              <div className="mt-3 rounded-xl border border-dashed border-white/[0.08] p-7 text-center">
                <PackageOpen className="mx-auto text-zinc-600" size={24} aria-hidden="true" />
                <p className="mt-3 text-xs font-semibold text-zinc-400">No outputs generated</p>
                <p className="mt-1 text-[11px] text-zinc-600">Run a mission to populate this node.</p>
              </div>
            ) : (
              <div className="mt-3 space-y-3">
                {nodeData.assets.map((asset, index) => (
                  <article key={`${asset.name}-${index}`} className="overflow-hidden rounded-xl border border-white/[0.08] bg-black/25">
                    <header className="flex items-center justify-between gap-3 border-b border-white/[0.06] px-3.5 py-3">
                      <h4 className="truncate text-xs font-bold text-zinc-200">{asset.name}</h4>
                      <span className="rounded-full border border-white/[0.08] px-2 py-0.5 font-mono text-[9px] uppercase tracking-wider text-zinc-500">{asset.type}</span>
                    </header>

                    {asset.type === "video" && (
                      <figure className="asset-preview asset-preview--video">
                        <span className="grid h-12 w-12 place-items-center rounded-full border border-white/10 bg-black/40 text-sky-300 shadow-lg">
                          <Play size={18} fill="currentColor" aria-hidden="true" />
                        </span>
                        <figcaption className="mt-3 text-center">
                          <span className="block text-xs font-semibold text-zinc-200">Optimized motion preview</span>
                          <span className="mt-1 block text-[10px] text-zinc-500">Sandbox reference · media not fetched</span>
                        </figcaption>
                      </figure>
                    )}

                    {asset.type === "image" && (
                      <figure className="asset-preview asset-preview--image">
                        <div className="asset-orbit" aria-hidden="true"><span /><span /><span /></div>
                        <ImageIcon size={18} className="relative z-10 text-violet-300" aria-hidden="true" />
                        <figcaption className="relative z-10 mt-3 text-center text-[10px] font-medium uppercase tracking-[0.12em] text-zinc-400">
                          Trade-off system map / generated concept
                        </figcaption>
                      </figure>
                    )}

                    {asset.type === "text" && (
                      <pre className="max-h-64 overflow-y-auto whitespace-pre-wrap p-3.5 font-mono text-[11px] leading-5 text-zinc-300">{asset.content}</pre>
                    )}

                    {asset.type === "ad_campaign" && (
                      <div className="p-3.5 font-mono text-[11px] leading-5 text-zinc-300">
                        <p className="font-semibold text-sky-300">META / CAMPAIGN DRAFT</p>
                        <p className="mt-2 whitespace-pre-wrap">{asset.content}</p>
                      </div>
                    )}
                  </article>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      <footer className="border-t border-white/[0.07] bg-black/15 p-4">
        <div className="flex items-center gap-3">
          <span className={`grid h-10 w-10 shrink-0 place-items-center rounded-xl ${isApproved ? "bg-emerald-400/10 text-emerald-300" : "bg-amber-300/10 text-amber-200"}`}>
            {isApproved ? <Unlock size={16} aria-hidden="true" /> : <Lock size={16} aria-hidden="true" />}
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-xs font-bold text-zinc-200">Operator greenlight</p>
            <p className="mt-0.5 text-[10px] text-zinc-500">{canApprove || isApproved ? "Local sandbox approval gate" : "Locked until Risk completes"}</p>
          </div>
          <button
            type="button"
            onClick={onApproveToggle}
            aria-pressed={isApproved}
            disabled={!canApprove && !isApproved}
            className={`flex min-h-11 items-center gap-2 rounded-xl border px-3 text-xs font-bold transition-colors disabled:cursor-not-allowed disabled:opacity-45 ${isApproved ? "border-emerald-300/20 bg-emerald-400/10 text-emerald-200 hover:bg-emerald-400/15" : "border-amber-300/20 bg-amber-300/[0.08] text-amber-100 hover:bg-amber-300/15"}`}
          >
            {isApproved ? <CheckCircle2 size={14} aria-hidden="true" /> : <AlertCircle size={14} aria-hidden="true" />}
            {isApproved ? "Approved" : canApprove ? "Pending" : "Awaiting QA"}
          </button>
        </div>
      </footer>
    </aside>
  );
};
