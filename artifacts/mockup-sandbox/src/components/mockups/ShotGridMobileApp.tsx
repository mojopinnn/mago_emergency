import { useState } from "react";

type NavKey = "today" | "actions" | "jobs" | "notes";

const shots = [
  {
    code: "EP104_SQ030_SH020",
    project: "DRAGON CAVE",
    task: "Comp",
    status: "rev",
    due: "오늘 18:00",
    artist: "김민준",
    frames: "1001-1088",
    version: "v014",
  },
  {
    code: "EP104_SQ030_SH040",
    project: "DRAGON CAVE",
    task: "Lighting",
    status: "ip",
    due: "내일",
    artist: "이서연",
    frames: "1001-1120",
    version: "v007",
  },
  {
    code: "CF22_PACK_SH010",
    project: "MAGO BRAND",
    task: "Transcode",
    status: "rdy",
    due: "대기",
    artist: "박도윤",
    frames: "1001-1036",
    version: "v003",
  },
];

const actions = [
  {
    title: "Nuke Transcode",
    description: "선택한 Version을 EXR/MOV로 변환",
    target: "Version",
    state: "외부 실행 가능",
  },
  {
    title: "Emergency Fix",
    description: "담당자에게 긴급 수정 푸시 발송",
    target: "Task / Shot",
    state: "푸시 준비",
  },
  {
    title: "Preview Render",
    description: "사내 Worker가 저해상도 프리뷰 생성",
    target: "Shot",
    state: "내부 렌더",
  },
];

const jobs = [
  {
    name: "EP104_SQ030_SH020 transcode",
    status: "running",
    progress: "68%",
    detail: "Nuke 렌더 중 - frame 1058 / 1088",
  },
  {
    name: "CF22_PACK_SH010 preview",
    status: "done",
    progress: "완료",
    detail: "프리뷰 업로드 완료",
  },
  {
    name: "EP104_SQ020_SH090 emergency",
    status: "waiting",
    progress: "대기",
    detail: "아티스트 응답 대기 중",
  },
];

const notes = [
  {
    author: "Supervisor",
    target: "EP104_SQ030_SH020",
    body: "Edge matte 확인 후 v015로 재업로드 필요. 프리뷰 렌더 먼저 확인해주세요.",
    time: "12분 전",
  },
  {
    author: "PM",
    target: "CF22_PACK_SH010",
    body: "클라이언트 확인용 MOV만 먼저 전달하면 됩니다.",
    time: "34분 전",
  },
];

const bottomNavItems: Array<{ key: NavKey; label: string }> = [
  { key: "today", label: "오늘" },
  { key: "actions", label: "AMI" },
  { key: "jobs", label: "작업" },
  { key: "notes", label: "노트" },
];

function statusClass(status: string): string {
  if (status === "rev") {
    return "border-amber-400/30 bg-amber-400/10 text-amber-200";
  }
  if (status === "ip" || status === "running") {
    return "border-blue-400/30 bg-blue-400/10 text-blue-200";
  }
  if (status === "done" || status === "rdy") {
    return "border-emerald-400/30 bg-emerald-400/10 text-emerald-200";
  }
  return "border-slate-400/30 bg-slate-400/10 text-slate-200";
}

function navClass(active: boolean): string {
  return active
    ? "bg-white text-slate-950 shadow-[0_10px_28px_rgba(255,255,255,0.24)]"
    : "text-slate-400";
}

