# The engine needs pg_dump/pg_restore of the SAME major version as the CMS database (PostgreSQL 16),
# so it is built on the official postgres image rather than python:slim.
FROM postgres:18-alpine AS runtime
RUN apk add --no-cache python3 py3-psycopg py3-boto3
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 BDR_BACKUP_DIR=/backups
WORKDIR /srv/engine
COPY bdr_engine ./bdr_engine
# The postgres image's unprivileged "postgres" user (uid 70) runs the engine; it never needs root.
RUN mkdir -p /backups && chown postgres:postgres /backups
USER postgres
ENTRYPOINT ["python3", "-m", "bdr_engine"]
CMD ["schedule"]

# ---- test image: runtime + pytest + the test suite ----
FROM runtime AS test
USER root
RUN apk add --no-cache py3-pytest
COPY pyproject.toml ./
COPY tests ./tests
USER postgres
ENTRYPOINT []
CMD ["python3", "-m", "pytest", "-q", "-p", "no:cacheprovider"]
