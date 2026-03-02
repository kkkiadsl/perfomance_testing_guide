# Locust 성능 테스트 환경

## 개요

Locust는 **Python으로 테스트 시나리오를 작성**하는 오픈소스 성능 테스트 도구다.
가상 사용자(User) 행동을 Python 클래스로 정의하고, 웹 UI를 통해 테스트를 실시간으로 제어할 수 있다.

### 핵심 특징

| 항목 | 내용 |
|---|---|
| 스크립트 언어 | Python |
| 가상 사용자 모델 | 스레드가 아닌 greenlet(코루틴) 기반 → 수천 명의 VU도 경량 처리 |
| 실행 방식 | 웹 UI 또는 CLI |
| 분산 실행 | Master-Worker 아키텍처 지원 |
| 결과 확인 | 내장 웹 UI (실시간 차트, CSV 다운로드) |

---

## 아키텍처 설계

```
┌──────────────────────────────────────────────┐
│               브라우저 (사용자)                │
│          http://localhost:8089 (웹 UI)        │
└──────────────────┬───────────────────────────┘
                   │ 테스트 시작/중지/설정
                   ▼
┌──────────────────────────────────────────────┐
│           locust-master (포트 8089, 5557)     │
│  - 웹 UI 서빙                                 │
│  - 가상 사용자 분배 조율                       │
│  - 메트릭 집계 및 표시                         │
└────────┬─────────────────────────────────────┘
         │ 5557 포트 (마스터-워커 통신)
    ┌────┴────┐
    ▼         ▼
┌────────┐ ┌────────┐
│worker-1│ │worker-2│  ← 수평 확장 가능 (--scale)
│실제 HTTP│ │실제 HTTP│
│요청 발송│ │요청 발송│
└────────┘ └────────┘
         │
         ▼
   [ 테스트 대상 서버 ]
```

### 설계 포인트

**1. Master-Worker 분리**

- `locust-master`: 웹 UI 제공, 워커에게 사용자 분배, 결과 집계
- `locust-worker`: 실제 HTTP 요청 발송. 독립적으로 확장 가능
- 스크립트 파일은 `./scripts` 볼륨을 통해 마스터/워커가 공유

**2. 수평 확장**

워커를 늘릴수록 더 많은 동시 사용자를 생성할 수 있다.
단일 워커로 수백~수천 VU 처리 가능하나, 부하가 클수록 분산이 유리하다.

```bash
# 워커 4개로 확장
docker compose up --scale locust-worker=4
```

**3. 태스크 가중치(`@task(weight)`)**

하나의 User 클래스 안에서 각 요청의 호출 빈도를 비율로 지정한다.

```python
@task(3)  # 메인 페이지: 3 비율
def get_main_page(self): ...

@task(1)  # 상세 페이지: 1 비율
def get_item_detail(self): ...
```

**4. 복수 User 클래스**

`WebsiteUser`, `HeavyUser` 등 행동 패턴이 다른 사용자를 같은 파일에 정의할 수 있다.
웹 UI에서 각 클래스별 비율 조정 가능.

**5. `catch_response=True` — 응답 검증**

HTTP 상태 코드가 200이더라도 비즈니스 로직상 실패일 수 있다.
`catch_response=True`로 응답을 직접 검증하여 Locust UI의 에러율에 반영한다.

```python
with self.client.get("/", catch_response=True) as response:
    if "expected_content" not in response.text:
        response.failure("콘텐츠 검증 실패")
```

**6. `host.docker.internal`**

Docker 컨테이너 내부에서 로컬 호스트(Mac/Windows)의 서버에 접근하기 위한 특수 DNS.
Linux 환경에서는 `--add-host=host.docker.internal:host-gateway` 옵션 추가 필요.

---

## 디렉터리 구조

```
locust/
├── docker-compose.yml   # 컨테이너 환경 정의
└── scripts/
    └── locustfile.py    # 테스트 시나리오 스크립트
```

---

## 실행 방법

### 사전 준비

- Docker Desktop 설치 및 실행

### 1단계: 컨테이너 실행

```bash
cd locust

# 기본 실행 (워커 2개)
docker compose up

# 백그라운드 실행
docker compose up -d

# 워커 수 지정
docker compose up --scale locust-worker=4
```

### 2단계: 웹 UI 접속

브라우저에서 `http://localhost:8089` 접속

| 항목 | 설명 |
|---|---|
| Number of users | 목표 동시 사용자 수 |
| Spawn rate | 초당 가상 사용자 증가 수 (Ramp-up 속도) |
| Host | 테스트 대상 서버 URL |

### 3단계: 테스트 실행 및 모니터링

- **Start** 버튼 클릭 → 테스트 시작
- **Statistics 탭**: 요청별 RPS, 응답시간(평균/p50/p95), 에러율 실시간 확인
- **Charts 탭**: 시간 흐름에 따른 VU 수, RPS, 응답시간 그래프
- **Stop** 버튼으로 테스트 중지

### 4단계: 결과 저장

웹 UI 우측 상단 **Download Data** → CSV 파일로 결과 다운로드

### 컨테이너 종료

```bash
# 포그라운드 실행 중: Ctrl+C
# 백그라운드 실행 중:
docker compose down
```

---

## 스크립트 작성 가이드

### 기본 구조

```python
from locust import HttpUser, task, between

class MyUser(HttpUser):
    wait_time = between(1, 3)     # 태스크 간 대기 시간 (초)

    def on_start(self):           # 사용자 시작 시 1회 실행 (로그인 등)
        pass

    @task
    def my_request(self):         # 반복 실행할 요청
        self.client.get("/api/endpoint")
```

### 주요 wait_time 종류

| 함수 | 동작 |
|---|---|
| `between(min, max)` | min~max 초 사이 랜덤 대기 |
| `constant(t)` | 항상 t초 대기 |
| `constant_pacing(t)` | 태스크 전체 소요 포함 t초 주기 유지 |

### 동적 URL 그룹핑

```python
# 이렇게 하면 /items/1, /items/2 ... 가 개별로 집계됨 (지양)
self.client.get(f"/items/{item_id}")

# name 파라미터로 그룹핑 (권장)
self.client.get(f"/items/{item_id}", name="/items/[id]")
```

---

## 주요 메트릭 해석

| 메트릭 | 설명 |
|---|---|
| RPS | 초당 처리 요청 수 |
| Failures/s | 초당 실패 요청 수 |
| Median (ms) | 응답시간 중앙값 (p50) |
| 95%ile (ms) | 상위 5% 사용자가 경험하는 응답시간 |
| Average (ms) | 평균 응답시간 (이상치에 민감 → p값 참고 권장) |
| Min / Max | 최소 / 최대 응답시간 |
