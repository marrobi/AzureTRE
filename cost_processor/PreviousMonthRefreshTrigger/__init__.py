import logging
import os

import azure.functions as func

from shared_code import api_client


def main(timer: func.TimerRequest) -> None:
    """Daily sweep of recently-closed month(s) until Azure has finished re-rating them.

    The look-back window is configurable; once a month is complete the API marks it final and
    it is never re-queried, so multi-year reports are served almost entirely from the collection.
    """
    if timer.past_due:
        logging.info("The previous-month cost refresh timer is past due.")

    look_back_months = int(os.environ.get("COST_PROCESSOR_PREVIOUS_MONTHS_LOOK_BACK", "1"))
    logging.info("Refreshing previous %s month(s) of cost data.", look_back_months)
    api_client.refresh_previous_months(look_back_months)
    logging.info("Previous-month cost refresh complete.")
