import React from "react";
import { 
  X, 
  CheckCircle2, 
  AlertCircle, 
  Lock, 
  Unlock, 
  Play, 
  FileText, 
  MessageSquare,
  Sparkles
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
  onApproveToggle: () => void;
}

export const InteractiveSidebar: React.FC<InteractiveSidebarProps> = ({
  nodeData,
  onClose,
  isApproved,
  onApproveToggle
}) => {
  if (!nodeData) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-center p-6 glass-panel border border-white/5 rounded-2xl bg-zinc-950/40 min-h-[520px]">
        <MessageSquare size={36} className="text-zinc-600 mb-3" />
        <h3 className="text-sm font-semibold text-zinc-400">Ningún nodo seleccionado</h3>
        <p className="text-xs text-zinc-600 max-w-[200px] mt-1">
          Haz clic en cualquier nodo del pipeline de Microsoft Fabric para ver logs en tiempo real y outputs generados.
        </p>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col glass-panel border border-white/5 rounded-2xl bg-zinc-950/40 overflow-hidden min-h-[520px]">
      {/* Sidebar Header */}
      <div className="flex justify-between items-center px-4 py-3 bg-white/[0.02] border-b border-white/5">
        <div>
          <h3 className="text-sm font-semibold text-zinc-100">{nodeData.name}</h3>
          <p className="text-[10px] text-zinc-500">{nodeData.role}</p>
        </div>
        <button 
          onClick={onClose} 
          className="text-zinc-500 hover:text-zinc-300 p-1 rounded-md hover:bg-white/5 transition-colors"
        >
          <X size={16} />
        </button>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-4">
        {/* Node Stats / Status Bar */}
        <div className="flex items-center justify-between p-3 rounded-lg bg-white/[0.01] border border-white/5">
          <div className="flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${
              nodeData.status === "running" ? "bg-sky-500 animate-pulse" :
              nodeData.status === "success" ? "bg-emerald-500" : "bg-zinc-700"
            }`} />
            <span className="text-[11px] text-zinc-400 font-medium">
              {nodeData.status === "running" ? "Ejecutando..." : nodeData.status === "success" ? "Completado" : "Espera"}
            </span>
          </div>
          <span className="text-xs font-semibold text-zinc-300">{nodeData.progress}%</span>
        </div>

        {/* Ingested Input Files (Sensors) */}
        {nodeData.files.length > 0 && (
          <div className="flex flex-col gap-2">
            <h4 className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">Archivos de Entrada / Sensores</h4>
            <div className="flex flex-col gap-1.5">
              {nodeData.files.map((file, idx) => (
                <div key={idx} className="flex items-center justify-between p-2 rounded-lg bg-zinc-950/60 border border-white/5 text-[11px]">
                  <div className="flex items-center gap-2 min-w-0">
                    <FileText size={12} className="text-sky-400 flex-shrink-0" />
                    <span className="text-zinc-300 truncate">{file.name}</span>
                  </div>
                  <span className="text-zinc-600 text-[10px]">{file.size}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Live Conversation logs */}
        <div className="flex flex-col gap-2 flex-1">
          <h4 className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">Transmisión / Diálogo de Agentes</h4>
          <div className="flex flex-col gap-3 min-h-[120px]">
            {nodeData.logs.length === 0 ? (
              <div className="text-[10px] text-zinc-600 italic p-3 text-center">Sin logs de actividad en este momento.</div>
            ) : (
              nodeData.logs.map((log, idx) => (
                <div key={idx} className="flex flex-col gap-1 p-3 rounded-lg bg-zinc-950/60 border border-white/5">
                  <div className="flex justify-between items-center text-[9px]">
                    <span className="font-semibold text-sky-400">{log.sender}</span>
                    <span className="text-zinc-600">{log.timestamp}</span>
                  </div>
                  <p className="text-[11px] text-zinc-300 leading-relaxed whitespace-pre-wrap">{log.message}</p>

                  {/* Highlight Scholar Addon / 3-Bullet NLP explanation */}
                  {log.isScholar && log.nlpExplanation && (
                    <div className="mt-3 pt-3 border-t border-white/5 flex flex-col gap-2 bg-sky-950/10 p-2 rounded-md">
                      <div className="flex items-center gap-1.5 text-[9px] font-semibold text-sky-400 uppercase tracking-wide">
                        <Sparkles size={10} />
                        Scholar NLP Persuasion Pattern
                      </div>
                      <div className="flex flex-col gap-1.5 text-[10px]">
                        <div className="text-zinc-400 leading-normal">
                          <span className="text-sky-300 font-medium">1. Reencuadre Cognitivo:</span> {log.nlpExplanation.reencuadre}
                        </div>
                        <div className="text-zinc-400 leading-normal">
                          <span className="text-indigo-300 font-medium">2. Tensión / Trade-off (Kleppmann):</span> {log.nlpExplanation.tradeoff}
                        </div>
                        <div className="text-zinc-400 leading-normal">
                          <span className="text-emerald-300 font-medium">3. Resolución Operativa:</span> {log.nlpExplanation.resolucion}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>

        {/* Generated Deliverables/Assets */}
        {nodeData.assets.length > 0 && (
          <div className="flex flex-col gap-2">
            <h4 className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">Entregables / Assets Generados</h4>
            <div className="flex flex-col gap-2.5">
              {nodeData.assets.map((asset, idx) => (
                <div key={idx} className="flex flex-col gap-2 p-3 rounded-lg bg-zinc-950/60 border border-white/5">
                  <div className="flex items-center justify-between text-[11px] font-medium text-zinc-300 border-b border-white/5 pb-1.5">
                    <span>{asset.name}</span>
                    <span className="text-[9px] bg-white/5 px-1.5 py-0.5 rounded text-zinc-500 uppercase">{asset.type}</span>
                  </div>

                  {asset.type === "video" && (
                    <div className="relative rounded-lg overflow-hidden border border-white/5 bg-zinc-900 aspect-video flex flex-col items-center justify-center text-center p-4">
                      <div className="w-10 h-10 rounded-full bg-white/5 flex items-center justify-center text-sky-400 mb-2 cursor-pointer hover:bg-sky-500/10 transition-colors">
                        <Play size={16} fill="currentColor" />
                      </div>
                      <span className="text-[10px] text-zinc-400">Previsualización de Video Optimizada</span>
                      <span className="text-[8px] text-zinc-600 truncate max-w-full mt-0.5">{asset.content}</span>
                    </div>
                  )}

                  {asset.type === "text" && (
                    <pre className="text-[9px] font-mono text-zinc-400 whitespace-pre-wrap bg-zinc-900/40 p-2.5 rounded border border-white/5 max-h-[140px] overflow-y-auto leading-normal">
                      {asset.content}
                    </pre>
                  )}

                  {asset.type === "ad_campaign" && (
                    <div className="text-[10px] text-zinc-400 bg-zinc-900/40 p-2.5 rounded border border-white/5 flex flex-col gap-1">
                      <div className="font-semibold text-sky-400 font-mono">{asset.name}</div>
                      <div className="whitespace-pre-wrap font-mono leading-normal">{asset.content}</div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Manual Approval / Greenlight Switch */}
      <div className="p-4 border-t border-white/5 bg-white/[0.01] flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className={`p-1.5 rounded-lg ${isApproved ? 'bg-emerald-500/10 text-emerald-400' : 'bg-amber-500/10 text-amber-400'}`}>
            {isApproved ? <Unlock size={14} /> : <Lock size={14} />}
          </div>
          <div>
            <h5 className="text-xs font-semibold text-zinc-300">Aprobación Manual</h5>
            <p className="text-[9px] text-zinc-500">Greenlight de Campaña</p>
          </div>
        </div>

        <button
          onClick={onApproveToggle}
          className={`cyber-btn flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
            isApproved 
              ? 'bg-emerald-500 text-zinc-950 border-transparent hover:bg-emerald-400 font-semibold' 
              : 'bg-zinc-900 text-zinc-300 border-white/10 hover:border-white/20'
          }`}
        >
          {isApproved ? (
            <>
              <CheckCircle2 size={12} />
              Aprobado
            </>
          ) : (
            <>
              <AlertCircle size={12} />
              Pendiente
            </>
          )}
        </button>
      </div>
    </div>
  );
};
