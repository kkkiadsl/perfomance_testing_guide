# Locust 성능 테스트 환경

## 개요

Locust는 **Python으로 테스트 시나리오를 작성**하는 오픈소스 성능 테스트 도구다.
가상 사용자(VU) 행동을 Python 클래스로 정의하고, 웹 UI를 통해 테스트를 실시간으로 제어할 수 있다.

---

## 로컬 환경 설치 (권장)

Docker 없이 Python만으로 실행한다.

### 사전 요건
- Python 3.9 이상 설치 확인: `python3 --version`

### 1단계: 필수 패키지 설치

```bash
pip install locust
```

설치 확인:
```bash
locust --version
```

> **`locust: command not found` 오류 발생 시**
> `pip install` 후에도 명령이 인식되지 않으면 아래 방법을 시도한다.
>
> ```bash
> # pip3로 재설치
> pip3 install locust
>
> # 또는 python 모듈로 직접 실행
> python3 -m locust -f 01_load_test.py --host=http://localhost:8080
> ```

### 2단계: 대상 서버 실행

성능 테스트를 받을 샘플 API 서버를 먼저 실행한다.

```bash
# 프로젝트 루트에서
cd target-server
pip install fastapi uvicorn pydantic
uvicorn app:app --host 0.0.0.0 --port 8080
```

> **`uvicorn: command not found` 오류 발생 시**
> `pip install` 후에도 명령이 인식되지 않으면 아래 방법을 시도한다.
>
> ```bash
> # pip3로 재설치
> pip3 install fastapi uvicorn pydantic
>
> # 또는 python 모듈로 직접 실행
> python3 -m uvicorn app:app --host 0.0.0.0 --port 8080
> ```

브라우저에서 `http://localhost:8080` 접속 → 실시간 모니터링 대시보드가 표시되면 정상.

### 3단계: Locust 실행

새 터미널을 열고:

```bash
cd locust/scripts

# 실습 1 — 부하 테스트
locust -f 01_load_test.py --host=http://localhost:8080

# 실습 2 — 스트레스 테스트
locust -f 02_stress_test.py --host=http://localhost:8080

# 실습 3 — 스파이크 테스트
locust -f 03_spike_test.py --host=http://localhost:8080

# 실습 4 — 내구성 테스트
locust -f 04_soak_test.py --host=http://localhost:8080

# 실습 5 — API별 개별 호출
locust -f 05_api_practice.py --host=http://localhost:8080
```

### 4단계: Web UI 접속

브라우저에서 `http://localhost:8089` 접속 후 Start 클릭.

| 항목 | 설명 |
|---|---|
| Number of users | 최대 동시 가상 사용자 수 |
| Spawn rate | 초당 추가되는 사용자 수 (Ramp-up 속도) |

> 02~04번 스크립트는 `LoadTestShape`가 부하 패턴을 자동 제어한다. Start만 누르면 된다.

---

## 실습 스크립트 구성

| 파일 | 테스트 유형 | 목적 |
|---|---|---|
| `01_load_test.py` | 부하 테스트 | 예상 트래픽에서의 안정성 확인 |
| `02_stress_test.py` | 스트레스 테스트 | 계단식 증가로 한계점 탐색 |
| `03_spike_test.py` | 스파이크 테스트 | 순간 급증 대응력 확인 |
| `04_soak_test.py` | 내구성 테스트 | 장시간 운영 안정성 확인 |
| `05_api_practice.py` | API별 실습 | 엔드포인트별 개별 호출 및 시나리오 |

---

## 대상 서버 API 목록

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/api/items` | 상품 목록 조회 (10~50ms 지연) |
| GET | `/api/items/{id}` | 상품 상세 조회 (5~30ms 지연) |
| POST | `/api/items` | 상품 생성 (30~100ms 지연) |
| GET | `/api/slow?delay=N` | 지연 시뮬레이션 (최대 10초) |
| GET | `/api/error?rate=N` | 에러율 시뮬레이션 (0.0~1.0) |
| GET | `/health` | 헬스체크 |

---

## Locust 스크립트 기본 구조

```python
from locust import HttpUser, task, between

class MyUser(HttpUser):
    wait_time = between(1, 3)   # Think Time: 1~3초 대기

    def on_start(self):         # 사용자 시작 시 1회 실행 (로그인 등)
        pass

    @task(3)                    # 가중치 3 — 다른 task 대비 3배 빈도
    def 자주_호출되는_API(self):
        self.client.get("/api/items", name="상품 목록")

    @task(1)                    # 가중치 1
    def 가끔_호출되는_API(self):
        self.client.get("/api/items/1", name="상품 상세")
```

### 핵심 개념 요약

| 개념 | 설명 |
|---|---|
| `HttpUser` | 가상 사용자 클래스. 이것을 상속받아 시나리오 작성 |
| `wait_time` | Think Time — 요청 사이 대기 시간 |
| `@task(weight)` | 반복 실행할 작업. 숫자가 클수록 더 자주 실행 |
| `name` 파라미터 | 동적 URL을 그룹핑할 때 사용 (결과 집계용) |
| `catch_response=True` | 응답 내용을 직접 검증하여 성공/실패 판정 |
| `LoadTestShape` | 부하 패턴(스파이크, 계단식 등)을 코드로 정의 |
| `SequentialTaskSet` | task를 순서대로 실행 (시나리오 흐름 표현) |

---

## 주요 메트릭 해석

| 메트릭 | 설명 |
|---|---|
| RPS | 초당 처리 요청 수 |
| Failures/s | 초당 실패 요청 수 |
| Median (ms) | 응답시간 중앙값 (p50) |
| 95%ile (ms) | 상위 5%가 경험하는 응답시간 — 가장 중요한 지표 |
| Average (ms) | 평균 응답시간 (이상치에 민감 → p값 참고 권장) |
| Min / Max | 최소 / 최대 응답시간 |

---

## 부록: Docker로 실행하기 (심화)

로컬 설치가 어렵거나 분산 테스트가 필요한 경우 Docker Compose를 사용한다.

```bash
cd locust

# 기본 실행 (Master 1 + Worker 2)
docker compose up

# Worker 수 확장
docker compose up --scale locust-worker=4

# 종료
docker compose down
```

Web UI: `http://localhost:8089`
Host 입력값: `http://host.docker.internal:8080`

> Docker 환경에서는 컨테이너 내부에서 호스트에 접근하므로 `localhost` 대신 `host.docker.internal`을 사용한다.
