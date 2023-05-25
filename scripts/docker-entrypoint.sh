#!/bin/bash
USER_ID="${USER_ID:-0}"
SCRIPT_PATH=$(readlink -f "$0")
echo "ClamAV Private Database Mirror Updater Cron ${SCRIPT_PATH}"
if [ "${USER_ID}" -ne "0" ]; then
    echo "Creating user with ID ${USER_ID}"
    useradd --create-home --home-dir /cvdupdate --uid "${USER_ID}" cvdupdate
    chown -R "${USER_ID}" /cvdupdate
    gosu cvdupdate cvdupdate config set --logdir /cvdupdate/logs
    gosu cvdupdate cvdupdate config set --dbdir /cvdupdate/database
else
    mkdir -p /cvdupdate/{logs,database}
    cvdupdate config set --logdir /cvdupdate/logs
    cvdupdate config set --dbdir /cvdupdate/database
fi

if [ $# -eq 0 ]; then
    set -e

    echo "Adding crontab entry"
    if [ "${USER_ID}" -ne "0" ]; then
        crontab -l | {
            cat
            echo "${CRON:-"30 */4 * * *"} /usr/sbin/gosu cvdupdate /usr/local/bin/cvdupdate update >/proc/1/fd/1 2>/proc/1/fd/2"
            echo "@reboot /usr/sbin/gosu cvdupdate /usr/local/bin/cvdupdate update >/proc/1/fd/1 2>/proc/1/fd/2"
        } | crontab -
    else
        crontab -l | {
            cat
            echo "${CRON:-"30 */4 * * *"} /usr/local/bin/cvdupdate update >/proc/1/fd/1 2>/proc/1/fd/2"
            echo "@reboot /usr/local/bin/cvdupdate update >/proc/1/fd/1 2>/proc/1/fd/2"
        } | crontab -
    fi
    cron -f
else
    if [ "${USER_ID}" -ne "0" ]; then
        exec gosu cvdupdate "$@"
    else
        exec "$@"
    fi
fi
