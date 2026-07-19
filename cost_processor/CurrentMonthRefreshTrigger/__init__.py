import logging

import azure.functions as func

from shared_code import api_client


def main(timer: func.TimerRequest) -> None:
    """Refresh the still-settling current month frequently (Cost Management lags ~24-48h)."""
    if timer.past_due:
        logging.info("The current-month cost refresh timer is past due.")

    logging.info("Refreshing current-month cost data.")
    result = api_client.refresh_current_month()
    logging.info("Current-month cost refresh complete: %s", result)
