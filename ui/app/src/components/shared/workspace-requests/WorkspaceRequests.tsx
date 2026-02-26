import React, { useCallback, useContext, useEffect, useState } from "react";
import {
  ColumnActionsMode,
  CommandBar,
  CommandBarButton,
  ContextualMenu,
  DirectionalHint,
  getTheme,
  IColumn,
  ICommandBarItemProps,
  Icon,
  IContextualMenuItem,
  IContextualMenuProps,
  Persona,
  PersonaSize,
  SelectionMode,
  ShimmeredDetailsList,
  Stack,
} from "@fluentui/react";
import { HttpMethod, useAuthApiCall } from "../../../hooks/useAuthApiCall";
import { ApiEndpoint } from "../../../models/apiEndpoints";
import {
  WorkspaceRequest,
  WorkspaceRequestAction,
  WorkspaceRequestStatus,
} from "../../../models/workspaceRequest";
import moment from "moment";
import { Route, Routes, useNavigate } from "react-router-dom";
import { LoadingState } from "../../../models/loadingState";
import { APIError } from "../../../models/exceptions";
import { ExceptionLayout } from "../ExceptionLayout";
import { WorkspaceRequestNew } from "./WorkspaceRequestNew";
import { WorkspaceRequestView } from "./WorkspaceRequestView";
import { AppRolesContext } from "../../../contexts/AppRolesContext";
import { RoleName } from "../../../models/roleNames";

