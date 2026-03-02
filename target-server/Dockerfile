FROM python:3.11-slim

WORKDIR /app

# 의존 패키지 설치
RUN pip install --no-cache-dir fastapi uvicorn[standard] pydantic

# 애플리케이션 복사
COPY app.py .

# 포트 노출
EXPOSE 8080

# 서버 실행
# workers=1 고정: 메트릭 수집기가 인메모리 상태를 사용하므로
# 멀티 프로세스 시 각 프로세스가 독립된 메트릭을 가짐 → 대시보드 집계 불일치 발생
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
