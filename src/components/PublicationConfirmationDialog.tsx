import { useEffect, useRef, useState } from "react";
import { AlertTriangle, LoaderCircle, Send, X } from "lucide-react";
import type { RuntimeSocialChannel } from "../lib/runtimeApi";
import { useModalDialog } from "../lib/useModalDialog";

interface PublicationConfirmationDialogProps {
  open: boolean;
  channel: RuntimeSocialChannel | null;
  artifactId: string;
  mediaArtifactId: string | null;
  requiredPhrase: string;
  busy: boolean;
  error: string;
  onClose: () => void;
  onConfirm: (phrase: string) => void;
}

export function PublicationConfirmationDialog({
  open,
  channel,
  artifactId,
  mediaArtifactId,
  requiredPhrase,
  busy,
  error,
  onClose,
  onConfirm,
}: PublicationConfirmationDialogProps) {
  const dialogRef = useRef<HTMLElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const [typedPhrase, setTypedPhrase] = useState("");
  useEffect(() => {
    setTypedPhrase("");
  }, [open, requiredPhrase]);
  useModalDialog({
    open,
    onClose: busy ? () => undefined : onClose,
    dialogRef,
    initialFocusRef: closeButtonRef,
  });

  if (!open || !channel) return null;
  const account = channel.connected_account;

  return (
    <div className="fixed inset-0 z-[130] grid place-items-center bg-black/80 p-4 backdrop-blur-sm" role="presentation">
      <section
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="publication-confirmation-title"
        aria-describedby="publication-confirmation-description"
        className="w-full max-w-lg rounded-2xl border border-amber-200/20 bg-zinc-950 p-5 shadow-2xl sm:p-6"
      >
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl border border-amber-200/20 bg-amber-200/[0.06] text-amber-100">
              <AlertTriangle size={17} aria-hidden="true" />
            </span>
            <div>
              <p className="section-kicker">EFECTO EXTERNO / CONFIRMACIÓN</p>
              <h2 id="publication-confirmation-title" className="mt-1 text-lg font-bold text-zinc-100">
                Publicar en {channel.display_name}
              </h2>
            </div>
          </div>
          <button
            ref={closeButtonRef}
            type="button"
            onClick={onClose}
            disabled={busy}
            className="grid min-h-10 min-w-10 place-items-center rounded-xl border border-white/[0.09] text-zinc-400 disabled:opacity-35"
            aria-label="Cancelar publicación"
          >
            <X size={15} aria-hidden="true" />
          </button>
        </div>

        <p id="publication-confirmation-description" className="mt-5 text-sm leading-6 text-zinc-300">
          Esta acción contactará al proveedor y puede crear una publicación visible. El intent durable se reservará antes de la solicitud y no se reintentará automáticamente si el resultado queda ambiguo.
        </p>

        <dl className="mt-5 grid gap-3 rounded-xl border border-white/[0.08] bg-black/30 p-4 text-xs sm:grid-cols-2">
          <div>
            <dt className="font-mono text-[9px] uppercase text-zinc-600">Cuenta</dt>
            <dd className="mt-1 font-semibold text-zinc-200">
              {account ? `@${account.account_username}` : "Sin cuenta autorizada"}
            </dd>
          </div>
          <div>
            <dt className="font-mono text-[9px] uppercase text-zinc-600">Artefacto</dt>
            <dd className="mt-1 break-all font-mono text-[10px] text-zinc-300">{artifactId}</dd>
          </div>
          <div>
            <dt className="font-mono text-[9px] uppercase text-zinc-600">Media</dt>
            <dd className="mt-1 font-semibold text-zinc-200">
              {mediaArtifactId ?? "No requerida"}
            </dd>
          </div>
          <div>
            <dt className="font-mono text-[9px] uppercase text-zinc-600">Control</dt>
            <dd className="mt-1 font-semibold text-emerald-200">Greenlight + exact-once</dd>
          </div>
        </dl>

        {requiredPhrase && (
          <div className="mt-5 rounded-xl border border-amber-200/20 bg-amber-200/[0.04] p-4">
            <p className="text-xs font-bold text-amber-100">Confirmación política obligatoria</p>
            <p className="mt-2 text-[11px] leading-5 text-zinc-400">
              Escribe exactamente la frase siguiente. El servidor conservará únicamente su SHA-256.
            </p>
            <code className="mt-3 block break-all rounded-lg bg-black/40 p-3 text-[10px] text-amber-100">
              {requiredPhrase}
            </code>
            <label className="mt-3 block text-[11px] font-semibold text-zinc-300">
              Frase de confirmación política
              <input
                value={typedPhrase}
                onChange={(event) => setTypedPhrase(event.target.value)}
                disabled={busy}
                autoComplete="off"
                className="form-control mt-2"
              />
            </label>
          </div>
        )}

        {error && (
          <p role="alert" className="mt-4 rounded-xl border border-red-300/20 bg-red-300/[0.05] p-3 text-xs leading-5 text-red-100">
            {error}
          </p>
        )}

        <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <button
            type="button"
            onClick={onClose}
            disabled={busy}
            className="min-h-11 rounded-xl border border-white/[0.1] px-4 text-xs font-bold text-zinc-300 disabled:opacity-35"
          >
            Cancelar
          </button>
          <button
            type="button"
            onClick={() => onConfirm(typedPhrase)}
            disabled={busy || !account || Boolean(requiredPhrase && typedPhrase !== requiredPhrase)}
            className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-amber-200 px-4 text-xs font-extrabold text-black disabled:opacity-35"
          >
            {busy ? <LoaderCircle size={14} className="animate-spin" aria-hidden="true" /> : <Send size={14} aria-hidden="true" />}
            {busy ? "Registrando intent y publicando…" : "Confirmar publicación externa"}
          </button>
        </div>
      </section>
    </div>
  );
}
