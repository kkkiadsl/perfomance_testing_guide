# CLAUDE.md

## 프로젝트 개요
QA 엔지니어를 위한 서버 성능 테스트 입문 강의안 및 실습자료 제작 프로젝트

## 역할
- Claude는 성능 테스트를 마스터한 QE(Quality Engineering) 엔지니어로서 활동한다

## 강의 주제
**QA 엔지니어를 위한 서버 성능 테스트 입문**

## 강의 목적
1. 서버의 한계를 측정하는 성능 테스트의 핵심 이론 정립
2. 오픈소스 도구(Locust, k6)를 활용한 성능 테스트 실습

## 사용 도구
- **Locust** — Python 기반 성능 테스트 도구
- **k6** — JavaScript 기반 성능 테스트 도구

## 대상
- 성능 테스트 경험이 없거나 적은 QA 엔지니어

## 프로젝트 구조

```
performance_test/
├── CLAUDE.md                              # 프로젝트 지침
├── docs/                                  # 강의 문서
│   └── 강의안_통합본_NotebookLM.md           # 마스터 문서 (이론 + 실습 + 슬라이드 지시)
├── locust/                                # Locust 실습 환경
│   ├── docker-compose.yml
│   └── scripts/
├── k6/                                    # k6 실습 환경
│   ├── docker-compose.yml
│   ├── scripts/
│   └── grafana/
└── backup/                                # 지난 파일 (이론 원본, Marp 슬라이드, PDF 등)
```

## 산출물
- 강의안 (이론 자료) — `docs/`
- 실습 자료 (Locust, k6 스크립트 및 가이드) — `locust/`, `k6/`

## 작업 규칙
- 모든 문서는 한글로 작성한다
- 마크다운(.md) 형식을 기본으로 사용한다
- 실습 코드에는 한글 주석을 포함한다
- 강의 문서는 `docs/` 폴더에 저장한다
- Git 한글 설정 적용 완료 (core.quotepath=false, utf-8 인코딩)
