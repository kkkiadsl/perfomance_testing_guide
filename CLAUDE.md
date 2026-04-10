# CLAUDE.md

## 프로젝트 개요
QA 엔지니어를 위한 서버 성능 테스트 입문 강의안 및 실습자료 제작 프로젝트

## 역할
- Claude는 성능 테스트를 마스터한 QE(Quality Engineering) 엔지니어로서 활동한다

## 강의 주제
**QA 엔지니어를 위한 서버 성능 테스트 입문**

## 강의 목적
1. 서버의 한계를 측정하는 성능 테스트의 핵심 이론 정립
2. Locust(Python)를 활용한 4가지 성능 테스트 유형 실습

## 사용 도구
- **Locust** — Python 기반 성능 테스트 도구 (메인 실습 도구)
- **k6** — JavaScript 기반 성능 테스트 도구 (부록 — 심화 학습용)
- **Docker** — 컨테이너 환경 (부록 — 분산 테스트 심화용)

## 대상
- 성능 테스트 경험이 없거나 적은 QA 엔지니어

## 프로젝트 구조

```
performance_test/
├── CLAUDE.md                              # 프로젝트 지침
├── docs/
│   └── 강의안_통합본.md                    # 마스터 문서 (이론 + 실습 + 슬라이드 지시 + 부록)
├── locust/                                # Locust 실습 환경 (메인)
│   ├── README.md                          # 로컬 설치 및 실행 가이드
│   ├── docker-compose.yml                 # 부록: Docker 분산 환경
│   └── scripts/
│       ├── locustfile.py                  # 빠른 동작 확인용 샘플
│       ├── 01_load_test.py                # 부하 테스트
│       ├── 02_stress_test.py              # 스트레스 테스트
│       ├── 03_spike_test.py               # 스파이크 테스트
│       ├── 04_soak_test.py                # 내구성 테스트
│       └── 05_api_practice.py             # API별 개별 호출 실습
├── target-server/                         # 성능 테스트 대상 FastAPI 서버
│   ├── app.py
│   └── docker-compose.yml
├── k6/                                    # 부록: k6 심화 자료
│   ├── docker-compose.yml
│   ├── scripts/
│   └── grafana/
└── backup/                                # 지난 파일 (이론 원본, Marp 슬라이드, PDF 등)
```

## 산출물
- 강의안 — `docs/강의안_통합본.md` (이론 + 실습 + 부록 통합)
- 실습 스크립트 — `locust/scripts/01~05_*.py`
- 환경 가이드 — `locust/README.md`

## 강의 구성 방침
- 본문: Locust + 로컬 Python 환경 (Docker 불필요)
- 부록 A: k6 심화 (JavaScript 기반 자동화)
- 부록 B: Docker 심화 (분산 테스트, k6+Grafana 스택)

## 작업 규칙
- 모든 문서는 한글로 작성한다
- 마크다운(.md) 형식을 기본으로 사용한다
- 실습 코드에는 한글 주석을 포함한다
- 강의 문서는 `docs/` 폴더에 저장한다
- Git 한글 설정 적용 완료 (core.quotepath=false, utf-8 인코딩)
