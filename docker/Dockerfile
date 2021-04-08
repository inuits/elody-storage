### Base stage
FROM python:3.9-slim AS base-stage

RUN adduser --no-create-home --disabled-password --home /app --shell /bin/ash app
WORKDIR /app

COPY docker/entrypoint*.sh /
COPY requirements.txt ./

RUN mkdir downloads
RUN chown -R app:app downloads

ENTRYPOINT ["/entrypoint.sh"]

### Development stage
FROM base-stage AS development-stage

ARG APP_ENV

ENV APP_ENV=${APP_ENV}

RUN pip install -r requirements.txt

### Build stage
FROM base-stage AS build-stage

COPY . ./
RUN chown -R app:app downloads

RUN pip install -r requirements.txt

### Production stage
FROM build-stage AS production-stage

ENV GUNICORN_CMD_ARGS="--workers=3"

USER app
