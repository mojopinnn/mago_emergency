import { Router } from "express";
import {
  createEmergency,
  incrementReminder,
} from "../lib/emergencyStore.js";
import {
  getShotById,
  getTaskById,
  getTasksForShot,
} from "../lib/shotgrid.js";
import { sendPushNotification, type PushPayload } from "../lib/push.js";
import { getSubscription } from "../lib/subscriptionStore.js";
import { logger } from "../lib/logger.js";

const router = Router();

/**
 * ShotGrid AMI 웹훅 (multipart/form-data 또는 urlencoded)
 * AMI 필드: selected_ids, entity_type, user_name
 *
 * ShotGrid Automation 웹훅 (JSON) 도 동시 지원:
 * { entity: { id, type }, project, user }
 */
router.post("/sg_webhook", async (req, res) => {
  let entityId: number | undefined;
  let entityType: string | undefined;
  let pmName = "PM";
  let pmUserId: number | undefined;

  const ct = req.headers["content-type"] ?? "";

  if (ct.includes("application/json") && req.body?.entity) {
    entityId = req.body.entity?.id;
    entityType = req.body.entity?.type;
    pmName = req.body.user?.name ?? "PM";
    pmUserId = req.body.user?.id ? parseInt(req.body.user.id) : undefined;
  } else {
    const selectedIds: string = req.body?.selected_ids ?? "";
    entityType = req.body?.entity_type ?? "Task";
    pmName = req.body?.user_name ?? "PM";
    pmUserId = req.body?.user_id ? parseInt(req.body.user_id) : undefined;
    const firstId = selectedIds.split(",")[0]?.trim();
    entityId = firstId ? parseInt(firstId) : undefined;
  }

  if (!entityId || !entityType) {
    res.status(400).json({ error: "entity id/type required" });
    return;
  }

  req.log.info({ entityId, entityType, pmName }, "AMI webhook received");

  try {
    let shotCode: string;
    let projectName: string;
    let assigneeIds: number[];

    if (entityType === "Task") {
      const task = await getTaskById(entityId);
      if (!task) {
        res.status(404).json({ error: `Task ${entityId} not found` });
        return;
      }
      shotCode = task.entity?.name ?? task.content;
      projectName = task.project?.name ?? "Unknown Project";
      assigneeIds = task.assignees.map((a) => a.id);
    } else {
      const shot = await getShotById(entityId);
      if (!shot) {
        res.status(404).json({ error: `Shot ${entityId} not found` });
        return;
      }
      shotCode = shot.code;
      projectName = shot.project?.name ?? "Unknown Project";
      const tasks = await getTasksForShot(entityId);
      const seen = new Set<number>();
      assigneeIds = [];
      for (const t of tasks) {
        for (const a of t.assignees) {
          if (!seen.has(a.id)) { seen.add(a.id); assigneeIds.push(a.id); }
        }
      }
    }

    req.log.info({ shotCode, projectName, assigneeIds }, "Emergency triggered");

    const emergency = createEmergency({
      shotId: entityId,
      shotCode,
      projectName,
      assigneeIds,
      triggeredByUserId: pmUserId,
      triggeredByName: pmName,
    });

    const artistPayload: PushPayload = {
      title: "🚨 긴급 수정 요청",
      body: `[${projectName}] ${shotCode} 긴급 수정 발생! 즉시 확인해주세요.`,
      emergencyId: emergency.id,
      shotCode,
      projectName,
      type: "emergency",
      tag: `emergency-${emergency.id}`,
    };

    let sentCount = 0;
    for (const userId of assigneeIds) {
      const sub = getSubscription(userId);
      if (sub) {
        await sendPushNotification(sub, artistPayload);
        sentCount++;
      } else {
        logger.warn({ userId }, "No push subscription for assignee");
      }
    }

    incrementReminder(emergency.id);

    res.json({
      ok: true,
      emergencyId: emergency.id,
      shotCode,
      projectName,
      assigneeCount: assigneeIds.length,
      sentCount,
    });
  } catch (err) {
    req.log.error({ err }, "Emergency webhook processing failed");
    res.status(500).json({ error: "Internal server error" });
  }
});

export default router;
