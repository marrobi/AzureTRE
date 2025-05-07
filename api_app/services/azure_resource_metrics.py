from core import config, credentials
from azure.mgmt.monitor import MonitorManagementClient
from azure.core.exceptions import ResourceNotFoundError
from services.logging import logger
from datetime import datetime, timedelta

# Default metrics to fetch for VMs. Can be extended for other resource types.
DEFAULT_VM_METRICS = [
    "Percentage CPU",
    "Available Memory Bytes"
]

def get_azure_resource_metrics(resource_id, metrics=None, timespan_minutes=5):
    """
    Fetches specified metrics for an Azure resource from Azure Monitor.
    :param resource_id: Azure resource ID
    :param metrics: List of metric names to fetch (default: sensible for VMs)
    :param timespan_minutes: How far back to look for metrics
    :return: Dict of metric name to latest value
    """
    if metrics is None:
        metrics = DEFAULT_VM_METRICS

    monitor_client = MonitorManagementClient(
        credentials.get_credential(),
        config.SUBSCRIPTION_ID,
        base_url=config.RESOURCE_MANAGER_ENDPOINT,
        credential_scopes=config.CREDENTIAL_SCOPES
    )

    end_time = datetime.now(datetime.timezone.utc)
    start_time = end_time - timedelta(minutes=timespan_minutes)
    timespan = f"{start_time.isoformat()}Z/{end_time.isoformat()}Z"

    result = {}
    try:
        metrics_data = monitor_client.metrics.list(
            resource_id,
            timespan=timespan,
            interval=None,
            metricnames=','.join(metrics),
            aggregation='Average',
        )
        for item in metrics_data.value:
            if item.timeseries and item.timeseries[0].data:
                # Get the latest data point
                latest = item.timeseries[0].data[-1]
                value = None
                if hasattr(latest, 'average'):
                    value = latest.average
                elif hasattr(latest, 'total'):
                    value = latest.total
                result[item.name.value] = value
            else:
                result[item.name.value] = None
    except ResourceNotFoundError:
        logger.warning(f"Unable to query metrics for {resource_id}, as the resource was not found.")
    except Exception as e:
        logger.warning(f"Error fetching metrics for {resource_id}: {e}")
    return result
