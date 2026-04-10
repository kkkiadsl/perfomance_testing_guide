/**
 * k6 성능 테스트 샘플 스크립트
 *
 * 실행 방법:
 *   docker compose run --rm k6 run /scripts/example.js
 *
 * 환경 변수로 대상 URL 변경:
 *   docker compose run --rm -e TARGET_URL=http://my-server k6 run /scripts/example.js
 */

import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';

// ─── 커스텀 메트릭 정의 ──────────────────────────────────────────────────
const errorRate = new Rate('custom_error_rate');        // 에러율
const mainPageDuration = new Trend('main_page_duration'); // 메인 페이지 응답 시간
const apiCallCount = new Counter('api_call_count');     // API 호출 횟수

// ─── 테스트 설정 ─────────────────────────────────────────────────────────
export const options = {
  // 시나리오: 단계적 부하 증가 (Ramp-up)
  stages: [
    { duration: '30s', target: 10 },  // 30초 동안 10명까지 증가
    { duration: '1m',  target: 1000 },  // 1분 동안 50명까지 증가
    { duration: '2m',  target: 1000 },  // 2분 동안 50명 유지
    { duration: '30s', target: 0  },  // 30초 동안 0명으로 감소
  ],

  // 성능 임계값 (이 기준을 넘으면 테스트 실패 처리)
  thresholds: {
    http_req_failed:           ['rate<0.01'],          // HTTP 에러율 1% 미만
    http_req_duration:         ['p(95)<500'],          // 95%tile 응답시간 500ms 미만
    http_req_duration:         ['p(99)<1000'],         // 99%tile 응답시간 1000ms 미만
    custom_error_rate:         ['rate<0.05'],          // 커스텀 에러율 5% 미만
    main_page_duration:        ['p(90)<300'],          // 메인 페이지 90%tile 300ms 미만
  },
};

// ─── 테스트 대상 URL ──────────────────────────────────────────────────────
// 환경 변수 TARGET_URL 이 없으면 기본값 사용
const BASE_URL = __ENV.TARGET_URL || 'http://host.docker.internal';

// ─── 기본 헤더 설정 ───────────────────────────────────────────────────────
const headers = {
  'Content-Type': 'application/json',
  'Accept': 'application/json',
};

// ─── 메인 테스트 함수 (가상 사용자마다 반복 실행) ───────────────────────────
export default function () {
  // 그룹으로 시나리오를 묶으면 Grafana에서 구분하여 확인 가능
  group('메인 페이지 조회', () => {
    const res = http.get(`${BASE_URL}/`, { headers });

    // 응답 검증
    const passed = check(res, {
      '상태코드 200': (r) => r.status === 200,
      '응답시간 500ms 미만': (r) => r.timings.duration < 500,
    });

    // 커스텀 메트릭 기록
    errorRate.add(!passed);
    mainPageDuration.add(res.timings.duration);

    sleep(1); // 1초 대기
  });

  group('API 호출', () => {
    // GET 요청 예시
    const listRes = http.get(`${BASE_URL}/api/items`, { headers });
    apiCallCount.add(1);

    check(listRes, {
      '목록 조회 성공': (r) => r.status === 200,
    });

    sleep(0.5);

    // POST 요청 예시
    const payload = JSON.stringify({
      name: `테스트 아이템 ${Date.now()}`,
      value: Math.floor(Math.random() * 100),
    });

    const createRes = http.post(`${BASE_URL}/api/items`, payload, { headers });
    apiCallCount.add(1);

    check(createRes, {
      '아이템 생성 성공': (r) => r.status === 200 || r.status === 201,
    });

    sleep(1);
  });
}

// ─── 테스트 시작 시 1회 실행 ──────────────────────────────────────────────
export function setup() {
  console.log(`테스트 대상 서버: ${BASE_URL}`);
  console.log('테스트를 시작합니다...');
}

// ─── 테스트 종료 후 1회 실행 ─────────────────────────────────────────────
export function teardown(data) {
  console.log('테스트가 완료되었습니다.');
}
