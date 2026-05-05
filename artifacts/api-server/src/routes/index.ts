import { Router, type IRouter } from "express";
import healthRouter from "./health.js";
import webhookRouter from "./webhook.js";
import emergencyRouter from "./emergency.js";
import subscribeRouter from "./subscribe.js";
import adminRouter from "./admin.js";

const router: IRouter = Router();

router.use(healthRouter);
router.use(webhookRouter);
router.use(emergencyRouter);
router.use(subscribeRouter);
router.use(adminRouter);

export default router;
