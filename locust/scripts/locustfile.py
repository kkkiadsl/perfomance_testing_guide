"""
Locust 실습 스크립트 — 진입점 안내
=====================================================

이 파일은 빠른 동작 확인용 샘플이다.
실제 실습은 번호가 붙은 스크립트를 사용한다.

실습 스크립트 목록:
  01_load_test.py   — 부하 테스트  : 예상 트래픽 안정성 확인
  02_stress_test.py — 스트레스 테스트: 계단식 증가로 한계점 탐색
  03_spike_test.py  — 스파이크 테스트: 순간 급증 대응력 확인
  04_soak_test.py   — 내구성 테스트 : 장시간 운영 안정성 확인
  05_api_practice.py— API별 실습   : 엔드포인트별 개별 호출 및 시나리오

실행 방법 (locust/scripts 디렉터리에서):
  locust -f 01_load_test.py --host=http://localhost:8080

Web UI: http://localhost:8089
"""

from locust import HttpUser, task, between
import random


class QuickStartUser(HttpUser):
    """
    빠른 동작 확인용 샘플 사용자.
    주요 API를 가중치에 따라 랜덤으로 호출한다.
    """

    wait_time = between(1, 3)

    @task(3)
    def 상품_목록_조회(self):
        self.client.get("/api/items", name="GET /api/items")

    @task(2)
    def 상품_상세_조회(self):
        item_id = random.randint(1, 100)
        self.client.get(f"/api/items/{item_id}", name="GET /api/items/[id]")

    @task(1)
    def 상품_생성(self):
        payload = {
            "name": f"샘플 상품 {random.randint(1, 9999)}",
            "value": random.randint(100, 50000)
        }
        self.client.post("/api/items", json=payload, name="POST /api/items")

    @task(1)
    def 헬스체크(self):
        self.client.get("/health", name="GET /health")
