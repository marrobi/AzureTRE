import logging

import azure.functions as func

from shared_code import api_client


def main(timer: func.TimerRequest) -> None:
    """Refresh the still-settling current month frequently (Cost Management lags ~24-48h)."""
    if timer.past_due:
        logging.info("The current-month cost refresh timer is past due.")

    logging.info("Refreshing current-month cost data.")
    try:
        result = api_client.refresh_current_month()
    except api_client.CostRefreshThrottled as throttled:
        # The next scheduled run picks this up; failing the invocation would only add noise.
        logging.warning("Current-month cost refresh throttled, retry after %ss; "
                        "skipping until the next scheduled run.", throttled.retry_after)
        return
    logging.info("Current-month cost refresh complete: %s", result)
