import {
  getActiveEmergencies,
  needsReminder,
  needsUnacknowledgedAlert,
  incrementReminder,
  markUnacknowledged,
} from "./emergencyStore.js";
import { sendPushNotification, type PushPayload } from "./push.js";
import { getSubscription } from "./subscriptionStore.js";
import { logger } from "./logger.js";

async function tick(): Promise<void> {
  const actives = getActiveEmergencies();

  for (const emergency of actives) {
    if (needsUnacknowledgedAlert(emergency)) {
      logger.warn({ emergencyId: emergency.id }, "Emergency unacknowledged for 5 minutes");
      markUnacknowledged(emergency.id);

      // Re-notify all assignees with escalation message
      const payload: PushPayload = {
        title: "⚠️ 긴급 알림 미확인 (5분 경과)",
        body: `[${emergency.projectName}] ${emergency.shotCode} - 5분이 지났습니다. 즉시 확인해주세요!`,
        emergencyId: emergency.id,
        shotCode: emergency.shotCode,
        projectName: emergency.projectName,
        type: "unacknowledged",
        tag: `unack-${emergency.id}`,
      };

      for (const userId of emergency.assigneeIds) {
        const sub = getSubscription(userId);
        if (sub) await sendPushNotification(sub, payload);
      }

      continue;
    }

    if (needsReminder(emergency)) {
      logger.info({ emergencyId: emergency.id, count: emergency.reminderCount + 1 }, "Sending reminder");
      incrementReminder(emergency.id);

      const payload: PushPayload = {
        title: `🔔 긴급 알림 재전송 (${emergency.reminderCount + 1}회)`,
        body: `[${emergency.projectName}] ${emergency.shotCode} - 아직 확인하지 않으셨습니다. 즉시 확인해주세요!`,
        emergencyId: emergency.id,
        shotCode: emergency.shotCode,
        projectName: emergency.projectName,
        type: "reminder",
        tag: `reminder-${emergency.id}`,
      };

      for (const userId of emergency.assigneeIds) {
        const sub = getSubscription(userId);
        if (sub) {
          const success = await sendPushNotification(sub, payload);
          if (!success) {
            logger.warn({ userId }, "Reminder push failed");
          }
        }
      }
    }
  }
}

export function startScheduler(): void {
  logger.info("Emergency scheduler started (30s interval)");
  setInterval(() => {
    tick().catch((err) => logger.error({ err }, "Scheduler tick error"));
  }, 30 * 1000);
}