export const WorkspaceRequests: React.FunctionComponent = () => {
  const [workspaceRequests, setWorkspaceRequests] = useState(
    [] as WorkspaceRequest[],
  );
  const [requestColumns, setRequestColumns] = useState([] as IColumn[]);
  const [orderBy, setOrderBy] = useState("updatedWhen");
  const [orderAscending, setOrderAscending] = useState(false);
  const [filters, setFilters] = useState(new Map<string, string>());
  const [loadingState, setLoadingState] = useState(LoadingState.Loading);
  const [contextMenuProps, setContextMenuProps] =
    useState<IContextualMenuProps>();
  const [apiError, setApiError] = useState<APIError>();
  const apiCall = useAuthApiCall();
  const theme = getTheme();
  const navigate = useNavigate();
  const appRolesCtx = useContext(AppRolesContext);

  const getWorkspaceRequests = useCallback(async () => {
    setApiError(undefined);
    setLoadingState(LoadingState.Loading);

    try {
      let query = "?";
      filters.forEach((value, key) => {
        query += `${key}=${value}&`;
      });
      if (orderBy) {
        query += `order_by=${orderBy}&order_ascending=${orderAscending}&`;
      }

      const result = await apiCall(
        `${ApiEndpoint.WorkspaceRequests}${query.slice(0, -1)}`,
        HttpMethod.Get,
      );

      const requests: WorkspaceRequest[] = result.workspaceRequests.map(
        (r: {
          workspaceRequest: WorkspaceRequest;
          allowedUserActions: Array<WorkspaceRequestAction>;
        }) => {
          const request = r.workspaceRequest;
          request.allowedUserActions = r.allowedUserActions;
          return request;
        },
      );

      setWorkspaceRequests(requests);
      setLoadingState(LoadingState.Ok);
    } catch (err: any) {
      err.userMessage = "Error fetching workspace requests";
      setApiError(err);
      setLoadingState(LoadingState.Error);
    }
  }, [apiCall, filters, orderBy, orderAscending]);

  useEffect(() => {
    getWorkspaceRequests();
  }, [getWorkspaceRequests]);

  const orderRequests = (column: IColumn) => {
    setOrderBy((o) => {
      if (o === column.key) {
        setOrderAscending((previous) => !previous);
        return column.key;
      }
      return column.key;
    });
  };

  const openContextMenu = useCallback(
    (
      column: IColumn,
      ev: React.MouseEvent<HTMLElement>,
      options: Array<string>,
    ) => {
      const filterOptions = options.map((option) => {
        return {
          key: option,
          name: option,
          canCheck: true,
          checked:
            filters?.has(column.key) && filters.get(column.key) === option,
          onClick: () => {
            setFilters((f) => {
              if (f.get(column.key) === option) {
                f.delete(column.key);
              } else {
                f.set(column.key, option);
              }
              return new Map(f);
            });
          },
        };
      });

      const items: IContextualMenuItem[] = [
        {
          key: "sort",
          name: "Sort",
          iconProps: { iconName: "Sort" },
          onClick: () => orderRequests(column),
        },
        {
          key: "filter",
          name: "Filter",
          iconProps: { iconName: "Filter" },
          subMenuProps: {
            items: filterOptions,
          },
        },
      ];

      setContextMenuProps({
        items: items,
        target: ev.currentTarget as HTMLElement,
        directionalHint: DirectionalHint.bottomCenter,
        gapSpace: 0,
        onDismiss: () => setContextMenuProps(undefined),
      });
    },
    [filters],
  );

  useEffect(() => {
    const orderByColumn = (
      ev: React.MouseEvent<HTMLElement>,
      column: IColumn,
    ) => {
      orderRequests(column);
    };

    const columns: IColumn[] = [
      {
        key: "icon",
        name: "",
        minWidth: 16,
        maxWidth: 16,
        isIconOnly: true,
        onRender: () => (
          <Icon
            iconName="CubeShape"
            style={{ verticalAlign: "bottom", fontSize: 14 }}
          />
        ),
      },
      {
        key: "title",
        name: "Title",
        ariaLabel: "Title of the workspace request",
        minWidth: 150,
        maxWidth: 300,
        isResizable: true,
        fieldName: "title",
      },
      {
        key: "requestor",
        name: "Requestor",
        ariaLabel: "Requestor of the workspace request",
        minWidth: 150,
        maxWidth: 200,
        isResizable: true,
        onRender: (request: WorkspaceRequest) => (
          <Persona size={PersonaSize.size24} text={request.requestor?.name} />
        ),
      },
      {
        key: "workspaceType",
        name: "Workspace Type",
        ariaLabel: "The workspace template type",
        minWidth: 120,
        maxWidth: 200,
        isResizable: true,
        fieldName: "workspaceType",
      },
      {
        key: "status",
        name: "Status",
        ariaLabel: "Status of the request",
        minWidth: 70,
        isResizable: true,
        fieldName: "status",
        columnActionsMode: ColumnActionsMode.hasDropdown,
        isSorted: orderBy === "status",
        isSortedDescending: !orderAscending,
        onColumnClick: (ev, column) =>
          openContextMenu(
            column,
            ev,
            Object.values(WorkspaceRequestStatus),
          ),
        onColumnContextMenu: (column, ev) =>
          column &&
          ev &&
          openContextMenu(
            column,
            ev,
            Object.values(WorkspaceRequestStatus),
          ),
        isFiltered: filters.has("status"),
        onRender: (request: WorkspaceRequest) =>
          request.status.replace("_", " "),
      },
      {
        key: "createdWhen",
        name: "Created",
        ariaLabel: "When the request was created",
        minWidth: 120,
        data: "number",
        isResizable: true,
        fieldName: "createdWhen",
        isSorted: orderBy === "createdWhen",
        isSortedDescending: !orderAscending,
        onRender: (request: WorkspaceRequest) => (
          <span>
            {moment.unix(request.createdWhen).format("DD/MM/YYYY")}
          </span>
        ),
        onColumnClick: orderByColumn,
      },
      {
        key: "updatedWhen",
        name: "Updated",
        ariaLabel: "When the request was last updated",
        minWidth: 120,
        data: "number",
        isResizable: true,
        fieldName: "updatedWhen",
        isSorted: orderBy === "updatedWhen",
        isSortedDescending: !orderAscending,
        onRender: (request: WorkspaceRequest) => (
          <span>{moment.unix(request.updatedWhen).fromNow()}</span>
        ),
        onColumnClick: orderByColumn,
      },
    ];
    setRequestColumns(columns);
  }, [openContextMenu, filters, orderAscending, orderBy]);

  const handleNewRequest = async (newRequest: WorkspaceRequest) => {
    await getWorkspaceRequests();
    navigate(newRequest.id);
  };

  const quickFilters: ICommandBarItemProps[] = [
    {
      key: "reset",
      text: "Clear filters",
      iconProps: { iconName: "ClearFilter" },
      onClick: () => setFilters(new Map()),
    },
  ];

  if (appRolesCtx.roles.includes(RoleName.TREAdmin)) {
    quickFilters.unshift({
      key: "awaitingReview",
      text: "Awaiting review",
      iconProps: { iconName: "TemporaryUser" },
      onClick: () => setFilters(new Map([["status", "in_review"]])),
    });
  }

  return (
    <>
      <Stack className="tre-panel">
        <Stack.Item>
          <Stack horizontal horizontalAlign="space-between">
            <h1 style={{ marginBottom: 0, marginRight: 30 }}>
              Workspace Requests
            </h1>
            <Stack.Item grow>
              <CommandBar items={quickFilters} ariaLabel="Quick filters" />
            </Stack.Item>
            <CommandBarButton
              iconProps={{ iconName: "refresh" }}
              text="Refresh"
              style={{
                background: "none",
                color: theme.palette.themePrimary,
              }}
              onClick={() => getWorkspaceRequests()}
            />
            <CommandBarButton
              iconProps={{ iconName: "add" }}
              text="New request"
              style={{
                background: "none",
                color: theme.palette.themePrimary,
              }}
              onClick={() => navigate("new")}
            />
          </Stack>
        </Stack.Item>
      </Stack>
      {apiError && <ExceptionLayout e={apiError} />}
      <div className="tre-resource-panel" style={{ padding: "0px" }}>
        <ShimmeredDetailsList
          items={workspaceRequests}
          columns={requestColumns}
          selectionMode={SelectionMode.none}
          getKey={(item) => item?.id}
          onItemInvoked={(item) => navigate(item.id)}
          className="tre-table"
          enableShimmer={loadingState === LoadingState.Loading}
        />
        {contextMenuProps && <ContextualMenu {...contextMenuProps} />}
        {workspaceRequests.length === 0 &&
          loadingState !== LoadingState.Loading && (
            <div
              style={{
                textAlign: "center",
                padding: "50px 10px 100px 10px",
              }}
            >
              <h4>No workspace requests found</h4>
              {filters.size > 0 ? (
                <small>
                  There are no requests matching your selected filter(s).
                </small>
              ) : (
                <small>
                  No workspace requests yet. Click "New request" to request
                  a workspace.
                </small>
              )}
            </div>
          )}
      </div>

      <Routes>
        <Route
          path="new"
          element={
            <WorkspaceRequestNew onCreateRequest={handleNewRequest} />
          }
        />
        <Route
          path=":requestId"
          element={
            <WorkspaceRequestView
              requests={workspaceRequests}
              onUpdateRequest={getWorkspaceRequests}
            />
          }
        />
      </Routes>
    </>
  );
};
