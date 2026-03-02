# k6 성능 테스트 환경 (InfluxDB + Grafana 연동)

## 개요

k6는 **JavaScript로 테스트 시나리오를 작성**하는 오픈소스 성능 테스트 도구다.
Grafana Labs에서 개발·관리하며, CLI 중심의 실행 방식과 코드로 임계값(Thresholds)을 정의하는 것이 특징이다.

### 핵심 특징

| 항목 | 내용 |
|---|---|
| 스크립트 언어 | JavaScript (ES6+, Node.js 아님) |
| 가상 사용자 모델 | Go 기반 경량 고루틴 → 높은 부하에서도 낮은 리소스 소비 |
| 실행 방식 | CLI (웹 UI 없음) |
| 결과 저장 | InfluxDB, Prometheus, JSON 등 다양한 output 지원 |
| 시각화 | Grafana 대시보드 (외부 연동) |
| Thresholds | 스크립트 코드 안에 합격/불합격 기준을 명시 |

---

## 아키텍처 설계

```
┌────────────────────────────────────────────────────────────────┐
│                    docker compose 환경                          │
│                                                                │
│  ┌──────────┐   K6_OUT=influxdb   ┌────────────────────────┐  │
│  │   k6     │ ─────────────────→  │  InfluxDB 1.8          │  │
│  │ (runner) │   메트릭 실시간 전송  │  database: k6          │  │
│  └──────────┘                     └───────────┬────────────┘  │
│       │                                       │               │
│       │ HTTP 요청                              │ 데이터 조회     │
│       ▼                                       ▼               │
│  [ 테스트 대상 서버 ]              ┌────────────────────────┐  │
│                                   │  Grafana               │  │
│                                   │  http://localhost:3001 │  │
│                                   │  (대시보드 자동 프로비저닝)│  │
│                                   └────────────────────────┘  │
└────────────────────────────────────────────────────────────────┘
```

### 설계 포인트

**1. InfluxDB 1.8 선택 이유**

k6는 `--out influxdb` 플래그로 InfluxDB에 결과를 전송하는 기능을 내장하고 있다.
이 내장 기능은 **InfluxDB v1 API와 호환**된다.
InfluxDB v2를 사용하려면 별도 확장 플러그인(`xk6-output-influxdb`)이 필요하므로,
실습 환경 단순화를 위해 v1.8을 채택했다.

**2. k6는 `docker compose run`으로 실행**

k6 컨테이너는 InfluxDB/Grafana와 달리 **테스트 실행 시에만 기동**하도록 설계했다.

```
docker compose up -d influxdb grafana   # 항상 켜두는 모니터링 스택
docker compose run --rm k6 run ...      # 테스트 실행 → 완료 후 자동 종료
```

`--rm` 옵션으로 테스트 완료 후 컨테이너가 자동 삭제된다.

**3. Grafana 자동 프로비저닝**

Grafana 시작 시 `provisioning/` 디렉터리를 읽어 **자동으로 데이터소스와 대시보드를 등록**한다.
별도 설정 없이 `docker compose up` 만으로 대시보드가 바로 사용 가능하다.

```
grafana/provisioning/
├── datasources/
│   └── influxdb.yaml     # InfluxDB 데이터소스 자동 등록
└── dashboards/
    ├── dashboard.yaml     # 대시보드 파일 경로 지정
    └── k6-dashboard.json  # k6 메트릭 대시보드 정의
```

**4. Thresholds — 코드로 합격 기준 정의**

k6의 핵심 철학: 성능 기준을 코드에 명시하고, CI/CD에서 자동으로 합격/불합격 판정.

```javascript
thresholds: {
    http_req_failed:   ['rate<0.01'],   // 에러율 1% 미만이어야 통과
    http_req_duration: ['p(95)<500'],   // p95 응답시간 500ms 미만이어야 통과
}
```

임계값 위반 시 k6 프로세스가 **exit code 99**로 종료 → CI/CD 파이프라인에서 자동 실패 처리 가능.

**5. 환경변수(`__ENV`)로 유연한 대상 서버 설정**

```javascript
const BASE_URL = __ENV.TARGET_URL || 'http://host.docker.internal';
```

스크립트 수정 없이 실행 시 환경변수로 대상 서버 변경 가능.

**6. Grafana 대시보드 패널 구성**

| 패널 | 설명 |
|---|---|
| 활성 VU 수 | 현재 실행 중인 가상 사용자 수 |
| HTTP 에러율 | 실패 요청 비율 |
| 평균 응답시간 | 전체 HTTP 요청 평균 |
| p95 응답시간 | 상위 5% 사용자가 경험하는 응답시간 |
| RPS | 초당 처리 요청 수 |
| VU vs RPS 추이 | 사용자 증가에 따른 처리량 변화 |
| 응답시간 백분위수 | p50/p90/p95/p99/최대 비교 |
| 요청 단계별 시간 | DNS→TCP→TLS→전송→대기→수신 스택 분석 |
| 네트워크 처리량 | 초당 송수신 데이터량 |