export default function ShotGridMobileApp() {
  const [activeNav, setActiveNav] = useState<NavKey>("today");

  return (
    <div className="min-h-screen bg-[#070b12] px-4 py-6 text-slate-100">
      <div className="relative mx-auto w-full max-w-[430px] overflow-hidden rounded-[34px] border border-white/10 bg-[#0b1019] shadow-2xl shadow-black/60">
        <div className="flex items-center justify-between border-b border-white/10 bg-white/[0.03] px-5 py-3 text-[11px] text-slate-400">
          <span>9:41</span>
          <span>ShotGrid Lite</span>
          <span>5G</span>
        </div>

        <main className="max-h-[860px] overflow-y-auto px-5 pb-36 pt-5">
          <section className="rounded-[28px] border border-white/10 bg-gradient-to-br from-slate-900 via-slate-900 to-blue-950 p-5">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.24em] text-blue-200">
                  MAGO Gateway
                </p>
                <h1 className="mt-2 text-3xl font-black tracking-tight text-white">
                  ShotGrid
                  <br />
                  Mobile Hub
                </h1>
              </div>
              <div className="rounded-2xl border border-emerald-400/25 bg-emerald-400/10 px-3 py-2 text-right">
                <p className="text-[10px] text-emerald-200">Worker</p>
                <p className="text-sm font-bold text-emerald-100">ONLINE</p>
              </div>
            </div>

            <div className="mt-5 grid grid-cols-3 gap-2">
              <div className="rounded-2xl bg-white/8 p-3">
                <p className="text-[10px] text-slate-400">내 작업</p>
                <p className="mt-1 text-xl font-black">12</p>
              </div>
              <div className="rounded-2xl bg-white/8 p-3">
                <p className="text-[10px] text-slate-400">렌더</p>
                <p className="mt-1 text-xl font-black text-blue-200">3</p>
              </div>
              <div className="rounded-2xl bg-white/8 p-3">
                <p className="text-[10px] text-slate-400">긴급</p>
                <p className="mt-1 text-xl font-black text-rose-200">1</p>
              </div>
            </div>
          </section>

          <section className="mt-5">
            <div className="flex items-center gap-2 rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3">
              <span className="text-slate-500">Search</span>
              <span className="text-sm text-slate-500">
                shot, version, task, action
              </span>
            </div>
          </section>

          {activeNav === "today" && (
            <section className="mt-6">
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-sm font-black uppercase tracking-[0.18em] text-slate-400">
                  오늘 작업
                </h2>
                <button className="text-xs font-bold text-blue-200">
                  전체 보기
                </button>
              </div>

              <div className="space-y-3">
                <div className="rounded-3xl border border-rose-400/20 bg-rose-400/10 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-xs font-bold text-rose-200">
                        긴급 수정 요청
                      </p>
                      <h3 className="mt-1 font-black text-white">
                        EP104_SQ030_SH020
                      </h3>
                    </div>
                    <button className="rounded-full bg-rose-400 px-4 py-2 text-xs font-black text-white">
                      확인
                    </button>
                  </div>
                  <p className="mt-3 text-xs leading-5 text-rose-100/80">
                    PM이 ShotGrid AMI에서 Emergency Fix를 실행했습니다.
                    담당자에게 푸시가 발송되었습니다.
                  </p>
                </div>

                {shots.map((shot) => (
                  <article
                    className="rounded-3xl border border-white/10 bg-white/[0.04] p-4"
                    key={shot.code}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-[11px] font-semibold text-slate-500">
                          {shot.project} / {shot.task}
                        </p>
                        <h3 className="mt-1 text-base font-black text-white">
                          {shot.code}
                        </h3>
                      </div>
                      <span
                        className={`rounded-full border px-2.5 py-1 text-[10px] font-black uppercase ${statusClass(
                          shot.status,
                        )}`}
                      >
                        {shot.status}
                      </span>
                    </div>
                    <div className="mt-4 grid grid-cols-3 gap-2 text-xs">
                      <div>
                        <p className="text-slate-500">Version</p>
                        <p className="mt-1 font-bold">{shot.version}</p>
                      </div>
                      <div>
                        <p className="text-slate-500">Frames</p>
                        <p className="mt-1 font-bold">{shot.frames}</p>
                      </div>
                      <div>
                        <p className="text-slate-500">Due</p>
                        <p className="mt-1 font-bold">{shot.due}</p>
                      </div>
                    </div>
                  </article>
                ))}
              </div>
            </section>
          )}

          {activeNav === "actions" && (
            <section className="mt-6">
              <h2 className="mb-3 text-sm font-black uppercase tracking-[0.18em] text-slate-400">
                AMI 액션
              </h2>
              <div className="space-y-3">
                {actions.map((action) => (
                  <article
                    className="rounded-3xl border border-white/10 bg-white/[0.04] p-4"
                    key={action.title}
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <p className="text-[11px] font-semibold text-blue-200">
                          {action.target}
                        </p>
                        <h3 className="mt-1 text-lg font-black text-white">
                          {action.title}
                        </h3>
                      </div>
                      <span className="rounded-full border border-emerald-400/25 bg-emerald-400/10 px-2.5 py-1 text-[10px] font-black text-emerald-200">
                        {action.state}
                      </span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-slate-400">
                      {action.description}
                    </p>
                    <button className="mt-4 w-full rounded-2xl bg-white px-4 py-3 text-sm font-black text-slate-950">
                      모바일에서 실행
                    </button>
                  </article>
                ))}
              </div>
            </section>
          )}

          {activeNav === "jobs" && (
            <section className="mt-6">
              <h2 className="mb-3 text-sm font-black uppercase tracking-[0.18em] text-slate-400">
                작업 상태
              </h2>
              <div className="space-y-3">
                {jobs.map((job) => (
                  <article
                    className="rounded-3xl border border-white/10 bg-white/[0.04] p-4"
                    key={job.name}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <h3 className="font-black text-white">{job.name}</h3>
                      <span
                        className={`rounded-full border px-2.5 py-1 text-[10px] font-black uppercase ${statusClass(
                          job.status,
                        )}`}
                      >
                        {job.status}
                      </span>
                    </div>
                    <p className="mt-2 text-xs text-slate-400">{job.detail}</p>
                    <div className="mt-4 h-2 overflow-hidden rounded-full bg-white/10">
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-blue-400 to-emerald-300"
                        style={{
                          width:
                            job.status === "running"
                              ? job.progress
                              : job.status === "done"
                                ? "100%"
                                : "16%",
                        }}
                      />
                    </div>
                    <p className="mt-2 text-right text-xs font-bold text-slate-400">
                      {job.progress}
                    </p>
                  </article>
                ))}
              </div>
            </section>
          )}

          {activeNav === "notes" && (
            <section className="mt-6">
              <h2 className="mb-3 text-sm font-black uppercase tracking-[0.18em] text-slate-400">
                노트
              </h2>
              <div className="space-y-3">
                {notes.map((note) => (
                  <article
                    className="rounded-3xl border border-white/10 bg-white/[0.04] p-4"
                    key={`${note.author}-${note.target}`}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="text-[11px] font-semibold text-blue-200">
                          {note.target}
                        </p>
                        <h3 className="mt-1 font-black text-white">
                          {note.author}
                        </h3>
                      </div>
                      <span className="text-[11px] font-bold text-slate-500">
                        {note.time}
                      </span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-slate-300">
                      {note.body}
                    </p>
                    <button className="mt-4 w-full rounded-2xl border border-white/10 bg-white/[0.05] px-4 py-3 text-sm font-black text-white">
                      답글 작성
                    </button>
                  </article>
                ))}
              </div>
            </section>
          )}
        </main>

        <nav className="absolute bottom-5 left-1/2 grid w-[calc(100%-40px)] max-w-[390px] -translate-x-1/2 grid-cols-4 gap-2 rounded-[26px] border border-white/10 bg-[#101722]/95 p-2 shadow-2xl shadow-black/50 backdrop-blur">
          {bottomNavItems.map((item) => (
            <button
              className={`rounded-2xl px-2 py-3 text-xs font-black transition ${navClass(
                activeNav === item.key,
              )}`}
              key={item.key}
              onClick={() => setActiveNav(item.key)}
            >
              {item.label}
            </button>
          ))}
        </nav>
      </div>
    </div>
  );
}
