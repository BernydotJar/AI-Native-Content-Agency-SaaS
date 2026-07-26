import { RuntimeApiError } from "./runtimeApi";

export function socialPublicationErrorMessage(error: unknown): string {
  if (
    error instanceof RuntimeApiError
    && error.code === "social_connection_reauthorization_required"
  ) {
    return "La autorización de Instagram expiró o fue revocada. Reconecta Instagram antes de publicar nuevamente.";
  }
  if (error instanceof Error) return error.message;
  return "No se pudo determinar el resultado de la publicación.";
}

export function requiresSocialReconnect(error: unknown): boolean {
  return error instanceof RuntimeApiError
    && error.code === "social_connection_reauthorization_required";
}
