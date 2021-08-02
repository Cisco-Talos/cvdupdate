from threading import Event, Thread

from cvdupdate.cvdupdate import CVDUpdate

def start(interval: int) -> None:
    """Spawn a thread to update the AV db after "interval" seconds
    :param interval: the interval in seconds between 2 updates of the db
    """
    if interval > 0:
        Thread(target=_update, daemon=True, args=[interval]).start()


def _update(interval: int) -> None:
    """Don't call this directly

    Updates the AV db after every "interval" seconds when it was started
    :param interval: the interval in seconds between 2 updates of the db
    """
    ticker = Event()
    m = CVDUpdate()
    m.logger.info(f"Updating the database every {interval} seconds")
    while not ticker.wait(interval):
        errors = m.db_update(debug_mode=True)
        if errors > 0:
            m.logger.error("Failed to fetch updates from ClamAV databases")
