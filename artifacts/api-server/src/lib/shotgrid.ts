import { logger } from "./logger.js";

const SHOTGRID_URL = process.env.SHOTGRID_URL ?? "";
const SHOTGRID_SCRIPT_NAME = process.env.SHOTGRID_SCRIPT_NAME ?? "";
const SHOTGRID_API_KEY = process.env.SHOTGRID_API_KEY ?? "";

interface ShotGridSession {
  token: string;
  expiresAt: number;
}

let session: ShotGridSession | null = null;

async function authenticate(): Promise<string> {
  if (session && Date.now() < session.expiresAt) {
    return session.token;
  }

  const res = await fetch(`${SHOTGRID_URL}/api/v1/auth/access_token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "client_credentials",
      client_id: SHOTGRID_SCRIPT_NAME,
      client_secret: SHOTGRID_API_KEY,
    }),
  });

  if (!res.ok) {
    const text = await res.text();
    logger.error({ status: res.status, body: text }, "ShotGrid auth failed");
    throw new Error(`ShotGrid auth failed: ${res.status}`);
  }

  const data = (await res.json()) as { access_token: string; expires_in: number };
  session = {
    token: data.access_token,
    expiresAt: Date.now() + (data.expires_in - 60) * 1000,
  };
  return session.token;
}

async function sgFetch(path: string, options: RequestInit = {}): Promise<unknown> {
  const token = await authenticate();
  const res = await fetch(`${SHOTGRID_URL}/api/v1${path}`, {
    ...options,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      Accept: "application/json",
      ...(options.headers ?? {}),
    },
  });

  if (!res.ok) {
    const text = await res.text();
    logger.error({ status: res.status, path, body: text }, "ShotGrid API error");
    throw new Error(`ShotGrid API error ${res.status}: ${path}`);
  }

  return res.json();
}

async function sgSearch(
  entityType: string,
  filters: unknown[],
  fields: string[],
  pageSize = 100,
): Promise<unknown[]> {
  const token = await authenticate();
  const body = {
    filters: {
      logical_operator: "and",
      conditions: filters,
    },
    fields,
    page: { size: pageSize },
  };

  const res = await fetch(`${SHOTGRID_URL}/api/v1/entity/${entityType}/_search`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/vnd+shotgun.api3_hash+json",
      Accept: "application/json",
    },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const text = await res.text();
    logger.error({ status: res.status, entityType, body: text }, "ShotGrid search error");
    throw new Error(`ShotGrid search error ${res.status}: ${entityType}`);
  }

  const data = (await res.json()) as { data: SGRawEntity[] };
  return (data.data ?? []).map((r) => parseAttrs(r));
}

interface SGRelEntity {
  id: number;
  type: string;
  name?: string;
}

interface SGRawEntity {
  id: number | string;
  type: string;
  attributes?: Record<string, unknown>;
  relationships?: Record<string, { data?: SGRelEntity | SGRelEntity[] }>;
}

function parseAttrs(raw: SGRawEntity): Record<string, unknown> {
  const relationships: Record<string, unknown> = {};
  if (raw.relationships) {
    for (const [key, rel] of Object.entries(raw.relationships)) {
      if (rel?.data !== undefined) {
        relationships[key] = rel.data;
      }
    }
  }
  return {
    id: typeof raw.id === "string" ? parseInt(raw.id) : raw.id,
    type: raw.type,
    ...(raw.attributes ?? {}),
    ...relationships,
  };
}

export interface SGUser {
  id: number;
  name: string;
  email: string;
  login: string;
  sg_role: string | null;
  sg_push_token: string | null;
}

export interface SGShot {
  id: number;
  code: string;
  project: { id: number; name: string } | null;
}

export interface SGTask {
  id: number;
  content: string;
  entity: { id: number; type: string; name: string };
  project: { id: number; name: string };
  assignees: { id: number; name: string }[];
}

export async function getUserById(userId: number): Promise<SGUser | null> {
  try {
    const data = (await sgFetch(
      `/entity/HumanUser/${userId}?fields=name,email,login,sg_role,sg_push_token`,
    )) as { data: SGRawEntity };
    const attrs = parseAttrs(data.data);
    return attrs as unknown as SGUser;
  } catch {
    return null;
  }
}

export async function getAllActiveUsers(): Promise<SGUser[]> {
  try {
    const results = await sgSearch(
      "HumanUser",
      [["sg_status_list", "is", "act"]],
      ["name", "email", "login"],
      200,
    );
    return results as unknown as SGUser[];
  } catch (err) {
    logger.error({ err }, "Failed to get all active users");
    return [];
  }
}

export async function getShotById(shotId: number): Promise<SGShot | null> {
  try {
    const data = (await sgFetch(
      `/entity/Shot/${shotId}?fields=code,project`,
    )) as { data: SGRawEntity };
    const raw = data.data;
    const attrs = raw.attributes ?? {};
    const projectRel = raw.relationships?.project?.data ?? null;

    let project: { id: number; name: string } | null = null;
    if (projectRel) {
      project = { id: projectRel.id, name: projectRel.name ?? `Project ${projectRel.id}` };
    }

    return {
      id: typeof raw.id === "string" ? parseInt(raw.id) : (raw.id as number),
      code: attrs.code as string,
      project,
    };
  } catch {
    return null;
  }
}

export async function getTasksForShot(shotId: number): Promise<SGTask[]> {
  try {
    const results = await sgSearch(
      "Task",
      [["entity", "is", { type: "Shot", id: shotId }]],
      ["content", "entity", "task_assignees", "project"],
      50,
    );
    return results.map((r) => {
      const attrs = r as Record<string, unknown>;
      return {
        id: attrs.id as number,
        content: attrs.content as string,
        entity: attrs.entity as SGTask["entity"],
        project: (attrs.project as SGTask["project"]) ?? { id: 0, name: "Unknown Project" },
        assignees: ((attrs.task_assignees ?? []) as Array<{ id: number; name: string }>),
      };
    });
  } catch (err) {
    logger.error({ err, shotId }, "Failed to get tasks for shot");
    return [];
  }
}

export async function getTaskById(taskId: number): Promise<SGTask | null> {
  try {
    const data = (await sgFetch(
      `/entity/Task/${taskId}?fields=content,entity,project,task_assignees`,
    )) as { data: SGRawEntity };
    const raw = data.data;
    const attrs = raw.attributes ?? {};
    const projectRel = raw.relationships?.project?.data ?? null;
    const entityRel = raw.relationships?.entity?.data ?? null;

    // task_assignees is a multi-entity relationship — comes back as array in relationships
    const taskAssigneesRel = raw.relationships?.task_assignees?.data;
    const assignees: Array<{ id: number; name: string }> = Array.isArray(taskAssigneesRel)
      ? taskAssigneesRel.map((a) => ({ id: a.id, name: a.name ?? "" }))
      : [];

    logger.info({ taskId, rawAttrs: attrs, rawRels: raw.relationships, assignees }, "Task raw data");

    return {
      id: typeof raw.id === "string" ? parseInt(raw.id) : (raw.id as number),
      content: attrs.content as string,
      entity: entityRel as SGTask["entity"],
      project: projectRel
        ? { id: projectRel.id, name: projectRel.name ?? `Project ${projectRel.id}` }
        : { id: 0, name: "Unknown Project" },
      assignees,
    };
  } catch (err) {
    logger.error({ err, taskId }, "Failed to get task by id");
    return null;
  }
}

export async function setupShotGridFields(): Promise<Record<string, string>> {
  const results: Record<string, string> = {};
  const fields = [
    { entity: "HumanUser", name: "sg_role", type: "text", label: "MAGO Role" },
    { entity: "HumanUser", name: "sg_push_token", type: "text", label: "MAGO Push Token" },
  ];

  for (const f of fields) {
    try {
      // Check if field exists first
      const schema = (await sgFetch(`/schema/${f.entity}/fields`)) as { data: Record<string, unknown> };
      if (schema.data && f.name in schema.data) {
        results[f.name] = "already_exists";
        continue;
      }
      // Create field
      await sgFetch(`/schema/${f.entity}/fields`, {
        method: "POST",
        body: JSON.stringify({
          data_type: f.type,
          properties: [{ property_name: "name", value: f.label }],
        }),
      });
      results[f.name] = "created";
    } catch (err) {
      results[f.name] = `error: ${String(err)}`;
      logger.error({ err, field: f.name }, "Failed to create ShotGrid field");
    }
  }
  return results;
}

export async function getProjectById(projectId: number): Promise<{ id: number; name: string } | null> {
  try {
    const data = (await sgFetch(
      `/entity/Project/${projectId}?fields=name`,
    )) as { data: SGRawEntity };
    const attrs = parseAttrs(data.data);
    return { id: attrs.id as number, name: attrs.name as string };
  } catch {
    return null;
  }
}

export async function updateUserPushToken(userId: number, token: string): Promise<void> {
  await sgFetch(`/entity/HumanUser/${userId}`, {
    method: "PUT",
    body: JSON.stringify({ sg_push_token: token }),
  });
}
