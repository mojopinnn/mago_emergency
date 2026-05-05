import { Router } from "express";
import { saveSubscription, removeSubscription } from "../lib/subscriptionStore.js";
import { updateUserPushToken } from "../lib/shotgrid.js";
import { getVapidPublicKey, type PushSubscription } from "../lib/push.js";

const router = Router();

router.get("/vapid-public-key", (_req, res) => {
  res.json({ key: getVapidPublicKey() });
});

router.post("/subscribe", async (req, res) => {
  const { userId, subscription } = req.body as {
    userId?: number;
    subscription?: PushSubscription;
  };

  if (!userId || !subscription?.endpoint || !subscription?.keys) {
    res.status(400).json({ error: "userId and subscription required" });
    return;
  }

  saveSubscription(userId, subscription);

  try {
    await updateUserPushToken(userId, subscription.endpoint);
  } catch {
    req.log.warn({ userId }, "Could not update ShotGrid push token");
  }

  res.json({ ok: true });
});

router.post("/unsubscribe", (req, res) => {
  const { userId } = req.body as { userId?: number };
  if (!userId) {
    res.status(400).json({ error: "userId required" });
    return;
  }
  removeSubscription(userId);
  res.json({ ok: true });
});

export default router;
