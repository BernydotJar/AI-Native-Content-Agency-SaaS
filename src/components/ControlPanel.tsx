import React, { useState } from "react";
import { 
  Play, 
  UploadCloud, 
  Palette
} from "lucide-react";
import { GlowCard } from "./GlowCard";


interface ControlPanelProps {
  onRunSimulation: (useCaseId: number, params: any) => void;
  isRunning: boolean;
  onAccentChange: (hue: number) => void;
}

const ACCENT_COLORS = [
  { name: "Cyan Slate", hue: 200, class: "bg-sky-500" },
  { name: "Neon Violet", hue: 260, class: "bg-purple-500" },
  { name: "Emerald Cyber", hue: 145, class: "bg-emerald-500" },
  { name: "Crimson Ember", hue: 350, class: "bg-rose-500" }
];

export const ControlPanel: React.FC<ControlPanelProps> = ({
  onRunSimulation,
  isRunning,
  onAccentChange
}) => {
  const [activeUseCase, setActiveUseCase] = useState<number>(3);
  const [activeAccent, setActiveAccent] = useState<number>(200);

  // Form parameters
  const [useCase1Params, setUseCase1Params] = useState({
    videoName: "entrevista_raw_final.mp4",
    platform: "TikTok"
  });

  const [useCase2Params, setUseCase2Params] = useState({
    imageName: "flyer_evento_arquitectura.png",
    duration: 5,
    style: "Cinemático Cyber"
  });

  const [useCase3Params, setUseCase3Params] = useState({
    prompt: "Quiero una campaña sobre por qué no hay soluciones técnicas universales basándome en Kleppmann.",
    audience: "Desarrolladores Senior y Technical Founders",
    budget: 3500
  });

  const handleAccentSelect = (hue: number) => {
    setActiveAccent(hue);
    onAccentChange(hue);
  };

  const handleRun = () => {
    if (activeUseCase === 1) {
      onRunSimulation(1, useCase1Params);
    } else if (activeUseCase === 2) {
      onRunSimulation(2, useCase2Params);
    } else {
      onRunSimulation(3, useCase3Params);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      {/* Accent Shift Theme Picker */}
      <GlowCard className="p-3 bg-zinc-950/40 border border-white/5 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Palette size={14} className="text-sky-400" />
          <span className="text-[11px] font-semibold text-zinc-300">Skin Accent Shift</span>
        </div>
        <div className="flex gap-2">
          {ACCENT_COLORS.map((color) => (
            <button
              key={color.hue}
              onClick={() => handleAccentSelect(color.hue)}
              title={color.name}
              className={`w-3.5 h-3.5 rounded-full border ${
                activeAccent === color.hue 
                  ? "border-white scale-125" 
                  : "border-white/10 opacity-70 hover:opacity-100"
              } ${color.class} transition-all`}
            />
          ))}
        </div>
      </GlowCard>

      {/* Use Cases Toggle */}
      <div className="grid grid-cols-3 gap-2 bg-zinc-900/40 p-1 rounded-lg border border-white/5">
        <button
          onClick={() => setActiveUseCase(1)}
          disabled={isRunning}
          className={`px-2 py-1.5 rounded text-[10px] font-semibold transition-all ${
            activeUseCase === 1 
              ? "bg-white/10 text-white shadow-sm" 
              : "text-zinc-500 hover:text-zinc-300"
          }`}
        >
          Caso 1: Optimizar Video
        </button>
        <button
          onClick={() => setActiveUseCase(2)}
          disabled={isRunning}
          className={`px-2 py-1.5 rounded text-[10px] font-semibold transition-all ${
            activeUseCase === 2 
              ? "bg-white/10 text-white shadow-sm" 
              : "text-zinc-500 hover:text-zinc-300"
          }`}
        >
          Caso 2: Foto a Video
        </button>
        <button
          onClick={() => setActiveUseCase(3)}
          disabled={isRunning}
          className={`px-2 py-1.5 rounded text-[10px] font-semibold transition-all ${
            activeUseCase === 3 
              ? "bg-white/10 text-white shadow-sm" 
              : "text-zinc-500 hover:text-zinc-300"
          }`}
        >
          Caso 3: Prompt Campaña
        </button>
      </div>

      {/* Main Parameters Panel */}
      <div className="flex-1 flex flex-col justify-between gap-4">
        {/* Use Case 1 Form */}
        {activeUseCase === 1 && (
          <div className="flex flex-col gap-3">
            <div className="flex flex-col gap-1">
              <label className="text-[10px] text-zinc-500 font-semibold uppercase">Archivo de Video Ingestado</label>
              <div className="flex items-center gap-3 p-4 rounded-lg border border-dashed border-white/10 bg-zinc-950/20 hover:bg-zinc-950/40 cursor-pointer transition-colors text-center justify-center flex-col">
                <UploadCloud className="text-zinc-500" size={24} />
                <div className="flex flex-col">
                  <span className="text-xs text-zinc-300 font-medium">{useCase1Params.videoName}</span>
                  <span className="text-[9px] text-zinc-600">Formato: MP4, MOV. Tamaño máx: 100MB</span>
                </div>
              </div>
            </div>

            <div className="flex flex-col gap-1">
              <label className="text-[10px] text-zinc-500 font-semibold uppercase">Plataforma Objetivo</label>
              <select
                value={useCase1Params.platform}
                onChange={(e) => setUseCase1Params({ ...useCase1Params, platform: e.target.value })}
                disabled={isRunning}
                className="w-full bg-zinc-950/60 border border-white/5 rounded-lg px-3 py-2 text-xs text-zinc-300 focus:outline-none focus:border-white/15"
              >
                <option value="TikTok">TikTok (Vertical 9:16)</option>
                <option value="Instagram">Instagram Reels (Vertical 9:16)</option>
                <option value="YouTube">YouTube Shorts (Vertical 9:16)</option>
                <option value="X">X / Twitter (Square 1:1)</option>
              </select>
            </div>
          </div>
        )}

        {/* Use Case 2 Form */}
        {activeUseCase === 2 && (
          <div className="flex flex-col gap-3">
            <div className="flex flex-col gap-1">
              <label className="text-[10px] text-zinc-500 font-semibold uppercase">Diseño / Foto Base</label>
              <div className="flex items-center gap-3 p-4 rounded-lg border border-dashed border-white/10 bg-zinc-950/20 hover:bg-zinc-950/40 cursor-pointer transition-colors text-center justify-center flex-col">
                <UploadCloud className="text-zinc-500" size={24} />
                <div className="flex flex-col">
                  <span className="text-xs text-zinc-300 font-medium">{useCase2Params.imageName}</span>
                  <span className="text-[9px] text-zinc-600">Formatos: PNG, JPG, WebP</span>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div className="flex flex-col gap-1">
                <label className="text-[10px] text-zinc-500 font-semibold uppercase">Duración</label>
                <input
                  type="number"
                  min={3}
                  max={8}
                  value={useCase2Params.duration}
                  onChange={(e) => setUseCase2Params({ ...useCase2Params, duration: parseInt(e.target.value) })}
                  disabled={isRunning}
                  className="w-full bg-zinc-950/60 border border-white/5 rounded-lg px-3 py-2 text-xs text-zinc-300 focus:outline-none focus:border-white/15"
                />
              </div>

              <div className="flex flex-col gap-1">
                <label className="text-[10px] text-zinc-500 font-semibold uppercase">Estilo Runway</label>
                <select
                  value={useCase2Params.style}
                  onChange={(e) => setUseCase2Params({ ...useCase2Params, style: e.target.value })}
                  disabled={isRunning}
                  className="w-full bg-zinc-950/60 border border-white/5 rounded-lg px-3 py-2 text-xs text-zinc-300 focus:outline-none focus:border-white/15"
                >
                  <option value="Cinemático Cyber">Cinemático Cyber</option>
                  <option value="Anime Hyper-detail">Anime Hyper-detail</option>
                  <option value="Sleek Obsidian 3D">Sleek Obsidian 3D</option>
                  <option value="Realista Documental">Realista Documental</option>
                </select>
              </div>
            </div>
          </div>
        )}

        {/* Use Case 3 Form */}
        {activeUseCase === 3 && (
          <div className="flex flex-col gap-3">
            <div className="flex flex-col gap-1">
              <label className="text-[10px] text-zinc-500 font-semibold uppercase">Prompt de Idea (Campañas)</label>
              <textarea
                value={useCase3Params.prompt}
                onChange={(e) => setUseCase3Params({ ...useCase3Params, prompt: e.target.value })}
                disabled={isRunning}
                rows={3}
                placeholder="Escribe la idea conceptual..."
                className="w-full bg-zinc-950/60 border border-white/5 rounded-lg p-2.5 text-xs text-zinc-300 focus:outline-none focus:border-white/15 resize-none leading-relaxed"
              />
            </div>

            <div className="flex flex-col gap-1">
              <label className="text-[10px] text-zinc-500 font-semibold uppercase">Audiencia Objetivo (NLP Target)</label>
              <input
                type="text"
                value={useCase3Params.audience}
                onChange={(e) => setUseCase3Params({ ...useCase3Params, audience: e.target.value })}
                disabled={isRunning}
                className="w-full bg-zinc-950/60 border border-white/5 rounded-lg px-3 py-2 text-xs text-zinc-300 focus:outline-none focus:border-white/15"
              />
            </div>

            <div className="flex flex-col gap-1">
              <label className="text-[10px] text-zinc-500 font-semibold uppercase">Presupuesto Inicial Ads (USD)</label>
              <input
                type="number"
                step={500}
                value={useCase3Params.budget}
                onChange={(e) => setUseCase3Params({ ...useCase3Params, budget: parseInt(e.target.value) })}
                disabled={isRunning}
                className="w-full bg-zinc-950/60 border border-white/5 rounded-lg px-3 py-2 text-xs text-zinc-300 focus:outline-none focus:border-white/15"
              />
            </div>
          </div>
        )}

        {/* Bottom Execute Button */}
        <button
          onClick={handleRun}
          disabled={isRunning}
          className="cyber-btn cyber-btn-primary w-full py-2.5 rounded-lg text-xs flex items-center justify-center gap-2 mt-4"
        >
          <Play size={12} fill="currentColor" />
          {isRunning ? "War Room en Proceso..." : "Iniciar Flujo del War Room"}
        </button>
      </div>
    </div>
  );
};
