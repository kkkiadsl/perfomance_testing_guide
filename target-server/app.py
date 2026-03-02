"""
성능 테스트용 샘플 API 서버 (실시간 웹 대시보드 포함)

http://localhost:8080 에서 실시간 부하 현황을 시각적으로 확인할 수 있다.

엔드포인트:
  GET  /                  - 실시간 모니터링 대시보드 (웹 UI)
  GET  /metrics/stream    - Server-Sent Events (대시보드 데이터 소스)
  GET  /health            - 헬스체크
  GET  /api/items         - 상품 목록 (페이지네이션)
  GET  /api/items/{id}    - 상품 상세
  POST /api/items         - 상품 생성
  GET  /api/slow          - 지연 시뮬레이션 (?delay=초)
  GET  /api/error         - 에러율 시뮬레이션 (?rate=0~1)
"""

import asyncio
import json
import random
import time
from collections import deque
from typing import Optional, AsyncGenerator

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

app = FastAPI(title="성능 테스트 대상 서버", version="1.0.0")

START_TIME = time.time()


# ─── 실시간 메트릭 수집기 ────────────────────────────────────────────────────

class MetricsCollector:
    """
    모든 HTTP 요청의 메트릭을 수집하고 초 단위 버킷으로 집계한다.
    대시보드의 SSE 스트림은 이 데이터를 1초 주기로 푸시한다.
    """

    def __init__(self):
        self.total_requests: int = 0
        self.total_errors: int = 0
        self.active_requests: int = 0

        # 최근 60초 슬라이딩 윈도우 (초 단위 버킷)
        self._history: deque = deque(maxlen=60)

        # 현재 진행 중인 초의 임시 데이터
        self._bucket_ts: int = int(time.time())
        self._bucket_count: int = 0
        self._bucket_errors: int = 0
        self._bucket_durations: list = []

        self._lock = asyncio.Lock()

    async def record(self, duration_ms: float, is_error: bool) -> None:
        """요청 완료 시 호출 — 미들웨어에서 자동 호출됨"""
        async with self._lock:
            self.total_requests += 1
            if is_error:
                self.total_errors += 1

            now_ts = int(time.time())

            # 초가 바뀌면 이전 버킷을 히스토리에 확정
            if now_ts != self._bucket_ts:
                avg_ms = (
                    sum(self._bucket_durations) / len(self._bucket_durations)
                    if self._bucket_durations else 0
                )
                self._history.append({
                    "ts": self._bucket_ts,
                    "rps": self._bucket_count,
                    "errors": self._bucket_errors,
                    "avg_ms": round(avg_ms, 1),
                })
                self._bucket_ts = now_ts
                self._bucket_count = 0
                self._bucket_errors = 0
                self._bucket_durations = []

            self._bucket_count += 1
            if is_error:
                self._bucket_errors += 1
            self._bucket_durations.append(duration_ms)

    async def snapshot(self) -> dict:
        """대시보드 SSE 전송용 현재 메트릭 스냅샷"""
        async with self._lock:
            history = list(self._history)

            # 최근 5초 평균 RPS / 응답시간
            recent = history[-5:]
            avg_rps = (
                sum(b["rps"] for b in recent) / len(recent)
                if recent else self._bucket_count
            )
            recent_ms = [b["avg_ms"] for b in recent if b["avg_ms"] > 0]
            avg_ms = sum(recent_ms) / len(recent_ms) if recent_ms else 0

            # 히스토리 전체 기준 에러율
            window_total = sum(b["rps"] for b in history)
            window_errors = sum(b["errors"] for b in history)
            error_rate = (window_errors / window_total * 100) if window_total else 0

            return {
                "total_requests": self.total_requests,
                "total_errors": self.total_errors,
                "active_requests": self.active_requests,
                "current_rps": self._bucket_count,
                "avg_rps": round(avg_rps, 1),
                "avg_ms": round(avg_ms, 1),
                "error_rate": round(error_rate, 2),
                "uptime": int(time.time() - START_TIME),
                "history": history[-30:],  # 최근 30초만 전송
            }


metrics = MetricsCollector()


# ─── 미들웨어: 모든 요청 자동 추적 ─────────────────────────────────────────

