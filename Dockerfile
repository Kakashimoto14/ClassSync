FROM python:3.12-slim
ARG SERVICE=all
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080 PYTHONPATH=/app
WORKDIR /app
COPY packages ./packages
COPY services ./services
COPY scripts/container_entrypoint.py ./scripts/container_entrypoint.py
COPY scripts/render_entrypoint.py ./scripts/render_entrypoint.py
COPY scripts/linux_runtime_probe.py scripts/registration_local_qualification.py ./scripts/
RUN case "$SERVICE" in gateway|academic|scheduling|all) ;; *) exit 1 ;; esac \
    && if [ "$SERVICE" = gateway ] || [ "$SERVICE" = all ]; then \
         apt-get update && apt-get install -y --no-install-recommends \
           tesseract-ocr tesseract-ocr-eng poppler-utils fonts-dejavu-core \
           && rm -rf /var/lib/apt/lists/*; \
       fi \
    && python -m pip install --no-cache-dir pip==26.2.2 \
    && if [ "$SERVICE" = all ]; then \
         for service in gateway academic scheduling notification; do \
           (cd "/app/services/$service" && \
             python -m pip install --no-cache-dir -r requirements.txt) || exit 1; \
         done; \
       else \
         cd "/app/services/$SERVICE" && \
         python -m pip install --no-cache-dir -r requirements.txt; \
       fi \
    && useradd --uid 10001 --create-home classsync
ENV CLASSSYNC_SERVICE=$SERVICE CLASSSYNC_ENV=production ENABLE_SCHEDULING_SANDBOX=false \
    ENABLE_TEST_IDENTITY_ADAPTERS=false ALLOW_UNAUTHENTICATED_DEVELOPMENT=false \
    COURSE_CLOUD_ENABLED=false
USER classsync
EXPOSE 8080
CMD ["python", "scripts/container_entrypoint.py"]
