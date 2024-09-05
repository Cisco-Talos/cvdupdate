FROM python:3.12.0b1-slim

WORKDIR /cvdupdate

RUN apt-get -y update && \
    apt-get -y --no-install-recommends install cron sudo && \
    apt-get -y clean && \
    rm -rf /var/lib/apt/lists/* && \
    useradd --no-create-home --home-dir /cvdupdate --uid 1000 cvdupdate && \
    echo '30 */4 * * * /usr/local/bin/cvdupdate update > /proc/1/fd/1 2>&1' >> /etc/cron.d/cvdupdate && \
    echo '@reboot /usr/local/bin/cvdupdate update >/proc/1/fd/1 2>/proc/1/fd/2' >> /etc/cron.d/cvdupdate && \
    crontab -u cvdupdate /etc/cron.d/cvdupdate && \
    echo "cvdupdate\tALL=(ALL:ALL) NOPASSWD: /usr/sbin/cron" >> /etc/sudoers

COPY . .

RUN pip install --no-cache-dir . && \
    chown cvdupdate:cvdupdate -R /cvdupdate

USER cvdupdate:cvdupdate

RUN cvd update

ENTRYPOINT [ "./scripts/docker-entrypoint.sh" ]
