FROM python:3.12-slim
ARG SERVICE=gateway
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080
WORKDIR /app
COPY packages ./packages
COPY services ./services
COPY scripts/container_entrypoint.py ./scripts/container_entrypoint.py
COPY scripts/linux_runtime_probe.py scripts/registration_local_qualification.py ./scripts/
RUN case "$SERVICE" in gateway|academic|scheduling) ;; *) exit 1 ;; esac \
    && if [ "$SERVICE" = gateway ]; then \
         apt-get update && apt-get install -y --no-install-recommends \
           tesseract-ocr tesseract-ocr-eng poppler-utils fonts-dejavu-core \
           && rm -rf /var/lib/apt/lists/*; \
       fi \
    && python -m pip install --no-cache-dir pip==26.2.2 \
    && cd "/app/services/$SERVICE" \
    && python -m pip install --no-cache-dir -r requirements.txt \
    && useradd --uid 10001 --create-home classsync
ENV CLASSSYNC_SERVICE=$SERVICE CLASSSYNC_ENV=production ENABLE_SCHEDULING_SANDBOX=false
USER classsync
EXPOSE 8080
CMD ["python", "scripts/container_entrypoint.py"]
