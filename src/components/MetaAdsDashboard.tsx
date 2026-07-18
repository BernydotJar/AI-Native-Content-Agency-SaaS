import React from "react";
import { 
  TrendingUp, 
  DollarSign, 
  Users, 
  RefreshCw, 
  Cpu, 
  BarChart3 
} from "lucide-react";
import { GlowCard } from "./GlowCard";


export interface MetaAdsCampaign {
  id: string;
  name: string;
  budget: number;
  spent: number;
  ctr: number;
  cac: number;
  impressions: number;
  conversions: number;
  status: "active" | "paused" | "pending";
  targeting: {
    demographics: string;
    interests: string[];
    locations: string[];
  };
}

interface MetaAdsDashboardProps {
  campaigns: MetaAdsCampaign[];
  isSyncing: boolean;
  onSync: () => void;
}

export const MetaAdsDashboard: React.FC<MetaAdsDashboardProps> = ({
  campaigns,
  isSyncing,
  onSync
}) => {
  // Aggregate stats
  const totalBudget = campaigns.reduce((acc, c) => acc + c.budget, 0);
  const totalSpent = campaigns.reduce((acc, c) => acc + c.spent, 0);
  const averageCtr = campaigns.length > 0
    ? campaigns.reduce((acc, c) => acc + c.ctr, 0) / campaigns.length
    : 0;
  const totalImpressions = campaigns.reduce((acc, c) => acc + c.impressions, 0);
  const totalConversions = campaigns.reduce((acc, c) => acc + c.conversions, 0);
  const averageCac = totalConversions > 0 ? totalSpent / totalConversions : 0;

  return (
    <div className="flex flex-col gap-4">
      {/* Dashboard Top Header */}
      <div className="flex justify-between items-center">
        <div>
          <h3 className="text-sm font-semibold text-zinc-100 flex items-center gap-1.5">
            <Cpu size={14} className="text-sky-400" />
            Meta Ads / Sandbox Adapter
          </h3>
          <p className="text-[10px] text-zinc-500">
            Métricas locales simuladas · sin gasto ni conexión externa
          </p>
        </div>

        <button
          onClick={onSync}
          disabled={isSyncing}
          type="button"
          aria-label="Simular sincronización de métricas de Meta Ads"
          className={`cyber-btn min-h-11 px-3 py-2 rounded-lg text-[11px] flex items-center gap-1 ${
            isSyncing ? 'opacity-60' : ''
          }`}
        >
          <RefreshCw size={10} className={isSyncing ? "animate-spin" : ""} />
          {isSyncing ? "Simulando..." : "Simular pulso"}
        </button>
      </div>

      {/* Aggregate Stats Row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <GlowCard className="p-3 bg-zinc-950/40 border border-white/5 flex flex-col gap-1 justify-between">
          <div className="flex justify-between items-center text-[11px] text-zinc-400">
            <span>Presupuesto Total</span>
            <DollarSign size={10} className="text-sky-400" />
          </div>
          <div className="flex flex-col">
            <span className="text-lg font-bold text-zinc-100">${totalBudget.toLocaleString()}</span>
            <span className="text-[10px] text-zinc-400">Gasto: ${totalSpent.toLocaleString()}</span>
          </div>
        </GlowCard>

        <GlowCard className="p-3 bg-zinc-950/40 border border-white/5 flex flex-col gap-1 justify-between">
          <div className="flex justify-between items-center text-[11px] text-zinc-400">
            <span>CTR Promedio</span>
            <TrendingUp size={10} className="text-emerald-400" />
          </div>
          <div className="flex flex-col">
            <span className="text-lg font-bold text-emerald-400">{averageCtr.toFixed(2)}%</span>
            <span className="text-[10px] text-zinc-400">Conversiones: {totalConversions}</span>
          </div>
        </GlowCard>

        <GlowCard className="p-3 bg-zinc-950/40 border border-white/5 flex flex-col gap-1 justify-between">
          <div className="flex justify-between items-center text-[11px] text-zinc-400">
            <span>CAC Promedio</span>
            <Users size={10} className="text-purple-400" />
          </div>
          <div className="flex flex-col">
            <span className="text-lg font-bold text-purple-400">${averageCac.toFixed(2)}</span>
            <span className="text-[10px] text-zinc-400">Referencia: &lt; $12.00</span>
          </div>
        </GlowCard>

        <GlowCard className="p-3 bg-zinc-950/40 border border-white/5 flex flex-col gap-1 justify-between">
          <div className="flex justify-between items-center text-[11px] text-zinc-400">
            <span>Impresiones</span>
            <BarChart3 size={10} className="text-zinc-400" />
          </div>
          <div className="flex flex-col">
            <span className="text-lg font-bold text-zinc-100">{totalImpressions.toLocaleString()}</span>
            <span className="text-[10px] text-zinc-400">Frecuencia simulada: 1.4x</span>
          </div>
        </GlowCard>
      </div>

      {/* Campaigns list */}
      <div className="flex flex-col gap-2">
        <h4 className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider">Campañas simuladas</h4>
        {campaigns.length === 0 ? (
          <div className="glass-panel rounded-xl border border-white/5 bg-zinc-950/20 p-6 text-center text-xs text-zinc-600">
            Ninguna campaña activa. Inicia un flujo de Use Case 3 para crear una campaña automatizada.
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            {campaigns.map((camp) => (
              <GlowCard key={camp.id} className="p-3.5 bg-zinc-950/60 border border-white/5 flex flex-col gap-3">
                {/* Header info */}
                <div className="flex justify-between items-start">
                  <div>
                    <h5 className="text-xs font-semibold text-zinc-200">{camp.name}</h5>
                    <p className="text-[9px] text-zinc-500">{camp.targeting.demographics}</p>
                  </div>
                  <span className={`text-[8px] font-semibold px-2 py-0.5 rounded-full ${
                    camp.status === "active" ? "bg-emerald-500/15 text-emerald-400" :
                    camp.status === "pending" ? "bg-amber-500/15 text-amber-400" :
                    "bg-zinc-800 text-zinc-500"
                  }`}>
                    {camp.status === "active" ? "Activo / sim" : camp.status === "pending" ? "Fixture..." : "Pausada"}
                  </span>
                </div>

                {/* Progress bar spent */}
                <div className="flex flex-col gap-1">
                  <div className="flex justify-between text-[9px] text-zinc-400">
                    <span>Presupuesto Consumido</span>
                    <span>${camp.spent} / ${camp.budget}</span>
                  </div>
                  <div className="w-full h-1 bg-white/5 rounded-full overflow-hidden">
                    <div 
                      role="progressbar"
                      aria-label={`Presupuesto consumido de ${camp.name}`}
                      aria-valuemin={0}
                      aria-valuemax={camp.budget}
                      aria-valuenow={Math.min(camp.budget, camp.spent)}
                      className="h-full bg-sky-500 transition-all duration-300"
                      style={{ width: `${camp.budget > 0 ? Math.min(100, (camp.spent / camp.budget) * 100) : 0}%` }}
                    />
                  </div>
                </div>

                {/* Grid details and targeting */}
                <div className="grid grid-cols-3 gap-2 border-t border-b border-white/5 py-2 text-[10px]">
                  <div className="flex flex-col">
                    <span className="text-zinc-500 text-[8px]">CTR</span>
                    <span className="font-semibold text-zinc-200">{camp.ctr}%</span>
                  </div>
                  <div className="flex flex-col">
                    <span className="text-zinc-500 text-[8px]">CAC</span>
                    <span className="font-semibold text-zinc-200">${camp.cac}</span>
                  </div>
                  <div className="flex flex-col">
                    <span className="text-zinc-500 text-[8px]">Conversiones</span>
                    <span className="font-semibold text-zinc-200">{camp.conversions}</span>
                  </div>
                </div>

                {/* Targeting interests tags */}
                <div className="flex flex-wrap gap-1 items-center">
                  <span className="text-[8px] text-zinc-500 font-medium mr-1 uppercase">Target:</span>
                  {camp.targeting.interests.map((tag, idx) => (
                    <span key={idx} className="text-[8px] bg-white/5 border border-white/5 rounded px-1.5 py-0.5 text-zinc-400">
                      {tag}
                    </span>
                  ))}
                </div>
              </GlowCard>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
