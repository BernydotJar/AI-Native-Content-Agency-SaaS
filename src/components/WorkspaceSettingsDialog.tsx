import { useRef } from "react";
import { Cable, Check, LockKeyhole, Palette, RefreshCw, ServerCog, X } from "lucide-react";
import type { RuntimeIntegrationSummary, RuntimeProvider, RuntimeProviderGatewayStatus, RuntimeSocialChannel } from "../lib/runtimeApi";
import { THEME_CATALOG, isThemeAvailable } from "../lib/themeCatalog";
import type { ThemeId } from "../lib/themeCatalog";
import { useModalDialog } from "../lib/useModalDialog";

interface WorkspaceSettingsDialogProps {
  open: boolean;
  onClose: () => void;
  activeTheme: ThemeId;
  premiumThemeEntitled: boolean;
  onThemeChange: (themeId: ThemeId) => void;
  providers: readonly RuntimeProvider[];
  gateway: RuntimeProviderGatewayStatus;
  integrations: readonly RuntimeIntegrationSummary[];
  socialChannels: readonly RuntimeSocialChannel[];
  providerLoading: boolean;
  providerError: string;
  sessionActive: boolean;
  onRefreshProviders: () => void;
}

const STATE_LABELS: Record<RuntimeProvider["configuration_state"], string> = {
  ready: "Listo",
  missing_credential: "Falta credencial",
  missing_model: "Falta modelo",
  missing_endpoint: "Falta endpoint",
};

const SOCIAL_STATE_LABELS: Record<RuntimeSocialChannel["configuration_state"], string> = {
  missing_credentials: "Faltan credenciales",
  missing_redirect_uri: "Falta callback OAuth",
  ready_for_authentication: "Lista para autenticar",
};

