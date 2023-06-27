FROM python:3.9-slim-bullseye as build

ADD . /mege-data-collector

WORKDIR /mege-data-collector

RUN apt-get update -y \
    && apt-get install -y build-essential libpq-dev git \
    && pip install virtualenv \
    && virtualenv /opt/mege-data-collector/venv \
    && . /opt/mege-data-collector/venv/bin/activate \
    && pip install . \
    && pip install gunicorn

FROM python:3.9-slim-bullseye

COPY --from=build /opt/mege-data-collector /opt/mege-data-collector

ADD entrypoint.sh /bin/entrypoint.sh

RUN apt-get update -y \
    && apt-get install -y libpq5\
    && apt-get clean \
    && mkdir -p /opt/mege-data-collector/data \
    && groupadd -g 5000 -r megedc \
    && useradd -d /opt/mege-data-collector -r -M -u 5000 -g megedc megedc \
    && chown -R megedc:megedc /opt/mege-data-collector/data \
    && chmod +x /bin/entrypoint.sh

WORKDIR /opt/mege-data-collector/data
ENV PYTHON_VENV_PATH /opt/mege-data-collector/venv
USER megedc:megedc

EXPOSE 8000

ENTRYPOINT ["entrypoint.sh"]