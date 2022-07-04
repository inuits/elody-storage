### Base stage
FROM python:3.10-slim AS base-stage

ENV FLASK_APP=app.py

RUN apt-get update && apt-get install -y libmagic1 && apt-get clean && \
        adduser --disabled-password --home /app --shell /bin/bash app

USER app
WORKDIR /app

COPY docker/entrypoint*.sh /
COPY docker/run-tests.sh /
COPY docker/test-coverage.sh /
COPY requirements.txt ./
COPY requirements_dev.txt ./

RUN echo "export PATH=${PATH}:/app/.local/bin" >> .bashrc

ENTRYPOINT ["/entrypoint.sh"]

### Development stage
FROM base-stage AS development-stage

ENV APP_ENV=dev

COPY docker/pip.conf /etc

RUN pip install --no-cache-dir -r requirements.txt -r requirements_dev.txt

EXPOSE 5000

### Build stage
FROM base-stage AS build-stage

COPY docker/pip.conf /etc
COPY api ./api

RUN pip install --no-cache-dir -r requirements.txt

### Production stage
FROM build-stage AS production-stage

ENV APP_ENV=prod
ENV GUNICORN_CMD_ARGS="--workers=3"

COPY --from=build-stage /app /app

EXPOSE 8000
