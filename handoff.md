# 작업 기록 (2026-02-21)

## 1. Grafana 포트 변경 (3000 → 3001)

**이유:** 호스트의 3000 포트가 이미 사용 중

**변경 파일:**
- `k6/docker-compose.yml` — 포트 매핑 `"3000:3000"` → `"3001:3000"`
- `docs/강의안_통합본_NotebookLM.md` — 접속 URL `localhost:3000` → `localhost:3001`

---

## 2. k6 InfluxDB 출력을 xk6-influxdb 방식으로 전환

**이유:** `grafana/k6:latest`에서 기존 `--out influxdb` (v1 내장 출력)가 제거됨. 최신 방식인 xk6-output-influxdb 확장 사용으로 전환.

**변경 내용:**

### 2-1. k6 커스텀 이미지 빌드 (`k6/Dockerfile` 신규 생성)
- `grafana/xk6`로 xk6-output-influxdb 확장을 포함한 k6 바이너리 빌드
- 빌드 출력 경로: `/tmp/k6` (루트 경로 권한 문제 회피)

### 2-2. docker-compose.yml (k6 서비스)
| 항목 | 변경 전 | 변경 후 |
|---|---|---|
| image | `grafana/k6:latest` | `build: .` (커스텀 Dockerfile) |
| K6_OUT | `influxdb=http://influxdb:8086/k6` | `xk6-influxdb=http://influxdb:8086` |
| K6_INFLUXDB_BUCKET | (없음) | `k6/autogen` |

### 2-3. 강의안 (`docs/강의안_통합본_NotebookLM.md`)
- k6 실행 명령어를 `--out xk6-influxdb=...` 형식으로 업데이트

---

## 3. Grafana 데이터소스 uid 불일치 수정

**증상:** k6 → InfluxDB 데이터 전송은 정상이나, Grafana 대시보드에 결과가 표시되지 않음

**원인:** 대시보드 JSON이 `"uid": "influxdb"`를 참조하는데, 데이터소스 프로비저닝 파일에 uid가 미지정되어 Grafana가 자동 생성한 uid와 불일치

**수정:** `k6/grafana/provisioning/datasources/influxdb.yaml`에 `uid: influxdb` 추가

**주의사항:** 기존 Grafana 볼륨에 캐시된 설정과 충돌할 수 있으므로, 볼륨 초기화 후 재시작 필요:
```bash
docker compose down && docker volume rm k6_grafana-data && docker compose up -d influxdb grafana
```

---

## 변경된 파일 목록

| 파일 | 변경 유형 |
|---|---|
| `k6/Dockerfile` | 신규 생성 |
| `k6/docker-compose.yml` | 수정 (포트, k6 이미지, 환경변수) |
| `k6/grafana/provisioning/datasources/influxdb.yaml` | 수정 (uid 추가) |
| `docs/강의안_통합본_NotebookLM.md` | 수정 (포트, k6 명령어) |
