# xk6-output-influxdb 확장이 포함된 k6 커스텀 빌드
FROM grafana/xk6:latest AS builder
RUN xk6 build \
    --with github.com/grafana/xk6-output-influxdb \
    --output /tmp/k6

FROM alpine:3.18
RUN apk add --no-cache ca-certificates
COPY --from=builder /tmp/k6 /usr/bin/k6
ENTRYPOINT ["k6"]
