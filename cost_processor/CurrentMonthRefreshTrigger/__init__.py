import logging

import azure.functions as func

from shared_code import api_client


def main(timer: func.TimerRequest) -> None:
    """Refresh the current (still-settling) month's cost data on a frequent cadence.

    Azure Cost Management data lags actual usage by roughly 24-48 hours and continues to be
    re-rated for a day or two, so the current month is the only segment that needs frequent
    refreshing; completed months are collected once and then served from the collection.
    """
    if timer.past_due:
        logging.info("The current-month cost refresh timer is past due.")

    logging.info("Refreshing current-month cost data.")
    result = api_client.refresh_current_month()
    logging.info("Current-month cost refresh complete: %s", result)
