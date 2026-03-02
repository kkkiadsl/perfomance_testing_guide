"""
Locust 성능 테스트 샘플 스크립트

실행 방법:
  1. docker compose up 으로 Locust 실행
  2. http://localhost:8089 접속
  3. 목표 서버 URL, 동시 사용자 수, Ramp-up 설정 후 테스트 시작

테스트 대상:
  - HOST 환경변수 또는 웹 UI에서 설정한 서버
"""

from locust import HttpUser, task, between, constant_pacing
from locust import events
import json
import random


class WebsiteUser(HttpUser):
    """
    일반적인 웹 사이트 사용자 행동을 시뮬레이션하는 클래스
    """

    # 각 태스크 사이 대기 시간 (초): 1~3초 랜덤 대기
    wait_time = between(1, 3)

    def on_start(self):
        """
        가상 사용자 시작 시 실행 (로그인 등 초기화 작업)
        """
        # 예시: 로그인 처리
        # response = self.client.post("/login", json={
        #     "username": "test_user",
        #     "password": "test_password"
        # })
        pass

    @task(3)  # weight=3: 다른 태스크 대비 3배 빈도로 실행
    def get_main_page(self):
        """
        메인 페이지 조회 (가장 빈번한 요청)
        """
        with self.client.get(
            "/",
            name="GET /",           # Locust UI에 표시될 요청 이름
            catch_response=True     # 응답 검증을 위해 명시적 catch 사용
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"예상치 못한 상태 코드: {response.status_code}")

    @task(2)
    def get_items_list(self):
        """
        상품 목록 조회
        """
        self.client.get("/api/items", name="목록 조회")

    @task(1)
    def get_item_detail(self):
        """
        상품 상세 조회 (랜덤 ID 사용)
        """
        item_id = random.randint(1, 100)
        self.client.get(
            f"/api/items/{item_id}",
            name="상세 조회 /api/items/[id]"   # 동적 URL은 name으로 그룹핑
        )

    @task(1)
    def create_item(self):
        """
        상품 생성 요청 (POST)
        """
        payload = {
            "name": f"테스트 상품 {random.randint(1, 1000)}",
            "value": random.randint(1, 500)
        }
        with self.client.post(
            "/api/items",
            json=payload,
            name="상품 생성",
            catch_response=True
        ) as response:
            if response.status_code in [200, 201]:
                response.success()
            else:
                response.failure(f"생성 실패: {response.status_code}")


class HeavyUser(HttpUser):
    """
    높은 부하를 생성하는 사용자 클래스 (API 집중 테스트용)
    """

    # 고정 간격으로 요청 발송 (초당 요청 수 일정하게 유지)
    wait_time = constant_pacing(1)

    # 이 클래스의 생성 비율 (WebsiteUser 대비 낮게 설정)
    weight = 1

    @task
    def api_health_check(self):
        """
        헬스체크 엔드포인트 반복 호출
        """
        self.client.get("/health", name="헬스체크")

    @task
    def slow_endpoint(self):
        """
        지연 엔드포인트 호출 (타임아웃 테스트용)
        """
        self.client.get("/api/slow?delay=0.5", name="지연 응답 /api/slow")