---

## 디렉터리 구조

```
k6/
├── docker-compose.yml               # 컨테이너 환경 정의
├── scripts/
│   └── example.js                   # 테스트 시나리오 스크립트
└── grafana/
    └── provisioning/
        ├── datasources/
        │   └── influxdb.yaml        # InfluxDB 데이터소스 자동 등록
        └── dashboards/
            ├── dashboard.yaml       # 대시보드 파일 위치 지정
            └── k6-dashboard.json    # k6 결과 시각화 대시보드
```

---

## 실행 방법

### 사전 준비

- Docker Desktop 설치 및 실행

### 1단계: 모니터링 스택 실행

```bash
cd k6

# InfluxDB + Grafana 백그라운드 실행
docker compose up -d influxdb grafana

# 준비 상태 확인
docker compose ps
```

### 2단계: k6 테스트 실행

```bash
# 기본 실행 (스크립트에 정의된 options 사용)
docker compose run --rm k6 run /scripts/example.js

# VU 수와 지속 시간 직접 지정
docker compose run --rm k6 run \
  --vus 50 \
  --duration 3m \
  /scripts/example.js

# 테스트 대상 URL 변경
docker compose run --rm \
  -e TARGET_URL=http://my-api-server:8080 \
  k6 run /scripts/example.js

# 결과를 JSON 파일로도 저장
docker compose run --rm k6 run \
  --out json=/scripts/result.json \
  /scripts/example.js
```

### 3단계: Grafana 대시보드 확인

브라우저에서 `http://localhost:3001` 접속

- 계정: `admin` / `admin`
- 좌측 메뉴 → **Dashboards** → **k6 성능 테스트 결과** 선택
- 테스트 실행 중 실시간으로 메트릭 확인 가능 (5초 자동 갱신)

### 4단계: 테스트 결과 해석

k6 CLI 출력 예시:

```
✓ 상태코드 200
✓ 응답시간 500ms 미만

checks.........................: 98.50%  ✓ 1970  ✗ 30
http_req_duration..............: avg=123ms  min=45ms  med=110ms  max=980ms  p(90)=220ms  p(95)=310ms
http_req_failed................: 0.50%   ✓ 10    ✗ 1990
http_reqs......................: 2000    33.3/s
```

| 출력 항목 | 의미 |
|---|---|
| `checks` | `check()` 검증 통과율 |
| `http_req_duration` | 전체 HTTP 응답시간 분포 |
| `http_req_failed` | HTTP 에러 비율 |
| `http_reqs` | 총 요청 수 및 RPS |
| `✓ threshold` | Thresholds 통과 (테스트 성공) |
| `✗ threshold` | Thresholds 위반 (exit code 99, 테스트 실패) |

### 컨테이너 종료

```bash
# 모니터링 스택 종료 (데이터 보존)
docker compose down

# 데이터까지 완전 삭제
docker compose down -v
```

---

## 스크립트 작성 가이드

### 기본 구조

```javascript
import http from 'k6/http';
import { check, sleep } from 'k6';

// 테스트 설정
export const options = {
  vus: 10,           // 동시 가상 사용자 수
  duration: '30s',   // 테스트 지속 시간
};

// 가상 사용자마다 반복 실행
export default function () {
  const res = http.get('http://my-server/');

  check(res, {
    '상태코드 200': (r) => r.status === 200,
  });

  sleep(1);
}
```

### stages로 단계적 부하 증가

```javascript
export const options = {
  stages: [
    { duration: '1m', target: 50 },   // 1분간 50명으로 증가
    { duration: '3m', target: 50 },   // 3분간 50명 유지
    { duration: '1m', target: 0  },   // 1분간 0명으로 감소
  ],
};
```

### 커스텀 메트릭

```javascript
import { Rate, Trend, Counter, Gauge } from 'k6/metrics';

const errorRate  = new Rate('my_error_rate');    // 비율 (0~1)
const latency    = new Trend('my_latency');      // 분포 (p값 계산 가능)
const reqCount   = new Counter('my_req_count');  // 누적 합계
const activeConn = new Gauge('active_conn');     // 현재 값
```

---

## k6 vs Locust 비교

| 항목 | k6 | Locust |
|---|---|---|
| 스크립트 언어 | JavaScript | Python |
| 웹 UI | 없음 (CLI 중심) | 있음 (내장) |
| 결과 시각화 | Grafana 별도 연동 | 내장 UI |
| Thresholds | 코드로 자동 판정 | 수동 확인 |
| CI/CD 연동 | 용이 (exit code 활용) | 상대적으로 복잡 |
| 리소스 효율 | 높음 (Go 기반) | 보통 (Python, greenlet) |
| 학습 난이도 | JavaScript 친숙 시 낮음 | Python 친숙 시 낮음 |
