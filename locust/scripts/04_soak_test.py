"""
실습 4 — 내구성 테스트 (Soak Test)
=====================================================
목적: 장시간 운영 시 메모리 누수, 커넥션 고갈 등 누적 장애를 탐지한다.
패턴: 적당한 부하를 장시간 유지

실행 방법:
  locust -f 04_soak_test.py --host=http://localhost:8080

  Web UI 설정 권장값 (실습용 단축 버전):
    Number of users : 150
    Spawn rate      : 10
    Run time        : 10분 이상 (실제 운영 환경에서는 4~8시간)

  CLI로 시간 고정 실행:
    locust -f 04_soak_test.py --host=http://localhost:8080 \\
           --headless -u 150 -r 10 --run-time 10m

확인 포인트:
  - 초반(1분) vs 후반(9분) 응답시간을 비교한다.
  - 시간이 지나도 응답시간이 일정하게 유지되는가?
  - 에러율이 테스트 중반 이후 슬금슬금 올라가지는 않는가?
    (메모리 누수 패턴 — 처음에는 정상, 시간 지나면 악화)

참고:
  실제 내구성 테스트는 4~8시간 실행이 권장된다.
  강의에서는 10분으로 단축하여 패턴만 확인한다.
"""

from locust import HttpUser, task, between, LoadTestShape
import random


# ── 부하 패턴 정의 ──────────────────────────────────────────────────────────

class SoakTestShape(LoadTestShape):
    """
    내구성 테스트 패턴.
    Ramp-up 후 일정 사용자를 장시간 유지한다.
    실습용으로 10분(600초) 기준으로 작성되었다.
    """

    # (경과 시간 초, 목표 사용자 수, 초당 spawn 수)
    stages = [
        (60,  150, 10),   # 0~60초   : Ramp-up (150명까지 점진적 증가, 한계 이하)
        (540, 150, 1),    # 60~540초 : Steady  (150명 유지, 약 8분)
        (600, 0,   20),   # 540~600초: Ramp-down
    ]

    def tick(self):
        run_time = self.get_run_time()
        for end_time, users, spawn_rate in self.stages:
            if run_time < end_time:
                return users, spawn_rate
        return None


# ── 가상 사용자 정의 ────────────────────────────────────────────────────────

class SoakTestUser(HttpUser):
    """내구성 테스트용 가상 사용자 — 장시간 꾸준한 요청"""

    # 실제 사용자처럼 여유 있는 Think Time
    wait_time = between(2, 5)

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

    @task(1)
    def 상품_생성(self):
        payload = {
            "name": f"내구성 테스트 상품 {random.randint(1, 9999)}",
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
