#!/bin/bash
#
# cvdupdate & cron entrypoint
#

set -e

SCRIPT_PATH=$(readlink -f "$0")

if [ $# -eq 0  ]; then
    echo "ClamAV Private Database Mirror Updater Cron ${SCRIPT_PATH}"

    sudo cron -f
else
    echo "ClamAV Private Database Mirror Updater "$@" ${SCRIPT_PATH}"

    cvdupdate "$@"
fi
