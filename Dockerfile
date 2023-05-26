FROM python:3-slim
RUN apt-get -y update \
    && apt-get -y --no-install-recommends install cron gosu \
    && rm -rf /var/lib/apt/lists/*
COPY . /dist
RUN pip install --no-cache-dir /dist
ENTRYPOINT [ "/dist/scripts/docker-entrypoint.sh" ]