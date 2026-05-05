import express, { type Express } from "express";
import cors from "cors";
import pinoHttp from "pino-http";
import path from "path";
import { fileURLToPath } from "url";
import router from "./routes/index.js";
import { logger } from "./lib/logger.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const app: Express = express();

app.use(
  pinoHttp({
    logger,
    serializers: {
      req(req) {
        return {
          id: req.id,
          method: req.method,
          url: req.url?.split("?")[0],
        };
      },
      res(res) {
        return {
          statusCode: res.statusCode,
        };
      },
    },
  }),
);
app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

const publicDir = path.join(__dirname, "..", "public");

// sw.js needs Service-Worker-Allowed header so scope /api/ is permitted
// (script is at /api/static/sw.js which is narrower than /api/ scope)
app.get("/api/static/sw.js", (_req, res) => {
  res.setHeader("Service-Worker-Allowed", "/api/");
  res.setHeader("Content-Type", "application/javascript");
  res.sendFile(path.join(publicDir, "sw.js"));
});

app.use("/api/static", express.static(publicDir));

app.get("/api/app", (_req, res) => {
  res.sendFile(path.join(publicDir, "app.html"));
});

app.use("/api", router);

export default app;
