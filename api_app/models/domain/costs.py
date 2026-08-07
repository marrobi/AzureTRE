from datetime import datetime, timedelta, date
from typing import List, Optional
from pydantic import BaseModel, conlist
from enum import StrEnum
import random
import uuid


class GranularityEnum(StrEnum):
    daily = "Daily"
    monthly = "Monthly"
    none = "None"


# Upper bound on the rows a single ingest request may carry. A calendar month of aggregated rows
# for a large TRE is far below this; the limit exists so one request cannot exhaust API memory.
MAX_INGEST_ROWS = 200_000


class CurrencyEnum(StrEnum):
    USD = "USD"
    ILS = "ILS"


def generate_cost_row_dict_example(granularity: GranularityEnum, currency: CurrencyEnum):
    return dict({
        "cost": random.uniform(0, 365), "currency": currency, "date":
            (datetime.today() - timedelta(
                days=-1 * random.randint(0, 1000))).date() if granularity == GranularityEnum.daily else None
    })


def generate_cost_item_dict_example(name: str, granularity: GranularityEnum):
    cost_item_dict = dict(
        id=str(uuid.uuid4()),
        name=name,
        costs=[generate_cost_row_dict_example(granularity, CurrencyEnum.USD),
               generate_cost_row_dict_example(granularity, CurrencyEnum.ILS)]
    )

    if granularity == GranularityEnum.daily:
        cost_item_dict["costs"].append(generate_cost_row_dict_example(granularity, CurrencyEnum.USD))
        cost_item_dict["costs"].append(generate_cost_row_dict_example(granularity, CurrencyEnum.USD))
        cost_item_dict["costs"].append(generate_cost_row_dict_example(granularity, CurrencyEnum.ILS))

    return cost_item_dict


def generate_cost_report_dict_example(granularity: GranularityEnum):
    cost_report = dict(
        core_services=[generate_cost_row_dict_example(granularity, CurrencyEnum.USD)],
        shared_services=[generate_cost_item_dict_example("Gitea", granularity),
                         generate_cost_item_dict_example("Nexus", granularity),
                         generate_cost_item_dict_example("Firewall", granularity)],
        workspaces=[generate_cost_item_dict_example("Workspace 1", granularity),
                    generate_cost_item_dict_example("Workspace 2", granularity),
                    generate_cost_item_dict_example("Workspace 3", granularity)],
        unattributed=[generate_cost_row_dict_example(granularity, CurrencyEnum.USD)]
    )

    if granularity == GranularityEnum.daily:
        cost_report["core_services"].append(generate_cost_row_dict_example(granularity, CurrencyEnum.USD))
        cost_report["core_services"].append(generate_cost_row_dict_example(granularity, CurrencyEnum.ILS))

    return cost_report


def generate_workspace_service_cost_report_dict_example(name: str, granularity: GranularityEnum):
    cost_report = dict(
        id=str(uuid.uuid4()),
        name=name,
        costs=[generate_cost_row_dict_example(granularity, CurrencyEnum.USD)],
        user_resources=[generate_cost_item_dict_example("VM1", granularity),
                        generate_cost_item_dict_example("VM2", granularity),
                        generate_cost_item_dict_example("VM3", granularity)]
    )

    if granularity == GranularityEnum.daily:
        cost_report["costs"].append(generate_cost_row_dict_example(granularity, CurrencyEnum.USD))
        cost_report["costs"].append(generate_cost_row_dict_example(granularity, CurrencyEnum.ILS))

    return cost_report


def generate_workspace_cost_report_dict_example(name: str, granularity: GranularityEnum):
    cost_report = dict(
        id=str(uuid.uuid4()),
        name=name,
        costs=[generate_cost_row_dict_example(granularity, CurrencyEnum.USD)],
        workspace_services=[generate_workspace_service_cost_report_dict_example("Guacamole", granularity)]
    )

    if granularity == GranularityEnum.daily:
        cost_report["costs"].append(generate_cost_row_dict_example(granularity, CurrencyEnum.USD))
        cost_report["costs"].append(generate_cost_row_dict_example(granularity, CurrencyEnum.ILS))

    return cost_report


class CostRow(BaseModel):
    cost: float
    currency: str
    date: Optional[date]


class CostItemType(StrEnum):
    """Discriminates item types in the cost collection (budgets/adjustments may be added later)."""
    cost_day = "cost-day"


class PersistedCostDay(BaseModel):
    """One day of collected Daily cost rows for a single scope, persisted in the cost collection.

    A day is the unit of storage so any requested report period composes from whole days: this
    keeps documents small (well inside Cosmos' 2MB item limit), lets the frequently re-run
    current-month refresh rewrite only the days that changed, and means an arbitrary report range
    never needs a document of its own. ``final`` marks a day Azure has finished re-rating, which
    is never re-queried; a still-settling day is re-queried once ``collected_at`` goes stale.
    """
    id: str
    partitionKey: str
    itemType: CostItemType = CostItemType.cost_day
    tre_id: str
    scope: str
    tag_name: str
    tag_value: str
    usage_date: str
    rows: List[list] = []
    final: bool = False
    collected_at: str


class CostItem(BaseModel):
    id: str
    name: str
    costs: List[CostRow]


class ExportedCostRow(BaseModel):
    """A single aggregated row read from a Cost Management export CSV.

    ``tag`` is a single ``"name":"value"`` pair (the same shape the Cost Management Query API
    emits when grouping by Tag) or an empty string for resources carrying no TRE tag, so
    exported rows can be persisted and read back exactly like query-derived rows.
    """
    date: int
    resource_group: str
    tag: str = ""
    cost: float
    currency: str


class CostIngestRequest(BaseModel):
    """Payload posted by the Cost Processor after running a Cost Management export.

    An export covers exactly one subscription, so ``subscription_id`` identifies which one the
    rows belong to; without it the same rows would be attributed to every subscription the TRE
    spans. It defaults to the core subscription so a single-subscription TRE needs no change.
    ``rows`` is bounded so a single request cannot exhaust API memory; the Cost Processor splits
    a month into contiguous day ranges that stay inside this limit.
    """
    from_date: date
    to_date: date
    granularity: GranularityEnum = GranularityEnum.daily
    subscription_id: Optional[str] = None
    rows: conlist(ExportedCostRow, max_items=MAX_INGEST_ROWS) = []


class CostReport(BaseModel):
    core_services: List[CostRow]
    shared_services: List[CostItem]
    workspaces: List[CostItem]
    # Cost tagged with a TRE workspace/shared-service id that no longer has a database record
    # (e.g. a hard-deleted workspace or a redeployed shared service), so it is not silently dropped.
    unattributed: List[CostRow] = []


class WorkspaceServiceCostItem(CostItem):
    user_resources: List[CostItem]


class WorkspaceCostReport(CostItem):
    workspace_services: List[WorkspaceServiceCostItem]
