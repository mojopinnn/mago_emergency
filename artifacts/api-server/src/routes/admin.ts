import { Router, type Request } from "express";
import { getAllActiveUsers, setupShotGridFields } from "../lib/shotgrid.js";
import { logger } from "../lib/logger.js";

const router = Router();

router.get("/admin/links", async (req: Request, res) => {
  const baseUrl =
    process.env.BASE_URL ??
    `${req.protocol}://${req.get("host")}`;

  try {
    const users = await getAllActiveUsers();
    users.sort((a, b) => a.name.localeCompare(b.name, "ko"));

    const rows = users
      .map((u) => {
        const link = `${baseUrl}/api/app?userId=${u.id}&userName=${encodeURIComponent(u.name)}`;
        return `
        <tr>
          <td>${u.name}</td>
          <td>
            <input readonly value="${link}" onclick="this.select()"
              style="width:100%;background:#1a1a2e;border:1px solid #2a2a4a;
                     color:#e8e8f0;padding:6px 10px;border-radius:6px;font-size:12px;" />
          </td>
          <td>
            <button onclick="navigator.clipboard.writeText('${link}')
                      .then(()=>this.textContent='✅ 복사됨')
                      .catch(()=>this.textContent='❌')"
              style="background:#ff4444;color:#fff;border:none;padding:6px 14px;
                     border-radius:6px;cursor:pointer;font-size:12px;">
              복사
            </button>
          </td>
        </tr>`;
      })
      .join("");

    res.send(`<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1.0"/>
  <title>MAGO 직원 링크 관리</title>
  <style>
    body { background:#0f0f1a; color:#e8e8f0; font-family:sans-serif; padding:24px; }
    h1 { color:#ff4444; margin-bottom:8px; font-size:20px; }
    p { color:#9999bb; font-size:13px; margin-bottom:20px; }
    table { width:100%; border-collapse:collapse; }
    th { background:#1a1a2e; padding:10px 12px; text-align:left; font-size:13px; color:#9999bb; border-bottom:1px solid #2a2a4a; }
    td { padding:10px 12px; border-bottom:1px solid #2a2a4a; font-size:13px; vertical-align:middle; }
    tr:hover td { background:#1a1a2e; }
    .ami-info { background:#1a1a2e; border:1px solid #2a2a4a; border-radius:8px; padding:16px; margin-bottom:20px; }
    .ami-info h2 { font-size:14px; color:#ffa500; margin-bottom:8px; }
    .ami-info code { background:#0f0f1a; padding:4px 8px; border-radius:4px; font-size:12px; color:#00d4aa; }
  </style>
</head>
<body>
  <h1>🔗 직원 개인 링크</h1>
  <div class="ami-info">
    <h2>⚙️ ShotGrid AMI 웹훅 주소</h2>
    <p style="margin:0">Task 또는 Shot에 우클릭 → mago_emergency 액션 메뉴 등록 시 사용하세요:</p>
    <br/>
    <code>${baseUrl}/api/sg_webhook</code>
  </div>
  <p>각 직원에게 아래 링크를 카카오톡으로 보내주세요.<br>
     링크 접속 후 <strong>알림 활성화</strong> 버튼 한 번만 누르면 이후 자동으로 긴급 알림이 수신됩니다.</p>
  <table>
    <thead>
      <tr><th>이름</th><th>개인 링크</th><th></th></tr>
    </thead>
    <tbody>${rows || '<tr><td colspan="3" style="text-align:center;color:#9999bb;padding:40px">ShotGrid 활성 사용자가 없습니다.</td></tr>'}</tbody>
  </table>
</body>
</html>`);
  } catch (err) {
    logger.error({ err }, "Failed to generate admin links");
    res.status(500).send("ShotGrid 연결 오류: " + String(err));
  }
});

router.get("/users", async (_req, res) => {
  try {
    const users = await getAllActiveUsers();
    users.sort((a, b) => a.name.localeCompare(b.name, "ko"));
    res.json({ data: users.map((u) => ({ id: u.id, name: u.name })) });
  } catch (err) {
    logger.error({ err }, "Failed to list users");
    res.status(500).json({ error: String(err) });
  }
});

router.post("/admin/setup-sg-fields", async (_req, res) => {
  try {
    const results = await setupShotGridFields();
    res.json({ ok: true, results });
  } catch (err) {
    logger.error({ err }, "Failed to setup ShotGrid fields");
    res.status(500).json({ error: String(err) });
  }
});

export default router;
