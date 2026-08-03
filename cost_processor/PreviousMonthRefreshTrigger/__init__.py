import logging
import os

import azure.functions as func

from shared_code import exports_client


def main(timer: func.TimerRequest) -> None:
    """Finalise recently-closed month(s) by re-running their Cost Management export.

    Azure keeps re-rating a month for a while after it closes, so each closed month is
    re-exported (rather than re-queried) until it settles, matching how history is seeded.
    """
    if timer.past_due:
        logging.info("The previous-month cost refresh timer is past due.")

    look_back_months = int(os.environ.get("COST_PROCESSOR_PREVIOUS_MONTHS_LOOK_BACK", "1"))
    logging.info("Finalising previous %s month(s) of cost data from Cost Management exports.",
                 look_back_months)
    summary = exports_client.finalise_previous_months(look_back_months)
    logging.info("Previous-month cost finalisation complete: %s", summary)
