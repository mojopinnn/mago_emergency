import webpush from "web-push";
import { logger } from "./logger.js";

const VAPID_PUBLIC_KEY = process.env.VAPID_PUBLIC_KEY ?? "";
const VAPID_PRIVATE_KEY = process.env.VAPID_PRIVATE_KEY ?? "";
const VAPID_EMAIL = process.env.VAPID_EMAIL ?? "mailto:admin@example.com";

if (VAPID_PUBLIC_KEY && VAPID_PRIVATE_KEY) {
  webpush.setVapidDetails(VAPID_EMAIL, VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY);
}

export interface PushSubscription {
  endpoint: string;
  keys: {
    p256dh: string;
    auth: string;
  };
}

export interface PushPayload {
  title: string;
  body: string;
  emergencyId: string;
  shotCode: string;
  projectName: string;
  type: "emergency" | "reminder" | "status_update" | "unacknowledged";
  tag?: string;
}

export async function sendPushNotification(
  subscription: PushSubscription,
  payload: PushPayload,
): Promise<boolean> {
  try {
    await webpush.sendNotification(subscription, JSON.stringify(payload), {
      urgency: "high",
      TTL: 300,
    });
    return true;
  } catch (err: unknown) {
    const error = err as { statusCode?: number; message?: string };
    if (error.statusCode === 410 || error.statusCode === 404) {
      logger.warn({ endpoint: subscription.endpoint }, "Push subscription expired");
      return false;
    }
    logger.error({ err, endpoint: subscription.endpoint }, "Failed to send push notification");
    return false;
  }
}

export function getVapidPublicKey(): string {
  return VAPID_PUBLIC_KEY;
}
