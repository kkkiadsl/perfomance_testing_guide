"""
실습 1 — 부하 테스트 (Load Test)
=====================================================
목적: 예상 트래픽 수준에서 서버가 안정적으로 동작하는지 확인한다.
패턴: 일정한 사용자 수를 유지 (수평선 형태)

실행 방법:
  locust -f 01_load_test.py --host=http://localhost:8080

Web UI 설정 권장값:
  Number of users : 20
  Spawn rate      : 5
  (Duration은 UI에서 직접 Stop 하거나 --run-time 3m 옵션 사용)

확인 포인트:
  - 응답시간이 안정적으로 유지되는가?
  - 에러율이 1% 이하인가?
  - 각 API 호출 비율이 @task 가중치대로 나오는가?
"""

from locust import HttpUser, task, between
import random


class LoadTestUser(HttpUser):
    """
    일반 사용자 행동을 시뮬레이션한다.
    상품 목록 조회 → 상세 조회 → 가끔 생성 패턴
    """

    # Think Time: 요청 사이 1~3초 대기 (실제 사용자처럼)
    wait_time = between(1, 3)

    @task(5)
    def 상품_목록_조회(self):
        """가장 빈번한 요청 — 가중치 5"""
        with self.client.get(
            "/api/items",
            name="[목록] GET /api/items",
            catch_response=True
        ) as res:
            if res.status_code == 200:
                res.success()
            else:
                res.failure(f"예상치 못한 상태코드: {res.status_code}")

    @task(3)
    def 상품_상세_조회(self):
        """상품 상세 조회 — 가중치 3"""
        item_id = random.randint(1, 100)
        with self.client.get(
            f"/api/items/{item_id}",
            name="[상세] GET /api/items/[id]",   # 동적 URL은 name으로 그룹핑
            catch_response=True
        ) as res:
            if res.status_code in [200, 404]:    # 범위 초과 ID는 404가 정상
                res.success()
            else:
                res.failure(f"예상치 못한 상태코드: {res.status_code}")

    @task(1)
    def 상품_생성(self):
        """상품 생성 (POST) — 가중치 1 (가장 드물게)"""
        payload = {
            "name": f"테스트 상품 {random.randint(1, 9999)}",
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

    @task(1)
    def 헬스체크(self):
        """서버 상태 확인"""
        self.client.get("/health", name="[헬스] GET /health")
