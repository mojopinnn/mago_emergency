import { logger } from "./logger.js";

export type EmergencyStatus =
  | "pending"
  | "acknowledged"
  | "unacknowledged"
  | "responded";

export type ResponseType =
  | "remote_within_10"
  | "remote_within_30"
  | "remote_unavailable";

export interface EmergencyRecord {
  id: string;
  shotId: number;
  shotCode: string;
  projectName: string;
  assigneeIds: number[];
  triggeredByUserId?: number;
  triggeredByName?: string;
  createdAt: number;
  acknowledgedAt?: number;
  respondedAt?: number;
  status: EmergencyStatus;
  responseType?: ResponseType;
  reminderCount: number;
  lastReminderAt?: number;
  notifiedUnacknowledged: boolean;
}

const store = new Map<string, EmergencyRecord>();

export function createEmergency(params: {
  shotId: number;
  shotCode: string;
  projectName: string;
  assigneeIds: number[];
  triggeredByUserId?: number;
  triggeredByName?: string;
}): EmergencyRecord {
  const id = `emg_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
  const record: EmergencyRecord = {
    id,
    shotId: params.shotId,
    shotCode: params.shotCode,
    projectName: params.projectName,
    assigneeIds: params.assigneeIds,
    triggeredByUserId: params.triggeredByUserId,
    triggeredByName: params.triggeredByName,
    createdAt: Date.now(),
    status: "pending",
    reminderCount: 0,
    notifiedUnacknowledged: false,
  };
  store.set(id, record);
  logger.info({ emergencyId: id, shotCode: params.shotCode }, "Emergency created");
  return record;
}

export function getEmergency(id: string): EmergencyRecord | undefined {
  return store.get(id);
}

export function getAllEmergencies(): EmergencyRecord[] {
  return Array.from(store.values()).sort((a, b) => b.createdAt - a.createdAt);
}

export function getActiveEmergencies(): EmergencyRecord[] {
  return getAllEmergencies().filter(
    (e) => e.status === "pending" || e.status === "acknowledged",
  );
}

export function acknowledgeEmergency(id: string): EmergencyRecord | null {
  const record = store.get(id);
  if (!record) return null;
  if (record.status !== "pending") return record;

  record.acknowledgedAt = Date.now();
  record.status = "acknowledged";
  store.set(id, record);
  logger.info({ emergencyId: id }, "Emergency acknowledged");
  return record;
}

export function respondToEmergency(
  id: string,
  responseType: ResponseType,
): EmergencyRecord | null {
  const record = store.get(id);
  if (!record) return null;

  record.respondedAt = Date.now();
  record.responseType = responseType;
  record.status = "responded";
  store.set(id, record);
  logger.info({ emergencyId: id, responseType }, "Emergency responded");
  return record;
}

export function markUnacknowledged(id: string): EmergencyRecord | null {
  const record = store.get(id);
  if (!record) return null;

  record.status = "unacknowledged";
  record.notifiedUnacknowledged = true;
  store.set(id, record);
  logger.warn({ emergencyId: id }, "Emergency marked as unacknowledged");
  return record;
}

export function incrementReminder(id: string): EmergencyRecord | null {
  const record = store.get(id);
  if (!record) return null;

  record.reminderCount += 1;
  record.lastReminderAt = Date.now();
  store.set(id, record);
  return record;
}

export function needsReminder(record: EmergencyRecord): boolean {
  if (record.status !== "pending") return false;
  const now = Date.now();
  const TWO_MINUTES = 2 * 60 * 1000;
  const lastTime = record.lastReminderAt ?? record.createdAt;
  return now - lastTime >= TWO_MINUTES;
}

export function needsUnacknowledgedAlert(record: EmergencyRecord): boolean {
  if (record.status !== "pending") return false;
  if (record.notifiedUnacknowledged) return false;
  const FIVE_MINUTES = 5 * 60 * 1000;
  return Date.now() - record.createdAt >= FIVE_MINUTES;
}
