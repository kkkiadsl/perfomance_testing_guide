"""
실습 5 — API별 개별 호출 실습
=====================================================
목적: 각 API 엔드포인트를 개별적으로 호출하여 동작을 확인한다.
      "어떤 API가 느린가?" "어떤 API에서 에러가 나는가?"를 분리해서 관찰한다.

실행 방법:
  locust -f 05_api_practice.py --host=http://localhost:8080

Web UI 설정 권장값:
  Number of users : 10
  Spawn rate      : 2

사용 가능한 User 클래스 (Web UI에서 선택 가능):
  - ItemsListUser    : 상품 목록 조회만 반복
  - ItemDetailUser   : 상품 상세 조회만 반복
  - CreateItemUser   : 상품 생성만 반복
  - SlowEndpointUser : 지연 API 호출 (타임아웃 테스트)
  - ErrorEndpointUser: 에러 API 호출 (에러율 관찰)
  - FullScenarioUser : 위 API를 순서대로 모두 호출 (시나리오 테스트)

특정 클래스만 실행하려면 CLI에서 지정:
  locust -f 05_api_practice.py --host=http://localhost:8080 \\
         --class-picker          # Web UI에서 클래스 선택 가능
"""

from locust import HttpUser, task, between, SequentialTaskSet
import random


# ── 1. 상품 목록 조회 전용 ───────────────────────────────────────────────────

class ItemsListUser(HttpUser):
    """GET /api/items — 상품 목록 조회만 반복"""
    wait_time = between(1, 2)

    @task
    def 상품_목록_조회(self):
        with self.client.get(
            "/api/items?page=1&size=20",
            name="GET /api/items",
            catch_response=True
        ) as res:
            if res.status_code == 200:
                data = res.json()
                # 응답 데이터 검증: items 키가 있어야 한다
                if "items" not in data:
                    res.failure("응답에 'items' 키 없음")
                else:
                    res.success()
            else:
                res.failure(f"상태코드: {res.status_code}")


# ── 2. 상품 상세 조회 전용 ───────────────────────────────────────────────────

class ItemDetailUser(HttpUser):
    """GET /api/items/{id} — 상품 상세 조회만 반복"""
    wait_time = between(1, 2)

    @task
    def 상품_상세_조회(self):
        item_id = random.randint(1, 100)
        with self.client.get(
            f"/api/items/{item_id}",
            name="GET /api/items/[id]",
            catch_response=True
        ) as res:
            if res.status_code == 200:
                res.success()
            elif res.status_code == 404:
                res.success()   # 범위 초과 ID의 404는 정상 동작
            else:
                res.failure(f"예상치 못한 상태코드: {res.status_code}")


# ── 3. 상품 생성 전용 ────────────────────────────────────────────────────────

class CreateItemUser(HttpUser):
    """POST /api/items — 상품 생성만 반복 (쓰기 부하 테스트)"""
    wait_time = between(1, 3)

    @task
    def 상품_생성(self):
        payload = {
            "name": f"실습 상품 {random.randint(1, 99999)}",
            "value": random.randint(1000, 100000)
        }
        with self.client.post(
            "/api/items",
            json=payload,
            name="POST /api/items",
            catch_response=True
        ) as res:
            if res.status_code in [200, 201]:
                res.success()
            else:
                res.failure(f"생성 실패: {res.status_code} — {res.text[:100]}")


# ── 4. 지연 API 테스트 ───────────────────────────────────────────────────────

class SlowEndpointUser(HttpUser):
    """
    GET /api/slow?delay=N — 응답 지연 API 호출
    응답 시간 p95, p99가 얼마나 올라가는지 관찰한다.
    """
    wait_time = between(2, 4)

    @task(1)
    def 지연_1초(self):
        with self.client.get(
            "/api/slow?delay=1.0",
            name="GET /api/slow (1초 지연)",
            catch_response=True
        ) as res:
            if res.status_code == 200:
                res.success()
            else:
                res.failure(f"상태코드: {res.status_code}")

    @task(1)
    def 지연_2초(self):
        with self.client.get(
            "/api/slow?delay=2.0",
            name="GET /api/slow (2초 지연)",
            catch_response=True
        ) as res:
            if res.status_code == 200:
                res.success()
            else:
                res.failure(f"상태코드: {res.status_code}")


# ── 5. 에러율 API 테스트 ─────────────────────────────────────────────────────

class ErrorEndpointUser(HttpUser):
    """
    GET /api/error?rate=N — 에러율 시뮬레이션 API 호출
    에러율이 올라갈 때 Locust UI의 Failures 탭이 어떻게 변하는지 관찰한다.
    """
    wait_time = between(1, 2)

    @task(1)
    def 에러율_30프로(self):
        """30% 확률로 500 에러 발생"""
        with self.client.get(
            "/api/error?rate=0.3",
            name="GET /api/error (에러율 30%)",
            catch_response=True
        ) as res:
            if res.status_code == 200:
                res.success()
            elif res.status_code == 500:
                res.failure("의도적 500 에러 (에러율 30%)")
            else:
                res.failure(f"상태코드: {res.status_code}")

    @task(1)
    def 에러율_50프로(self):
        """50% 확률로 500 에러 발생"""
        with self.client.get(
            "/api/error?rate=0.5",
            name="GET /api/error (에러율 50%)",
            catch_response=True
        ) as res:
            if res.status_code == 200:
                res.success()
            elif res.status_code == 500:
                res.failure("의도적 500 에러 (에러율 50%)")
            else:
                res.failure(f"상태코드: {res.status_code}")


# ── 6. 전체 시나리오 순서대로 호출 ──────────────────────────────────────────

class FullScenarioTasks(SequentialTaskSet):
    """
    SequentialTaskSet: @task가 순서대로 실행된다.
    실제 사용자의 행동 흐름을 순차적으로 시뮬레이션할 때 사용.
    목록 조회 → 상세 조회 → 생성 → 에러 API 순으로 실행
    """

    @task
    def step1_상품_목록_조회(self):
        self.client.get("/api/items", name="[1단계] 목록 조회")

    @task
    def step2_상품_상세_조회(self):
        item_id = random.randint(1, 50)
        self.client.get(f"/api/items/{item_id}", name="[2단계] 상세 조회")

    @task
    def step3_상품_생성(self):
        payload = {"name": f"시나리오 상품 {random.randint(1, 999)}", "value": 5000}
        self.client.post("/api/items", json=payload, name="[3단계] 상품 생성")

    @task
    def step4_에러_API_호출(self):
        """일부러 에러가 발생하는 API를 포함하여 실제 오류 상황을 재현"""
        self.client.get("/api/error?rate=0.2", name="[4단계] 에러 API")


class FullScenarioUser(HttpUser):
    """전체 시나리오를 순서대로 실행하는 사용자"""
    tasks = [FullScenarioTasks]
    wait_time = between(1, 3)
