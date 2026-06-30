FROM python:3.13-slim-bookworm AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

COPY requirements.txt ./
RUN python -m pip wheel --wheel-dir /wheels -r requirements.txt


FROM python:3.13-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_SETTINGS_MODULE=fuelops.settings

WORKDIR /app

RUN groupadd --system --gid 10001 fuelops \
    && useradd --system --uid 10001 --gid fuelops --home-dir /app --shell /usr/sbin/nologin fuelops

COPY --from=builder /wheels /wheels
RUN python -m pip install /wheels/* \
    && rm -rf /wheels

COPY --chown=fuelops:fuelops . /app
RUN chmod +x /app/docker/entrypoint.sh \
    && mkdir -p /app/data /app/staticfiles /app/media \
    && chown -R fuelops:fuelops /app/data /app/staticfiles /app/media

USER fuelops

EXPOSE 8000

ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["gunicorn", "fuelops.wsgi:application", "--bind", "0.0.0.0:8000", "--no-control-socket"]
