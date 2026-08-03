import logging
import os

import azure.functions as func

from shared_code import exports_client


def main(timer: func.TimerRequest) -> None:
    """Seed cost history from one-time Cost Management exports, one calendar month at a time.

    Follows Microsoft's "Seed a historical cost dataset with the Exports API" guidance: a
    one-time export per month is far cheaper and more reliable for historical data than
    repeatedly querying the (heavily throttled, one-year-limited) Query API.
    """
    if timer.past_due:
        logging.info("The cost history backfill timer is past due.")

    # 0 (the default) means walk back until a month has no data, capped by Cost Management's
    # ~13 month retention window.
    max_months = int(os.environ.get("COST_PROCESSOR_BACKFILL_MAX_MONTHS", "0")) or None
    stop_after_empty_months = int(os.environ.get(
        "COST_PROCESSOR_BACKFILL_STOP_AFTER_EMPTY_MONTHS",
        str(exports_client.BACKFILL_STOP_AFTER_EMPTY_MONTHS)))
    # Wall-clock budget for a single run; 0 means no limit (rely on max_months instead).
    max_runtime_seconds = int(os.environ.get(
        "COST_PROCESSOR_BACKFILL_MAX_RUNTIME_SECONDS",
        str(exports_client.BACKFILL_MAX_RUNTIME_SECONDS))) or None
    logging.info("Starting cost history backfill (max_months=%s, stop_after_empty_months=%s, "
                 "max_runtime_seconds=%s).", max_months, stop_after_empty_months, max_runtime_seconds)
    summary = exports_client.backfill_history(max_months, stop_after_empty_months, max_runtime_seconds)
    logging.info("Cost history backfill complete: %s", summary)
