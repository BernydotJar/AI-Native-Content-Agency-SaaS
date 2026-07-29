import { describe, expect, it } from "vitest";
import { RuntimeApiError } from "./runtimeApi";
import {
  requiresSocialReconnect,
  socialPublicationErrorMessage,
} from "./socialPublicationError";

describe("social publication error mapping", () => {
  it("turns invalid provider authorization into an explicit reconnect action", () => {
    const error = new RuntimeApiError(
      409,
      "Instagram connection must be authorized again",
      "req-reconnect",
      "social_connection_reauthorization_required",
    );
    expect(requiresSocialReconnect(error)).toBe(true);
    expect(socialPublicationErrorMessage(error)).toMatch(/Reconecta Instagram/i);
  });

  it("preserves other safe runtime messages", () => {
    const error = new RuntimeApiError(
      502,
      "social provider rejected publication",
      "req-rejected",
      "social_publication_rejected",
    );
    expect(requiresSocialReconnect(error)).toBe(false);
    expect(socialPublicationErrorMessage(error)).toBe(
      "social provider rejected publication",
    );
  });
});