@app.middleware("http")
async def track_metrics(request: Request, call_next):
    # SSE 스트림 자체는 추적 제외 (무한 루프 방지)
    if request.url.path in ("/metrics/stream", "/health"):
        return await call_next(request)

    metrics.active_requests += 1
    start = time.perf_counter()
    is_error = False
    try:
        response = await call_next(request)
        is_error = response.status_code >= 500
        return response
    except Exception:
        is_error = True
        raise
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        metrics.active_requests -= 1
        await metrics.record(duration_ms, is_error)


# ─── 대시보드 HTML ────────────────────────────────────────────────────────────

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>성능 테스트 대상 서버</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
  <style>
    :root {
      --bg: #0f172a; --card: #1e293b; --border: #334155;
      --text: #e2e8f0; --dim: #64748b;
      --green: #22c55e; --yellow: #eab308; --orange: #f97316; --red: #ef4444;
      --blue: #3b82f6; --purple: #a78bfa;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: 'Segoe UI', system-ui, sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; }

    /* Header */
    .header {
      display: flex; justify-content: space-between; align-items: center;
      padding: 18px 32px; background: var(--card); border-bottom: 1px solid var(--border);
    }
    .header h1 { font-size: 18px; font-weight: 700; letter-spacing: -0.02em; }
    .header-sub { font-size: 12px; color: var(--dim); margin-top: 2px; }
    .uptime-badge {
      font-family: monospace; font-size: 13px; font-weight: 600;
      background: var(--bg); border: 1px solid var(--border);
      padding: 6px 14px; border-radius: 20px; color: var(--text);
    }

    /* Stress Banner */
    .stress-banner {
      display: flex; align-items: center; gap: 14px;
      padding: 14px 32px;
      border-left: 4px solid var(--green);
      background: rgba(34,197,94,0.07);
      transition: border-color .5s, background .5s;
    }
    .status-dot {
      width: 10px; height: 10px; border-radius: 50%;
      background: var(--green); transition: background .5s;
      box-shadow: 0 0 0 0 rgba(34,197,94,.5);
      animation: pulse-dot 2s infinite;
    }
    @keyframes pulse-dot {
      0%   { box-shadow: 0 0 0 0 rgba(34,197,94,.5); }
      70%  { box-shadow: 0 0 0 6px rgba(34,197,94,0); }
      100% { box-shadow: 0 0 0 0 rgba(34,197,94,0); }
    }
    .stress-label { font-size: 11px; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; color: var(--dim); }
    .stress-level { font-size: 16px; font-weight: 800; min-width: 48px; transition: color .5s; }
    .stress-bar-bg { flex: 1; height: 6px; background: var(--border); border-radius: 3px; overflow: hidden; }
    .stress-bar-fill { height: 100%; border-radius: 3px; width: 0%; transition: width .4s, background .5s; background: var(--green); }
    .stress-rps { font-size: 14px; font-weight: 700; min-width: 72px; text-align: right; font-variant-numeric: tabular-nums; }

    /* Layout */
    .main { padding: 24px 32px; display: flex; flex-direction: column; gap: 20px; }

    /* Stat cards */
    .cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
    .card {
      background: var(--card); border: 1px solid var(--border); border-radius: 12px;
      padding: 20px 24px; display: flex; flex-direction: column; gap: 6px;
    }
    .card-label { font-size: 11px; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; color: var(--dim); }
    .card-value {
      font-size: 42px; font-weight: 800; line-height: 1.1;
      font-variant-numeric: tabular-nums; transition: color .3s;
    }
    .card-unit { font-size: 14px; font-weight: 400; color: var(--dim); }
    .card-sub { font-size: 11px; color: var(--dim); }

    /* Charts */
    .charts { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
    .chart-card {
      background: var(--card); border: 1px solid var(--border);
      border-radius: 12px; padding: 20px 20px 16px;
    }
    .chart-title { font-size: 11px; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; color: var(--dim); margin-bottom: 14px; }
    .chart-wrapper { position: relative; height: 180px; }

    /* Bottom stats */
    .bottom { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
    .stat-box {
      background: var(--card); border: 1px solid var(--border); border-radius: 12px;
      padding: 18px 24px; display: flex; flex-direction: column; gap: 4px;
    }
    .stat-box-label { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .1em; color: var(--dim); }
    .stat-box-value { font-size: 30px; font-weight: 800; font-variant-numeric: tabular-nums; }

    /* Endpoint table */
    .ep-card { background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 20px 24px; }
    .ep-title { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .1em; color: var(--dim); margin-bottom: 14px; }
    .ep-list { display: flex; flex-direction: column; gap: 8px; }
    .ep-row {
      display: flex; align-items: center; gap: 12px;
      padding: 10px 14px; background: var(--bg); border-radius: 8px;
      font-family: 'Consolas', 'SF Mono', monospace; font-size: 13px;
    }
    .method {
      padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 700;
      min-width: 42px; text-align: center; letter-spacing: .05em;
    }
    .get  { background: rgba(59,130,246,.15); color: #60a5fa; }
    .post { background: rgba(34,197,94,.15);  color: #4ade80; }
    .ep-desc { color: var(--dim); font-family: 'Segoe UI', sans-serif; font-size: 12px; margin-left: auto; }

    @media (max-width: 900px) {
      .cards { grid-template-columns: repeat(2, 1fr); }
      .charts { grid-template-columns: 1fr; }
      .bottom { grid-template-columns: repeat(2, 1fr); }
      .main { padding: 16px; }
      .header { padding: 16px; }
      .stress-banner { padding: 12px 16px; }
    }
  </style>
</head>
<body>

<div class="header">
  <div>
    <h1>성능 테스트 대상 서버</h1>
    <div class="header-sub">http://localhost:8080 &nbsp;·&nbsp; 실시간 모니터링</div>
  </div>
  <div class="uptime-badge" id="uptime-badge">업타임: 00:00:00</div>
</div>

<div class="stress-banner" id="stress-banner">
  <div class="status-dot" id="status-dot"></div>
  <span class="stress-label">부하 레벨</span>
  <span class="stress-level" id="stress-level" style="color:var(--dim)">연결 중...</span>
  <div class="stress-bar-bg">
    <div class="stress-bar-fill" id="stress-bar"></div>
  </div>
  <span class="stress-rps" id="stress-rps">— RPS</span>
</div>

<div class="main">

  <div class="cards">
    <div class="card">
      <div class="card-label">초당 요청 수</div>
      <div class="card-value" id="val-rps">—&nbsp;<span class="card-unit">RPS</span></div>
      <div class="card-sub">5초 평균</div>
    </div>
    <div class="card">
      <div class="card-label">활성 요청</div>
      <div class="card-value" id="val-active">—&nbsp;<span class="card-unit">req</span></div>
      <div class="card-sub">현재 처리 중</div>
    </div>
    <div class="card">
      <div class="card-label">평균 응답시간</div>
      <div class="card-value" id="val-ms">—&nbsp;<span class="card-unit">ms</span></div>
      <div class="card-sub">5초 평균</div>
    </div>
    <div class="card">
      <div class="card-label">에러율</div>
      <div class="card-value" id="val-err">—&nbsp;<span class="card-unit">%</span></div>
      <div class="card-sub">HTTP 5xx 기준</div>
    </div>
  </div>

  <div class="charts">
    <div class="chart-card">
      <div class="chart-title">초당 요청 수 (RPS) — 최근 30초</div>
      <div class="chart-wrapper"><canvas id="chart-rps"></canvas></div>
    </div>
    <div class="chart-card">
      <div class="chart-title">평균 응답시간 (ms) — 최근 30초</div>
      <div class="chart-wrapper"><canvas id="chart-ms"></canvas></div>
    </div>
  </div>

  <div class="bottom">
    <div class="stat-box">
      <div class="stat-box-label">총 요청 수</div>
      <div class="stat-box-value" id="val-total">—</div>
    </div>
    <div class="stat-box">
      <div class="stat-box-label">총 에러 수</div>
      <div class="stat-box-value" id="val-errtotal" style="color:var(--red)">—</div>
    </div>
    <div class="stat-box">
      <div class="stat-box-label">서버 업타임</div>
      <div class="stat-box-value" id="val-uptime" style="font-size:22px">00:00:00</div>
    </div>
  </div>

  <div class="ep-card">
    <div class="ep-title">API 엔드포인트</div>
    <div class="ep-list">
      <div class="ep-row">
        <span class="method get">GET</span>
        <span>/api/items?page=1&size=20</span>
        <span class="ep-desc">상품 목록 조회 · DB 시뮬레이션 10~50ms</span>
      </div>
      <div class="ep-row">
        <span class="method get">GET</span>
        <span>/api/items/{id}</span>
        <span class="ep-desc">상품 상세 조회 · 5~30ms · 범위 초과 시 404</span>
      </div>
      <div class="ep-row">
        <span class="method post">POST</span>
        <span>/api/items</span>
        <span class="ep-desc">상품 생성 · 쓰기 시뮬레이션 30~100ms</span>
      </div>
      <div class="ep-row">
        <span class="method get">GET</span>
        <span>/api/slow?delay=1.0</span>
        <span class="ep-desc">지연 시뮬레이션 · 타임아웃 테스트용 (최대 10초)</span>
      </div>
      <div class="ep-row">
        <span class="method get">GET</span>
        <span>/api/error?rate=0.3</span>
        <span class="ep-desc">에러율 시뮬레이션 · 0.3 = 30% 확률로 500 반환</span>
      </div>
      <div class="ep-row">
        <span class="method get">GET</span>
        <span>/health</span>
        <span class="ep-desc">헬스체크 (메트릭 미집계)</span>
      </div>
    </div>
  </div>

</div>

<script>
  // ─── Chart.js 공통 옵션 ──────────────────────────────────────────────────
  const WINDOW = 30;
  const emptyData = () => Array(WINDOW).fill(null);
  const baseLabels = Array.from({length: WINDOW}, (_, i) => i % 5 === 0 ? `-${WINDOW - i}s` : '');

  const scaleOpts = {
    x: {
      ticks: { color: '#475569', font: { size: 10 }, maxRotation: 0 },
      grid: { color: 'rgba(51,65,85,0.5)' },
    },
    y: {
      ticks: { color: '#475569', font: { size: 10 } },
      grid: { color: 'rgba(51,65,85,0.5)' },
      beginAtZero: true,
    },
  };

  // RPS 차트 (막대 그래프)
  const rpsChart = new Chart(document.getElementById('chart-rps'), {
    type: 'bar',
    data: {
      labels: [...baseLabels],
      datasets: [{
        data: emptyData(),
        backgroundColor: Array(WINDOW).fill('rgba(59,130,246,0.5)'),
        borderColor: Array(WINDOW).fill('#3b82f6'),
        borderWidth: 1,
        borderRadius: 3,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      animation: { duration: 200 },
      plugins: { legend: { display: false }, tooltip: {
        callbacks: { label: ctx => ` ${ctx.raw} req/s` }
      }},
      scales: scaleOpts,
    },
  });

  // 응답시간 차트 (라인 그래프)
  const msChart = new Chart(document.getElementById('chart-ms'), {
    type: 'line',
    data: {
      labels: [...baseLabels],
      datasets: [{
        data: emptyData(),
        borderColor: '#a78bfa',
        backgroundColor: 'rgba(167,139,250,0.08)',
        borderWidth: 2, tension: 0.4, pointRadius: 0, fill: true,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      animation: { duration: 200 },
      plugins: { legend: { display: false }, tooltip: {
        callbacks: { label: ctx => ` ${ctx.raw} ms` }
      }},
      scales: scaleOpts,
    },
  });

  // ─── 스트레스 레벨 설정 ───────────────────────────────────────────────────
  function stressConfig(rps) {
    if (rps < 10)  return { label: '안정',  color: '#22c55e', bg: 'rgba(34,197,94,0.07)',  barColor: '#22c55e', pct: rps / 10 * 25 };
    if (rps < 30)  return { label: '주의',  color: '#eab308', bg: 'rgba(234,179,8,0.07)',  barColor: '#eab308', pct: 25 + (rps - 10) / 20 * 25 };
    if (rps < 60)  return { label: '경고',  color: '#f97316', bg: 'rgba(249,115,22,0.07)', barColor: '#f97316', pct: 50 + (rps - 30) / 30 * 25 };
    return               { label: '위험',  color: '#ef4444', bg: 'rgba(239,68,68,0.09)',  barColor: '#ef4444', pct: Math.min(75 + (rps - 60) / 40 * 25, 100) };
  }

  // ─── 포맷 헬퍼 ───────────────────────────────────────────────────────────
  const fmt    = n => Math.round(n).toLocaleString('ko-KR');
  const fmtMs  = n => n < 1000 ? `${Math.round(n)}` : `${(n/1000).toFixed(1)}k`;
  function fmtTime(s) {
    const h = String(Math.floor(s / 3600)).padStart(2, '0');
    const m = String(Math.floor((s % 3600) / 60)).padStart(2, '0');
    const sec = String(s % 60).padStart(2, '0');
    return `${h}:${m}:${sec}`;
  }

  // ─── RPS 값에 따른 막대 색 ───────────────────────────────────────────────
  function rpsBarColor(rps) {
    if (rps < 10)  return 'rgba(59,130,246,0.55)';
    if (rps < 30)  return 'rgba(234,179,8,0.55)';
    if (rps < 60)  return 'rgba(249,115,22,0.55)';
    return               'rgba(239,68,68,0.65)';
  }
  function rpsBorderColor(rps) {
    if (rps < 10)  return '#3b82f6';
    if (rps < 30)  return '#eab308';
    if (rps < 60)  return '#f97316';
    return               '#ef4444';
  }

  // ─── UI 전체 업데이트 ─────────────────────────────────────────────────────
  function update(d) {
    const rps = d.avg_rps;
    const cfg = stressConfig(rps);

    // 스트레스 배너
    const banner = document.getElementById('stress-banner');
    banner.style.background    = cfg.bg;
    banner.style.borderColor   = cfg.color;

    const dot = document.getElementById('status-dot');
    dot.style.background = cfg.color;
    dot.style.animationDuration = rps > 60 ? '0.5s' : rps > 30 ? '1s' : '2s';

    const lvl = document.getElementById('stress-level');
    lvl.textContent   = cfg.label;
    lvl.style.color   = cfg.color;

    const bar = document.getElementById('stress-bar');
    bar.style.width      = cfg.pct + '%';
    bar.style.background = cfg.barColor;

    document.getElementById('stress-rps').textContent = rps.toFixed(1) + ' RPS';

    // 메트릭 카드
    const rpsEl = document.getElementById('val-rps');
    rpsEl.innerHTML    = `${rps.toFixed(1)}&nbsp;<span class="card-unit">RPS</span>`;
    rpsEl.style.color  = rps > 30 ? cfg.color : 'var(--text)';

    const actEl = document.getElementById('val-active');
    actEl.innerHTML    = `${d.active_requests}&nbsp;<span class="card-unit">req</span>`;
    actEl.style.color  = d.active_requests > 20 ? 'var(--orange)' : 'var(--text)';

    const msEl = document.getElementById('val-ms');
    msEl.innerHTML     = `${fmtMs(d.avg_ms)}&nbsp;<span class="card-unit">ms</span>`;
    msEl.style.color   = d.avg_ms > 500 ? 'var(--red)' : d.avg_ms > 200 ? 'var(--yellow)' : 'var(--text)';

    const errEl = document.getElementById('val-err');
    errEl.innerHTML    = `${d.error_rate.toFixed(1)}&nbsp;<span class="card-unit">%</span>`;
    errEl.style.color  = d.error_rate >= 1 ? 'var(--red)' : d.error_rate > 0 ? 'var(--yellow)' : 'var(--text)';

    // 하단 통계
    document.getElementById('val-total').textContent    = fmt(d.total_requests);
    document.getElementById('val-errtotal').textContent = fmt(d.total_errors);
    const upStr = fmtTime(d.uptime);
    document.getElementById('val-uptime').textContent   = upStr;
    document.getElementById('uptime-badge').textContent = '업타임: ' + upStr;

    // 차트 업데이트
    if (d.history && d.history.length > 0) {
      const hist    = d.history.slice(-WINDOW);
      const pad     = WINDOW - hist.length;
      const rpsData = [...Array(pad).fill(null), ...hist.map(b => b.rps)];
      const msData  = [...Array(pad).fill(null), ...hist.map(b => b.avg_ms || null)];
      const bgColors = [...Array(pad).fill('rgba(59,130,246,0.1)'), ...hist.map(b => rpsBarColor(b.rps))];
      const bdColors = [...Array(pad).fill('#3b82f6'),              ...hist.map(b => rpsBorderColor(b.rps))];

      rpsChart.data.datasets[0].data            = rpsData;
      rpsChart.data.datasets[0].backgroundColor = bgColors;
      rpsChart.data.datasets[0].borderColor     = bdColors;
      msChart.data.datasets[0].data             = msData;

      rpsChart.update('none');
      msChart.update('none');
    }
  }

  // ─── SSE 연결 (자동 재연결 포함) ────────────────────────────────────────
  function connect() {
    const es = new EventSource('/metrics/stream');

    es.onopen = () => {
      document.getElementById('stress-level').textContent = '연결됨';
    };

    es.onmessage = (e) => {
      try { update(JSON.parse(e.data)); }
      catch (_) {}
    };

    es.onerror = () => {
      document.getElementById('stress-level').textContent = '재연결 중...';
      document.getElementById('stress-level').style.color = 'var(--dim)';
      es.close();
      setTimeout(connect, 3000);
    };
  }

  connect();
</script>
</body>
</html>
"""


# ─── 라우트 ──────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """실시간 모니터링 대시보드"""
    return HTMLResponse(content=DASHBOARD_HTML)


@app.get("/metrics/stream")
async def metrics_stream():
    """
    Server-Sent Events (SSE) — 대시보드에 메트릭을 1초 주기로 푸시
    브라우저는 /metrics/stream 에 연결하여 실시간 데이터를 수신한다.
    """
    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            while True:
                data = await metrics.snapshot()
                yield f"data: {json.dumps(data)}\n\n"
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass  # 클라이언트 연결 종료 시 정상 종료

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection":    "keep-alive",
            "X-Accel-Buffering": "no",  # Nginx 프록시 사용 시 버퍼링 방지
        },
    )


@app.get("/health")
async def health_check():
    """헬스체크 — 메트릭 집계 제외"""
    return {"status": "ok", "uptime_seconds": round(time.time() - START_TIME, 1)}


# ─── 데이터 모델 ──────────────────────────────────────────────────────────────

class Item(BaseModel):
    name: str
    value: Optional[int] = None


# ─── 인메모리 데이터 (실습용) ─────────────────────────────────────────────────

ITEMS = [
    {"id": i, "name": f"상품 {i:03d}", "value": random.randint(100, 10000)}
    for i in range(1, 101)
]


def db_latency(min_ms: float, max_ms: float) -> float:
    """DB 쿼리 지연 시뮬레이션 (초 단위 반환)"""
    return random.uniform(min_ms, max_ms) / 1000


# ─── API 엔드포인트 ───────────────────────────────────────────────────────────

@app.get("/api/items")
async def list_items(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
):
    """상품 목록 조회 (페이지네이션) · DB 시뮬레이션 10~50ms"""
    await asyncio.sleep(db_latency(10, 50))
    start = (page - 1) * size
    paged = ITEMS[start: start + size]
    return {
        "items": paged,
        "total": len(ITEMS),
        "page": page,
        "size": size,
        "pages": (len(ITEMS) + size - 1) // size,
    }


@app.get("/api/items/{item_id}")
async def get_item(item_id: int):
    """상품 상세 조회 · DB 시뮬레이션 5~30ms · 범위 외 ID는 404"""
    await asyncio.sleep(db_latency(5, 30))
    if item_id < 1 or item_id > len(ITEMS):
        raise HTTPException(status_code=404, detail=f"상품 ID {item_id}를 찾을 수 없습니다")
    return ITEMS[item_id - 1]


@app.post("/api/items", status_code=201)
async def create_item(item: Item):
    """상품 생성 · 쓰기 시뮬레이션 30~100ms"""
    await asyncio.sleep(db_latency(30, 100))
    return {
        "id": len(ITEMS) + random.randint(100, 999),
        "name": item.name,
        "value": item.value or random.randint(100, 10000),
    }


@app.get("/api/slow")
async def slow_endpoint(
    delay: float = Query(default=1.0, ge=0.1, le=10.0, description="지연 시간 (초)"),
):
    """응답 지연 시뮬레이션 · 타임아웃 테스트용"""
    await asyncio.sleep(delay)
    return {"delayed_seconds": delay, "message": f"{delay}초 지연 후 응답"}


@app.get("/api/error")
async def error_endpoint(
    rate: float = Query(default=0.5, ge=0.0, le=1.0, description="에러 발생 확률 (0.0~1.0)"),
):
    """에러율 시뮬레이션 · Threshold 테스트용"""
    await asyncio.sleep(db_latency(5, 20))
    if random.random() < rate:
        raise HTTPException(status_code=500, detail="시뮬레이션된 서버 에러 (의도적 오류)")
    return {"status": "ok", "error_rate": rate}
