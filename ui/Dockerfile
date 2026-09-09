FROM python:3.12-slim
RUN pip install --no-cache-dir fastapi uvicorn pyyaml jinja2 python-multipart httpx
WORKDIR /opt/agentbox/ui
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
