FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Non-root runtime user (reduces blast radius if the process is compromised)
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 7860

# FORWARDED_ALLOW_IPS:
#   HF Spaces / Render sit behind a trusted edge and do not publish a stable
#   proxy CIDR whitelist — '*' is the platform-correct default.
#   Override for local/dev: FORWARDED_ALLOW_IPS=127.0.0.1
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-7860} --proxy-headers --forwarded-allow-ips=${FORWARDED_ALLOW_IPS:-*}"]
