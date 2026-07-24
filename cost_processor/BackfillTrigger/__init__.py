import logging
import os

import azure.functions as func

from shared_code import api_client


def main(timer: func.TimerRequest) -> None:
    """Walk cost history backwards until a month has no data, filling any months missing from
    the collection so multi-year reports are served from Cosmos rather than live Azure queries.
    """
    if timer.past_due:
        logging.info("The cost history backfill timer is past due.")

    # 0 (the default) means walk all the way back until Azure returns a month with no data.
    max_months = int(os.environ.get("COST_PROCESSOR_BACKFILL_MAX_MONTHS", "0")) or None
    stop_after_empty_months = int(os.environ.get(
        "COST_PROCESSOR_BACKFILL_STOP_AFTER_EMPTY_MONTHS",
        str(api_client.BACKFILL_STOP_AFTER_EMPTY_MONTHS)))
    # Wall-clock budget for a single run; 0 means no limit (rely on max_months instead).
    max_runtime_seconds = int(os.environ.get(
        "COST_PROCESSOR_BACKFILL_MAX_RUNTIME_SECONDS",
        str(api_client.BACKFILL_MAX_RUNTIME_SECONDS))) or None
    logging.info("Starting cost history backfill (max_months=%s, stop_after_empty_months=%s, "
                 "max_runtime_seconds=%s).", max_months, stop_after_empty_months, max_runtime_seconds)
    summary = api_client.backfill_history(max_months, stop_after_empty_months, max_runtime_seconds)
    logging.info("Cost history backfill complete: %s", summary)
