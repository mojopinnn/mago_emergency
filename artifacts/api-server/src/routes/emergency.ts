import { Router } from "express";
import {
  getEmergency,
  getAllEmergencies,
  acknowledgeEmergency,
  respondToEmergency,
  type ResponseType,
} from "../lib/emergencyStore.js";
import { getUserById } from "../lib/shotgrid.js";
import { sendPushNotification, type PushPayload } from "../lib/push.js";
import { getSubscription } from "../lib/subscriptionStore.js";

const router = Router();

router.get("/emergency", (_req, res) => {
  const emergencies = getAllEmergencies().slice(0, 50);
  res.json({ data: emergencies });
});

router.get("/emergency/:id", (req, res) => {
  const emergency = getEmergency(req.params.id);
  if (!emergency) {
    res.status(404).json({ error: "Emergency not found" });
    return;
  }
  res.json({ data: emergency });
});

router.post("/emergency/:id/acknowledge", async (req, res) => {
  const { userId } = req.body as { userId?: number };
  const emergency = acknowledgeEmergency(req.params.id);

  if (!emergency) {
    res.status(404).json({ error: "Emergency not found or already processed" });
    return;
  }

  let acknowledgerName = "작업자";
  if (userId) {
    const user = await getUserById(userId);
    if (user) acknowledgerName = user.name;
  }

  // Notify other assignees that someone acknowledged
  const notifyPayload: PushPayload = {
    title: "✅ 긴급 알림 확인됨",
    body: `[${emergency.projectName}] ${emergency.shotCode} - ${acknowledgerName}님이 확인했습니다.`,
    emergencyId: emergency.id,
    shotCode: emergency.shotCode,
    projectName: emergency.projectName,
    type: "status_update",
    tag: `ack-${emergency.id}`,
  };

  // Notify other assignees
  for (const assigneeId of emergency.assigneeIds) {
    if (assigneeId === userId) continue;
    const sub = getSubscription(assigneeId);
    if (sub) await sendPushNotification(sub, notifyPayload);
  }

  // Notify the PM who triggered it (if different from acknowledger)
  if (emergency.triggeredByUserId && emergency.triggeredByUserId !== userId) {
    const pmSub = getSubscription(emergency.triggeredByUserId);
    if (pmSub) await sendPushNotification(pmSub, notifyPayload);
  }

  res.json({ ok: true, data: emergency });
});

const RESPONSE_LABELS: Record<ResponseType, string> = {
  remote_within_10: "10분 이내 원격 접속 가능",
  remote_within_30: "30분 이내 원격 접속 가능",
  remote_unavailable: "30분 이내 원격 접속 불가",
};

router.post("/emergency/:id/respond", async (req, res) => {
  const { responseType, userId } = req.body as {
    responseType?: ResponseType;
    userId?: number;
  };

  if (!responseType || !["remote_within_10", "remote_within_30", "remote_unavailable"].includes(responseType)) {
    res.status(400).json({ error: "Invalid responseType" });
    return;
  }

  const emergency = respondToEmergency(req.params.id, responseType);
  if (!emergency) {
    res.status(404).json({ error: "Emergency not found" });
    return;
  }

  let responderName = "작업자";
  if (userId) {
    const user = await getUserById(userId);
    if (user) responderName = user.name;
  }

  const label = RESPONSE_LABELS[responseType];

  const notifyPayload: PushPayload = {
    title: "📋 작업자 응답 도착",
    body: `[${emergency.projectName}] ${emergency.shotCode} - ${responderName}: ${label}`,
    emergencyId: emergency.id,
    shotCode: emergency.shotCode,
    projectName: emergency.projectName,
    type: "status_update",
    tag: `respond-${emergency.id}`,
  };

  // Notify other assignees
  for (const assigneeId of emergency.assigneeIds) {
    if (assigneeId === userId) continue;
    const sub = getSubscription(assigneeId);
    if (sub) await sendPushNotification(sub, notifyPayload);
  }

  // Notify the PM who triggered it (if different from responder)
  if (emergency.triggeredByUserId && emergency.triggeredByUserId !== userId) {
    const pmSub = getSubscription(emergency.triggeredByUserId);
    if (pmSub) await sendPushNotification(pmSub, notifyPayload);
  }

  res.json({ ok: true, data: emergency, label });
});

export default router;
