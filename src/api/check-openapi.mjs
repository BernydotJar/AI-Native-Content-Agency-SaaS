import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

const documentPath = resolve(
  process.cwd(),
  process.env.OPENAPI_DOCUMENT ?? "backend/openapi.json",
);

const expectedPaths = {
  "/api/v1/identity": ["get"],
  "/api/v1/missions": ["post"],
  "/api/v1/missions/{mission_id}/runs": ["post"],
  "/api/v1/runs/{run_id}": ["get"],
  "/api/v1/runs/{run_id}/approvals": ["post"],
  "/healthz": ["get"],
  "/readyz": ["get"],
};

const expectedResponses = {
  "GET /api/v1/identity": {
    200: "IdentityResponse",
    401: "ErrorResponse",
    422: "ErrorResponse",
    500: "ErrorResponse",
  },
  "GET /healthz": {
    200: "HealthResponse",
    500: "ErrorResponse",
  },
  "GET /readyz": {
    200: "HealthResponse",
    500: "ErrorResponse",
    503: "ErrorResponse",
  },
  "POST /api/v1/missions": {
    201: "MissionResponse",
    400: "ErrorResponse",
    401: "ErrorResponse",
    409: "ErrorResponse",
    413: "ErrorResponse",
    422: "ErrorResponse",
    500: "ErrorResponse",
    503: "ErrorResponse",
  },
  "POST /api/v1/missions/{mission_id}/runs": {
    201: "RunResponse",
    400: "ErrorResponse",
    401: "ErrorResponse",
    404: "ErrorResponse",
    409: "ErrorResponse",
    413: "ErrorResponse",
    422: "ErrorResponse",
    500: "ErrorResponse",
    503: "ErrorResponse",
  },
  "GET /api/v1/runs/{run_id}": {
    200: "RunResponse",
    401: "ErrorResponse",
    404: "ErrorResponse",
    422: "ErrorResponse",
    500: "ErrorResponse",
    503: "ErrorResponse",
  },
  "POST /api/v1/runs/{run_id}/approvals": {
    200: "RunResponse",
    400: "ErrorResponse",
    401: "ErrorResponse",
    404: "ErrorResponse",
    409: "ErrorResponse",
    413: "ErrorResponse",
    422: "ErrorResponse",
    500: "ErrorResponse",
    503: "ErrorResponse",
  },
};

const expectedSchemaProperties = {
  AuditEventResponse: [
    "action",
    "audit_id",
    "correlation_id",
    "occurred_at",
    "payload",
    "principal_id",
    "schema_version",
  ],
  ApprovalCreate: [
    "artifact_manifest_hash",
    "decision",
    "note",
    "policy_version",
    "reviewer",
    "schema_version",
  ],
  ApprovalResponse: [
    "approval_id",
    "artifact_manifest_hash",
    "decided_at",
    "decision",
    "idempotency_key",
    "note",
    "policy_version",
    "principal_id",
    "reviewer",
    "schema_version",
  ],
  ArtifactResponse: [
    "artifact_id",
    "created_at",
    "created_by",
    "evidence_ids",
    "kind",
    "ordinal",
    "payload",
    "schema_version",
    "title",
  ],
  ErrorBody: ["code", "correlation_id", "details", "message"],
  ErrorResponse: ["error", "schema_version"],
  HealthResponse: ["schema_version", "status"],
  IdentityResponse: ["principal", "schema_version", "tenant"],
  MissionCreate: [
    "audience",
    "budget_cents",
    "campaign_goal",
    "objective",
    "platforms",
    "schema_version",
    "source_asset",
    "title",
  ],
  MissionResponse: [
    "audience",
    "budget_cents",
    "campaign_goal",
    "created_at",
    "created_by",
    "mission_id",
    "objective",
    "platforms",
    "schema_version",
    "source_asset",
    "tenant_id",
    "title",
    "version",
  ],
  PrincipalIdentityResponse: [
    "auth_mode",
    "principal_id",
    "schema_version",
    "tenant_id",
  ],
  RunEventResponse: [
    "action",
    "artifact_ids",
    "detail",
    "event_id",
    "evidence_ids",
    "role",
    "schema_version",
    "sequence",
    "status",
    "timestamp",
  ],
  RunResponse: [
    "approval",
    "artifact_manifest_hash",
    "artifacts",
    "audit_events",
    "completed_at",
    "events",
    "evidence",
    "external_side_effects",
    "mission_id",
    "policy_version",
    "run_id",
    "schema_version",
    "started_at",
    "status",
    "steps",
    "tenant_id",
    "version",
  ],
  RunStart: ["schema_version"],
  RunStepResponse: [
    "detail",
    "progress",
    "role",
    "schema_version",
    "sequence",
    "status",
    "step_id",
    "updated_at",
  ],
  ToolEvidenceResponse: [
    "created_at",
    "evidence_id",
    "operation",
    "payload",
    "references",
    "sandbox",
    "schema_version",
    "summary",
    "tool",
  ],
  TenantIdentityResponse: ["schema_version", "tenant_id"],
};

