"""
실습 3 — 스파이크 테스트 (Spike Test)
=====================================================
목적: 갑작스러운 트래픽 급증에 서버가 어떻게 반응하는지 확인한다.
패턴: 소수 사용자 → 순간 급증 → 유지 → 급감 → 회복 확인

실행 방법:
  locust -f 03_spike_test.py --host=http://localhost:8080

  Web UI 접속: http://localhost:8089
  Start 버튼 클릭 후 자동 진행

부하 단계:
  0~ 30초 :   5명 (안정적인 기준선)
  30~ 40초:  50명 (스파이크! 10초 만에 10배로 급증)
  40~ 80초:  50명 (스파이크 유지 — 서버가 버티는지 관찰)
  80~100초:   5명 (급감 — 회복되는지 관찰)
  100~130초:  5명 (회복 후 안정 확인)
  130~140초:  0명 (종료)

확인 포인트:
  - 스파이크 구간(30~40초)에서 응답시간이 얼마나 치솟는가?
  - 에러가 발생하는가? 어떤 에러인가?
  - 스파이크가 줄어든 후 서버가 정상으로 회복되는가?
  - 회복 시간은 얼마나 걸리는가?
"""

from locust import HttpUser, task, between, LoadTestShape
import random


# ── 부하 패턴 정의 ──────────────────────────────────────────────────────────

class SpikeTestShape(LoadTestShape):
    """
    스파이크 테스트 패턴.
    30~40초 구간에서 5명 → 50명으로 순간 급증한다.
    """

    # (경과 시간 초, 목표 사용자 수, 초당 spawn 수)
    stages = [
        (30,  5,  2),     # 0~30초   : 기준선 (안정)
        (40,  50, 50),    # 30~40초  : 스파이크 (10초 만에 50명)
        (80,  50, 1),     # 40~80초  : 스파이크 유지
        (100, 5,  30),    # 80~100초 : 급감
        (130, 5,  1),     # 100~130초: 회복 후 안정 확인
        (140, 0,  30),    # 종료
    ]

    def tick(self):
        run_time = self.get_run_time()
        for end_time, users, spawn_rate in self.stages:
            if run_time < end_time:
                return users, spawn_rate
        return None


# ── 가상 사용자 정의 ────────────────────────────────────────────────────────

class SpikeTestUser(HttpUser):
    """스파이크 테스트용 가상 사용자 — 실제 이벤트 오픈 시 사용자 행동을 모사"""

    # 스파이크 상황: 사용자가 바쁘게 요청을 보낸다 (Think Time 짧게)
    wait_time = between(0.5, 1.5)

    @task(5)
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

    @task(4)
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
        """스파이크 시 결제/생성 요청도 함께 몰린다"""
        payload = {
            "name": f"스파이크 테스트 상품 {random.randint(1, 9999)}",
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
