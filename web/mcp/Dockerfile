# Hosted MCP endpoint for the NAS deployment, served at https://<site>/mcp by nginx.
# Built locally by dev.sh (`./dev.sh nas deploy`) and loaded onto the NAS.
#
# Holds NO token: every caller sends their own `Authorization: Bearer jyd_…`,
# forwarded to the backend as-is. Never give this container JYOTIR_API_TOKEN.
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py .
RUN useradd --system --no-create-home mcp
USER mcp
ENV MCP_TRANSPORT=http \
    MCP_HTTP_HOST=0.0.0.0 \
    MCP_HTTP_PORT=8765 \
    JYOTIR_API_URL=http://backend:8000 \
    PYTHONUNBUFFERED=1
EXPOSE 8765
CMD ["python", "server.py"]