export function WorkspaceSettingsDialog({
  open,
  onClose,
  activeTheme,
  premiumThemeEntitled,
  onThemeChange,
  providers,
  gateway,
  integrations,
  socialChannels,
  providerLoading,
  providerError,
  sessionActive,
  onRefreshProviders,
}: WorkspaceSettingsDialogProps) {
  const dialogRef = useRef<HTMLElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  useModalDialog({
    open,
    onClose,
    dialogRef,
    initialFocusRef: closeButtonRef,
  });

  if (!open) return null;
  const configuredCount = providers.filter((provider) => provider.configured).length;

  return (
    <div className="fixed inset-0 z-[110] flex justify-end bg-black/70 backdrop-blur-sm" role="presentation">
      <section
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="workspace-settings-title"
        className="h-full w-full max-w-2xl overflow-y-auto border-l border-white/[0.1] bg-zinc-950 shadow-2xl"
      >
        <header className="sticky top-0 z-10 flex items-start justify-between gap-4 border-b border-white/[0.08] bg-zinc-950/95 px-5 py-5 backdrop-blur-xl sm:px-7">
          <div>
            <p className="section-kicker">Configuración del espacio</p>
            <h2 id="workspace-settings-title" className="mt-1 text-xl font-bold text-zinc-100">
              Administración del espacio
            </h2>
            <p className="mt-1 text-xs leading-5 text-zinc-500">
              La configuración infrecuente vive aquí para mantener la misión enfocada en resultados.
            </p>
          </div>
          <button
            ref={closeButtonRef}
            type="button"
            onClick={onClose}
            className="grid min-h-11 min-w-11 place-items-center rounded-xl border border-white/[0.09] text-zinc-400 hover:text-zinc-100"
            aria-label="Cerrar configuración del espacio"
          >
            <X size={16} aria-hidden="true" />
          </button>
        </header>

        <div className="space-y-8 p-5 sm:p-7">
          <section aria-labelledby="appearance-settings-title">
            <div className="flex items-center gap-3">
              <span className="grid h-10 w-10 place-items-center rounded-xl border border-white/[0.08] bg-white/[0.03] text-[var(--primary-color)]">
                <Palette size={16} aria-hidden="true" />
              </span>
              <div>
                <h3 id="appearance-settings-title" className="text-sm font-bold text-zinc-100">Apariencia</h3>
                <p className="mt-0.5 text-[11px] text-zinc-500">Preferencia personal; nunca cambia permisos ni decisiones de campaña.</p>
              </div>
            </div>
            <div className="mt-4 grid gap-2 sm:grid-cols-2" role="group" aria-label="Tema del espacio de trabajo">
              {THEME_CATALOG.map((theme) => {
                const available = isThemeAvailable(theme, premiumThemeEntitled);
                const selected = activeTheme === theme.id;
                return (
                  <button
                    key={theme.id}
                    type="button"
                    aria-label={theme.label}
                    aria-pressed={selected}
                    aria-disabled={!available}
                    onClick={() => available && onThemeChange(theme.id)}
                    className={`flex min-h-16 items-center gap-3 rounded-xl border px-4 py-3 text-left transition ${
                      selected
                        ? "border-[var(--primary-color)] bg-[var(--primary-color)]/10"
                        : "border-white/[0.08] bg-white/[0.02] hover:border-white/[0.16]"
                    } ${available ? "" : "cursor-not-allowed opacity-55"}`}
                  >
                    <span className="h-5 w-5 shrink-0 rounded-full border border-black/30" style={{ background: theme.accent }} aria-hidden="true" />
                    <span className="min-w-0 flex-1">
                      <span className="block text-xs font-bold text-zinc-100">{theme.label}</span>
                      <span className="mt-0.5 block text-[10px] leading-4 text-zinc-500">
                        {theme.premium && !available ? "Requiere entitlement premium" : theme.description}
                      </span>
                    </span>
                    {selected ? <Check size={14} className="text-[var(--primary-color)]" aria-hidden="true" /> : theme.premium ? <LockKeyhole size={13} className="text-zinc-500" aria-hidden="true" /> : null}
                  </button>
                );
              })}
            </div>
          </section>

          <section aria-labelledby="provider-settings-title" className="border-t border-white/[0.07] pt-7">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-center gap-3">
                <span className="grid h-10 w-10 place-items-center rounded-xl border border-white/[0.08] bg-white/[0.03] text-[var(--primary-color)]">
                  <ServerCog size={16} aria-hidden="true" />
                </span>
                <div>
                  <h3 id="provider-settings-title" className="text-sm font-bold text-zinc-100">Proveedores de modelos</h3>
                  <p className="mt-0.5 text-[11px] text-zinc-500">Credenciales y enrutamiento de modelos administrados por el servidor.</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className="rounded-full border border-white/[0.08] px-3 py-1.5 font-mono text-[10px] text-zinc-400">
                  {configuredCount}/{providers.length || 5} listos
                </span>
                <button
                  type="button"
                  onClick={onRefreshProviders}
                  disabled={!sessionActive || providerLoading}
                  className="grid min-h-10 min-w-10 place-items-center rounded-full border border-white/[0.08] text-zinc-400 hover:text-zinc-100 disabled:opacity-35"
                  aria-label="Actualizar configuración de proveedores"
                >
                  <RefreshCw size={13} className={providerLoading ? "animate-spin" : ""} aria-hidden="true" />
                </button>
              </div>
            </div>

            {sessionActive && (
              <div className={`mt-4 rounded-xl border p-4 text-[11px] leading-5 ${
                gateway.execution_enabled
                  ? "border-amber-300/20 bg-amber-300/[0.05] text-amber-100"
                  : "border-white/[0.08] bg-white/[0.02] text-zinc-400"
              }`}>
                <p className="font-bold text-zinc-200">
                  {gateway.execution_enabled
                    ? `Gateway protocol-ready: ${gateway.selected_provider}`
                    : "Gateway de inferencia deshabilitado"}
                </p>
                <p className="mt-1">
                  {gateway.execution_enabled
                    ? gateway.execution_available
                      ? "El protocolo HTTP está disponible, pero todavía no está conectado a los runs: falta un receipt outbound durable que evite gasto duplicado."
                      : "El gateway fue habilitado, pero la configuración seleccionada no está disponible."
                    : "El catálogo puede inspeccionarse, pero no se realizan llamadas a modelos ni gasto externo."}
                </p>
                <p className="mt-2 font-mono text-[9px] uppercase tracking-[0.08em] opacity-70">
                  receipt durable: {gateway.durable_outbound_receipt ? "sí" : "no"} · integración automática: {gateway.automatic_run_integration ? "sí" : "no"}
                </p>
              </div>
            )}

            {!sessionActive ? (
              <div className="mt-4 rounded-xl border border-dashed border-white/[0.09] p-5 text-xs leading-6 text-zinc-500">
                Conecta el espacio para inspeccionar la configuración autorizada del tenant. Las credenciales de proveedores nunca se solicitan ni se muestran en el navegador.
              </div>
            ) : providerError ? (
              <div role="status" className="mt-4 rounded-xl border border-red-300/15 bg-red-300/[0.04] p-4 text-xs leading-5 text-red-100">
                {providerError}
              </div>
            ) : providerLoading && providers.length === 0 ? (
              <div role="status" className="mt-4 rounded-xl border border-white/[0.08] p-4 text-xs text-zinc-500">Cargando estado de proveedores del servidor…</div>
            ) : (
              <div className="mt-4 space-y-2">
                {providers.map((provider) => (
                  <article key={provider.provider_id} className="rounded-xl border border-white/[0.08] bg-white/[0.02] p-4">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <h4 className="text-sm font-bold text-zinc-100">{provider.display_name}</h4>
                          <span className={`rounded-full border px-2 py-1 font-mono text-[9px] uppercase ${provider.configured ? "border-emerald-300/20 bg-emerald-300/[0.06] text-emerald-200" : "border-amber-300/20 bg-amber-300/[0.05] text-amber-100"}`}>
                            {STATE_LABELS[provider.configuration_state]}
                          </span>
                        </div>
                        <p className="mt-1 font-mono text-[10px] text-zinc-500">{provider.protocol.replaceAll("_", " ")}</p>
                      </div>
                      <div className="text-left sm:text-right">
                        <p className="text-xs font-semibold text-zinc-300">{provider.model || "Sin modelo seleccionado"}</p>
                        <p className="mt-1 font-mono text-[9px] text-zinc-600">{provider.endpoint_host || "Endpoint no configurado"}</p>
                      </div>
                    </div>
                    <div className="mt-3 grid gap-2 border-t border-white/[0.06] pt-3 text-[10px] leading-4 text-zinc-500 sm:grid-cols-2">
                      <p>Credencial: entorno del servidor</p>
                      <p>Recomendados: {provider.recommended_models.join(" · ")}</p>
                    </div>
                  </article>
                ))}
              </div>
            )}

            <div className="mt-4 rounded-xl border border-sky-300/15 bg-sky-300/[0.04] p-4 text-[11px] leading-5 text-sky-100/80">
              El estado mostrado es evidencia real de configuración. Esta pantalla no ejecuta inferencia, gasto ni entregas externas.
            </div>
          </section>

          <section aria-labelledby="social-channel-settings-title" className="border-t border-white/[0.07] pt-7">
            <div className="flex items-center gap-3">
              <span className="grid h-10 w-10 place-items-center rounded-xl border border-white/[0.08] bg-white/[0.03] text-[var(--primary-color)]">
                <Cable size={16} aria-hidden="true" />
              </span>
              <div>
                <h3 id="social-channel-settings-title" className="text-sm font-bold text-zinc-100">Canales de publicación</h3>
                <p className="mt-0.5 text-[11px] text-zinc-500">X e Instagram usan credenciales server-side y autorización por cuenta.</p>
              </div>
            </div>
            {!sessionActive ? (
              <p className="mt-4 rounded-xl border border-dashed border-white/[0.09] p-4 text-xs leading-5 text-zinc-500">Conecta el espacio para inspeccionar canales sociales.</p>
            ) : socialChannels.length === 0 ? (
              <p className="mt-4 rounded-xl border border-dashed border-white/[0.09] p-4 text-xs leading-5 text-zinc-500">El catálogo de canales está temporalmente vacío.</p>
            ) : (
              <div className="mt-4 space-y-3">
                {socialChannels.map((channel) => (
                  <article key={channel.channel_id} className="rounded-2xl border border-white/[0.08] bg-white/[0.02] p-4">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <div>
                        <h4 className="text-sm font-bold text-zinc-100">{channel.display_name}</h4>
                        <p className="mt-1 text-[10px] leading-5 text-zinc-500">{channel.account_requirement}</p>
                      </div>
                      <span className={`self-start rounded-full border px-3 py-1 font-mono text-[9px] uppercase ${channel.configured ? "border-emerald-300/20 bg-emerald-300/[0.06] text-emerald-200" : "border-amber-300/20 bg-amber-300/[0.05] text-amber-100"}`}>
                        {SOCIAL_STATE_LABELS[channel.configuration_state]}
                      </span>
                    </div>

                    <div className="mt-4 grid gap-2 sm:grid-cols-3">
                      <div className="rounded-xl border border-white/[0.06] bg-black/20 p-3">
                        <p className="font-mono text-[8px] uppercase text-zinc-600">Credenciales</p>
                        <p className="mt-1 text-[10px] font-semibold text-zinc-300">{channel.credentials_configured ? "Configuradas" : "Pendientes"}</p>
                      </div>
                      <div className="rounded-xl border border-white/[0.06] bg-black/20 p-3">
                        <p className="font-mono text-[8px] uppercase text-zinc-600">Callback</p>
                        <p className="mt-1 text-[10px] font-semibold text-zinc-300">{channel.callback_configured ? "Configurada" : "Pendiente"}</p>
                      </div>
                      <div className="rounded-xl border border-white/[0.06] bg-black/20 p-3">
                        <p className="font-mono text-[8px] uppercase text-zinc-600">Cuenta</p>
                        <p className="mt-1 text-[10px] font-semibold text-zinc-300">{channel.connection_state === "connected" ? "Conectada" : "Sin autenticar"}</p>
                      </div>
                    </div>

                    <div className="mt-4 rounded-xl border border-white/[0.06] bg-black/20 p-3 text-[9px] leading-5 text-zinc-500">
                      <p><span className="text-zinc-300">Variables:</span> {channel.credential_environments.join(" · ")} · {channel.redirect_environment}</p>
                      <p><span className="text-zinc-300">Protocolo:</span> {channel.publish_protocol}</p>
                      {channel.requires_media && <p className="text-amber-100/80">Instagram requiere imagen, reel o carrusel además del caption.</p>}
                    </div>

                    <div className="mt-3 rounded-xl border border-sky-300/15 bg-sky-300/[0.04] p-3 text-[10px] leading-5 text-sky-100/80">
                      {channel.configured
                        ? "La app y callback están listas. Falta implementar y ejecutar la autorización OAuth con token storage cifrado antes de publicar."
                        : "Define las variables indicadas en el servidor y pulsa Actualizar; los valores nunca se devuelven al navegador."}
                    </div>
                  </article>
                ))}
              </div>
            )}
          </section>

          <section aria-labelledby="integration-settings-title" className="border-t border-white/[0.07] pt-7">
            <div className="flex items-center gap-3">
              <span className="grid h-10 w-10 place-items-center rounded-xl border border-white/[0.08] bg-white/[0.03] text-[var(--primary-color)]">
                <Cable size={16} aria-hidden="true" />
              </span>
              <div>
                <h3 id="integration-settings-title" className="text-sm font-bold text-zinc-100">Integraciones revisadas</h3>
                <p className="mt-0.5 text-[11px] text-zinc-500">Herramientas adicionales evaluadas y deshabilitadas por defecto.</p>
              </div>
            </div>
            {!sessionActive ? (
              <p className="mt-4 rounded-xl border border-dashed border-white/[0.09] p-4 text-xs leading-5 text-zinc-500">Conecta el espacio para inspeccionar integraciones.</p>
            ) : integrations.length === 0 ? (
              <p className="mt-4 rounded-xl border border-dashed border-white/[0.09] p-4 text-xs leading-5 text-zinc-500">No hay integraciones revisadas para este tenant.</p>
            ) : (
              <div className="mt-4 space-y-2">
                {integrations.map((integration) => (
                  <article key={integration.integration_id} className="rounded-xl border border-white/[0.08] bg-white/[0.02] p-4">
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                      <div>
                        <h4 className="text-sm font-bold text-zinc-100">{integration.display_name}</h4>
                        <p className="mt-1 font-mono text-[9px] text-zinc-600">{integration.integration_id}</p>
                      </div>
                      <span className="rounded-full border border-amber-300/20 bg-amber-300/[0.05] px-3 py-1 font-mono text-[9px] uppercase text-amber-100">
                        {integration.review_status.replaceAll("_", " ")}
                      </span>
                    </div>
                    <p className="mt-3 text-[10px] text-zinc-500">
                      Ejecución: {integration.execution_available ? "disponible" : "no disponible"} · efectos externos: {integration.external_effects_enabled ? "habilitados" : "deshabilitados"}
                    </p>
                  </article>
                ))}
              </div>
            )}
          </section>
        </div>
      </section>
    </div>
  );
}