const expectedEnums = {
  AgentRole: ["ceo", "growth", "media", "publisher", "research", "risk", "strategist", "writer"],
  AgentStatus: ["attention", "blocked", "processing", "ready", "standby", "waiting_greenlight"],
  ApprovalDecision: ["approved", "rejected"],
  Platform: ["facebook", "instagram", "tiktok", "x"],
  RunStatus: ["awaiting_greenlight", "completed", "failed", "rejected", "running"],
};

const identityPattern = "^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$";
const idempotencyPattern = "^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$";
const expectedHeaders = {
  "GET /api/v1/identity": {
    "X-Principal-ID": identityPattern,
    "X-Tenant-ID": identityPattern,
  },
  "GET /api/v1/runs/{run_id}": {
    "X-Principal-ID": identityPattern,
    "X-Tenant-ID": identityPattern,
  },
  "POST /api/v1/missions": {
    "Idempotency-Key": idempotencyPattern,
    "X-Principal-ID": identityPattern,
    "X-Tenant-ID": identityPattern,
  },
  "POST /api/v1/missions/{mission_id}/runs": {
    "Idempotency-Key": idempotencyPattern,
    "X-Principal-ID": identityPattern,
    "X-Tenant-ID": identityPattern,
  },
  "POST /api/v1/runs/{run_id}/approvals": {
    "Idempotency-Key": idempotencyPattern,
    "X-Principal-ID": identityPattern,
    "X-Tenant-ID": identityPattern,
  },
};

const expectedDateTimeFields = {
  ApprovalResponse: ["decided_at"],
  ArtifactResponse: ["created_at"],
  AuditEventResponse: ["occurred_at"],
  MissionResponse: ["created_at"],
  RunEventResponse: ["timestamp"],
  RunResponse: ["completed_at", "started_at"],
  RunStepResponse: ["updated_at"],
  ToolEvidenceResponse: ["created_at"],
};

function fail(message) {
  throw new Error(`OpenAPI/frontend contract drift: ${message}`);
}

function exactKeys(value) {
  return Object.keys(value ?? {}).sort();
}

function assertEqual(actual, expected, label) {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    fail(`${label}; expected ${JSON.stringify(expected)}, received ${JSON.stringify(actual)}`);
  }
}

let document;
try {
  document = JSON.parse(await readFile(documentPath, "utf8"));
} catch (error) {
  fail(`cannot read canonical document at ${documentPath}: ${error instanceof Error ? error.message : "unknown error"}`);
}

if (typeof document.openapi !== "string" || !document.openapi.startsWith("3.")) {
  fail("canonical document is not OpenAPI 3.x");
}

for (const [path, methods] of Object.entries(expectedPaths)) {
  if (!document.paths?.[path]) fail(`missing path ${path}`);
  for (const method of methods) {
    if (!document.paths[path][method]) fail(`missing ${method.toUpperCase()} ${path}`);
  }
}

for (const [operation, expected] of Object.entries(expectedResponses)) {
  const separator = operation.indexOf(" ");
  const method = operation.slice(0, separator).toLowerCase();
  const path = operation.slice(separator + 1);
  const responses = document.paths?.[path]?.[method]?.responses;
  if (!responses) fail(`missing responses for ${operation}`);
  assertEqual(exactKeys(responses), exactKeys(expected), `${operation} response statuses changed`);
  for (const [status, schemaName] of Object.entries(expected)) {
    const actualRef = responses[status]?.content?.["application/json"]?.schema?.$ref;
    const expectedRef = `#/components/schemas/${schemaName}`;
    if (actualRef !== expectedRef) {
      fail(`${operation} ${status} must use ${expectedRef}, received ${actualRef ?? "no schema"}`);
    }
  }
}

