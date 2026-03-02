# QA 엔지니어를 위한 서버 성능 테스트 입문

성능 테스트 경험이 없거나 적은 QA 엔지니어를 위한 입문 강의 자료 및 실습 환경입니다.

## 강의 목적

1. 서버의 한계를 측정하는 성능 테스트의 핵심 이론 정립
2. 오픈소스 도구(Locust, k6)를 활용한 성능 테스트 실습

## 강의 구성

| 파트 | 시간 | 내용 |
|------|------|------|
| Part 1 — 이론 | 40분 | 성능 테스트의 필요성, 핵심 지표, 실무 적용, 도구 소개 |
| Part 2 — 실습 | 60분 | Locust 실습, k6 실습, Grafana 시각화 |
| Part 3 — 정리 | 20분 | 도구 비교, 핵심 정리, Q&A |

## 사용 도구

- **Locust** — Python 기반 성능 테스트 도구 (Web UI 내장)
- **k6** — JavaScript 기반 성능 테스트 도구 (CLI 중심, Thresholds 자동 판정)
- **Grafana + InfluxDB** — k6 결과 시각화
- **Docker Compose** — 실습 환경 구성

## 프로젝트 구조

```
performance_test/
├── docs/                          # 강의 문서
│   └── 강의안_통합본.md            # 마스터 문서 (이론 + 실습 + 슬라이드 지시)
├── target-server/                 # 성능 테스트 대상 서버
│   ├── app.py                     # FastAPI 기반 샘플 API 서버
│   ├── Dockerfile
│   └── docker-compose.yml
├── locust/                        # Locust 실습 환경
│   ├── docker-compose.yml         # master + worker 구조
│   ├── scripts/
│   │   └── locustfile.py          # Locust 테스트 시나리오
│   └── README.md
├── k6/                            # k6 실습 환경
│   ├── docker-compose.yml         # k6 + InfluxDB 1.8 + Grafana
│   ├── scripts/
│   │   └── example.js             # k6 테스트 시나리오
│   ├── grafana/provisioning/      # Grafana 대시보드 자동 프로비저닝
│   └── README.md
└── backup/                        # 이전 버전 파일
```

## 대상 서버 API

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/` | GET | 실시간 모니터링 대시보드 (웹 UI) |
| `/api/items` | GET | 상품 목록 조회 |
| `/api/items/{id}` | GET | 상품 상세 조회 |
| `/api/items` | POST | 상품 생성 |
| `/api/slow` | GET | 지연 시뮬레이션 (`?delay=초`) |
| `/api/error` | GET | 에러율 시뮬레이션 (`?rate=0~1`) |

## 실습 환경 구성

### 사전 준비

- Docker Desktop 설치 및 실행

### 1. 대상 서버 실행

```bash
cd target-server
docker compose up -d --build
```

브라우저에서 http://localhost:8080 접속 → 실시간 모니터링 대시보드 확인

### 2. Locust 실습

```bash
cd locust
docker compose up
```

- 웹 UI: http://localhost:8089
- 워커 확장: `docker compose up --scale locust-worker=4`

### 3. k6 실습

```bash
cd k6

# InfluxDB + Grafana 실행
docker compose up -d influxdb grafana

# k6 테스트 실행
docker compose run --rm k6 run /scripts/example.js
```

- Grafana 대시보드: http://localhost:3001 (admin / admin)

### 4. 실습 종료

```bash
# 각 디렉터리에서
docker compose down
```

## 데이터 흐름

```
Locust  ──→  대상 서버 (localhost:8080)  ←──  k6
  │                                            │
  └→ Web UI (localhost:8089)                   └→ InfluxDB → Grafana (localhost:3001)
```

- Locust: 자체 Web UI로 실시간 모니터링
- k6: InfluxDB에 결과 저장 → Grafana 대시보드에서 시각화
- 대상 서버: 자체 모니터링 대시보드 (localhost:8080) 제공
