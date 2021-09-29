### Base stage
FROM python:3.9-slim AS base-stage

RUN adduser --no-create-home --disabled-password --home /app --shell /bin/ash app
WORKDIR /app

COPY docker/entrypoint*.sh /
COPY requirements.txt ./
COPY requirements_dev.txt ./
COPY docker/run-tests.sh /
COPY docker/test-coverage.sh /

RUN mkdir downloads
RUN chown -R app:app downloads

ENTRYPOINT ["/entrypoint.sh"]

### Development stage
FROM base-stage AS development-stage

ARG APP_ENV

ENV APP_ENV=${APP_ENV}

ARG PIPENV_USERNAME
ARG PIPENV_PASSWORD

RUN pip install -r requirements.txt -i "https://${PIPENV_USERNAME}:${PIPENV_PASSWORD}@nexus.inuits.eu/repository/python/simple" \
    && pip install -r requirements_dev.txt -i "https://${PIPENV_USERNAME}:${PIPENV_PASSWORD}@nexus.inuits.eu/repository/python/simple"

### Build stage
FROM base-stage AS build-stage

COPY . ./
RUN chown -R app:app downloads

ARG PIPENV_USERNAME
ARG PIPENV_PASSWORD

RUN pip install -r requirements.txt -i "https://${PIPENV_USERNAME}:${PIPENV_PASSWORD}@nexus.inuits.eu/repository/python/simple"

### Production stage
FROM build-stage AS production-stage

ENV GUNICORN_CMD_ARGS="--workers=3"

USER app
