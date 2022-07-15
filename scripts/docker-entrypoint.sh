#!/bin/bash
if [ $# -eq 0 ]; then
    set -e
    SCRIPT_PATH=$(readlink -f "$0")
    echo "ClamAV Private Database Mirror Updater Cron ${SCRIPT_PATH}"

    # Add crontab entry and start cron
    echo "Adding crontab entry"
    crontab -l | {
        cat
        echo "${CRON:-"30 */4 * * *"} /usr/local/bin/cvdupdate update >/proc/1/fd/1 2>/proc/1/fd/2"
        echo "@reboot /usr/local/bin/cvdupdate update >/proc/1/fd/1 2>/proc/1/fd/2"
    } | crontab -
    cron -f
else
    exec "$@"
fi