for (const [operation, expected] of Object.entries(expectedHeaders)) {
  const separator = operation.indexOf(" ");
  const method = operation.slice(0, separator).toLowerCase();
  const path = operation.slice(separator + 1);
  const headers = (document.paths?.[path]?.[method]?.parameters ?? [])
    .filter((parameter) => parameter.in === "header");
  assertEqual(headers.map((header) => header.name).sort(), Object.keys(expected).sort(), `${operation} headers changed`);
  for (const [name, pattern] of Object.entries(expected)) {
    const header = headers.find((candidate) => candidate.name === name);
    if (header?.required !== true) fail(`${operation} ${name} must be required`);
    if (header?.schema?.type !== "string" || header.schema.pattern !== pattern || header.schema.anyOf) {
      fail(`${operation} ${name} must be a non-null string with its exact pattern`);
    }
  }
}

const schemas = document.components?.schemas;
if (!schemas) fail("components.schemas is absent");
if (schemas.HTTPValidationError || schemas.ValidationError) {
  fail("framework validation schemas leaked into the versioned error contract");
}

for (const [name, expectedProperties] of Object.entries(expectedSchemaProperties)) {
  const schema = schemas[name];
  if (!schema) fail(`missing schema ${name}`);
  assertEqual(exactKeys(schema.properties), [...expectedProperties].sort(), `${name} properties changed`);
}

for (const [name, schema] of Object.entries(schemas)) {
  if (schema.type === "object" && schema.properties?.schema_version) {
    if (!schema.required?.includes("schema_version")) {
      fail(`${name}.schema_version must be required`);
    }
  }
}

for (const [name, expectedValues] of Object.entries(expectedEnums)) {
  const schema = schemas[name];
  if (!schema) fail(`missing enum schema ${name}`);
  assertEqual([...(schema.enum ?? [])].sort(), expectedValues, `${name} values changed`);
}

for (const [schemaName, propertyName, expectedRef] of [
  ["ArtifactResponse", "created_by", "AgentRole"],
  ["IdentityResponse", "principal", "PrincipalIdentityResponse"],
  ["IdentityResponse", "tenant", "TenantIdentityResponse"],
  ["RunEventResponse", "role", "AgentRole"],
  ["RunEventResponse", "status", "AgentStatus"],
  ["RunResponse", "status", "RunStatus"],
  ["RunStepResponse", "role", "AgentRole"],
  ["RunStepResponse", "status", "AgentStatus"],
]) {
  const actualRef = schemas[schemaName]?.properties?.[propertyName]?.$ref;
  if (actualRef !== `#/components/schemas/${expectedRef}`) {
    fail(`${schemaName}.${propertyName} must reference ${expectedRef}`);
  }
}

for (const [schemaName, fieldNames] of Object.entries(expectedDateTimeFields)) {
  for (const fieldName of fieldNames) {
    const field = schemas[schemaName]?.properties?.[fieldName];
    const formatted = field?.format === "date-time"
      || field?.anyOf?.some((member) => member.format === "date-time");
    if (!formatted) fail(`${schemaName}.${fieldName} must retain date-time format`);
  }
}

const missionSchemaVersion = schemas.MissionCreate.properties.schema_version;
if (missionSchemaVersion.const !== "v1" && !missionSchemaVersion.enum?.includes("v1")) {
  fail("MissionCreate schema_version is no longer v1");
}
const approvalPolicy = schemas.ApprovalCreate.properties.policy_version;
if (approvalPolicy.const !== "greenlight.v1" && !approvalPolicy.enum?.includes("greenlight.v1")) {
  fail("ApprovalCreate policy_version is no longer greenlight.v1");
}
for (const schemaName of ["ApprovalResponse", "RunResponse"]) {
  const policy = schemas[schemaName].properties.policy_version;
  if (policy.const !== "greenlight.v1" && !policy.enum?.includes("greenlight.v1")) {
    fail(`${schemaName}.policy_version is no longer greenlight.v1`);
  }
}
if (schemas.ApprovalCreate.properties.artifact_manifest_hash.pattern !== "^[a-f0-9]{64}$") {
  fail("ApprovalCreate artifact manifest hash pattern changed");
}

process.stdout.write(
  `OpenAPI/frontend contract check passed: ${Object.keys(expectedPaths).length} paths, ${Object.keys(expectedSchemaProperties).length} objects, ${Object.keys(expectedEnums).length} enums.\n`,
);
