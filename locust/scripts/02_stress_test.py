"""
실습 2 — 스트레스 테스트 (Stress Test)
=====================================================
목적: 사용자를 계단식으로 증가시켜 서버의 한계점(Breaking Point)을 찾는다.
패턴: 계단식 증가 → 어느 구간에서 에러율이 치솟고 응답시간이 폭증하는지 관찰

실행 방법:
  locust -f 02_stress_test.py --host=http://localhost:8080

  (LoadTestShape가 자동으로 부하 패턴을 제어하므로 Web UI에서 Start만 누르면 된다.)
  Web UI 접속: http://localhost:8089
  Start 버튼 클릭 후 자동 진행

부하 단계:
  0~  60초 :  10명 (기준선 — 안정 구간)
  60~120초 :  30명 (증가 1단계)
  120~180초:  60명 (증가 2단계)
  180~240초: 100명 (증가 3단계 — 한계 탐색)
  240~300초:   0명 (Ramp-down)

확인 포인트:
  - 어느 단계에서 응답시간이 급증하는가?
  - 에러율이 1%를 넘는 시점은?
  - 서버가 한계를 넘어서도 회복되는가? (Ramp-down 후 정상 복귀 여부)
"""

from locust import HttpUser, task, between, LoadTestShape
import random


# ── 부하 패턴 정의 ──────────────────────────────────────────────────────────

class StressTestShape(LoadTestShape):
    """
    계단식 스트레스 테스트 패턴.
    tick()이 1초마다 호출되어 현재 목표 (사용자 수, spawn_rate)를 반환한다.
    None을 반환하면 테스트가 자동 종료된다.
    """

    # (경과 시간 초, 목표 사용자 수, 초당 spawn 수)
    stages = [
        (60,  10,  5),    # 0~60초  :  10명
        (120, 30,  5),    # 60~120초:  30명
        (180, 60,  10),   # 120~180초: 60명
        (240, 100, 10),   # 180~240초: 100명
        (300, 0,   20),   # 240~300초: Ramp-down
    ]

    def tick(self):
        run_time = self.get_run_time()
        for end_time, users, spawn_rate in self.stages:
            if run_time < end_time:
                return users, spawn_rate
        return None   # 모든 단계 완료 → 테스트 자동 종료


# ── 가상 사용자 정의 ────────────────────────────────────────────────────────

class StressTestUser(HttpUser):
    """스트레스 테스트용 가상 사용자"""

    wait_time = between(1, 2)

    @task(4)
    def 상품_목록_조회(self):
        with self.client.get(
            "/api/items",
            name="[목록] GET /api/items",
            catch_response=True
        ) as res:
            if res.status_code == 200:
                res.success()
            else:
                res.failure(f"상태코드: {res.status_code}")

    @task(3)
    def 상품_상세_조회(self):
        item_id = random.randint(1, 100)
        with self.client.get(
            f"/api/items/{item_id}",
            name="[상세] GET /api/items/[id]",
            catch_response=True
        ) as res:
            if res.status_code in [200, 404]:
                res.success()
            else:
                res.failure(f"상태코드: {res.status_code}")

    @task(2)
    def 상품_생성(self):
        payload = {
            "name": f"스트레스 테스트 상품 {random.randint(1, 9999)}",
            "value": random.randint(100, 50000)
        }
        with self.client.post(
            "/api/items",
            json=payload,
            name="[생성] POST /api/items",
            catch_response=True
        ) as res:
            if res.status_code in [200, 201]:
                res.success()
            else:
                res.failure(f"생성 실패: {res.status_code}")
