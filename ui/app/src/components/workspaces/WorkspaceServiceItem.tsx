import React, { useContext, useEffect, useState } from "react";
import { Route, Routes, useNavigate, useParams } from "react-router-dom";
import { ApiEndpoint } from "../../models/apiEndpoints";
import { useAuthApiCall, HttpMethod } from "../../hooks/useAuthApiCall";
import { UserResource } from "../../models/userResource";
import { WorkspaceService } from "../../models/workspaceService";
import { PrimaryButton, Spinner, SpinnerSize, Stack, IconButton } from "@fluentui/react";
import { ComponentAction, Resource } from "../../models/resource";
import { ResourceCardList } from "../shared/ResourceCardList";
import { LoadingState } from "../../models/loadingState";
import { WorkspaceContext } from "../../contexts/WorkspaceContext";
import { ResourceType } from "../../models/resourceType";
import { ResourceHeader } from "../shared/ResourceHeader";
import { useComponentManager } from "../../hooks/useComponentManager";
import { CreateUpdateResourceContext } from "../../contexts/CreateUpdateResourceContext";
import { successStates } from "../../models/operation";
import { UserResourceItem } from "./UserResourceItem";
import { ResourceBody } from "../shared/ResourceBody";
import { SecuredByRole } from "../shared/SecuredByRole";
import { WorkspaceRoleName } from "../../models/roleNames";
import { APIError } from "../../models/exceptions";
import { ExceptionLayout } from "../shared/ExceptionLayout";
import { CachedUser } from "../../models/user";
import { useMsal, useAccount } from "@azure/msal-react";

interface WorkspaceServiceItemProps {
  workspaceService?: WorkspaceService;
  updateWorkspaceService: (ws: WorkspaceService) => void;
  removeWorkspaceService: (ws: WorkspaceService) => void;
}

export const WorkspaceServiceItem: React.FunctionComponent<
  WorkspaceServiceItemProps
> = (props: WorkspaceServiceItemProps) => {
  const { workspaceServiceId } = useParams();
  const [userResources, setUserResources] = useState([] as Array<UserResource>);
  const [workspaceService, setWorkspaceService] = useState(
    {} as WorkspaceService,
  );
  const [loadingState, setLoadingState] = useState(LoadingState.Loading);
  const [selectedUserResource, setSelectedUserResource] = useState(
    {} as UserResource,
  );
  const [hasUserResourceTemplates, setHasUserResourceTemplates] =
    useState(false);
  const [usersCache, setUsersCache] = useState(new Map<string, CachedUser>());
  const [isRefreshing, setIsRefreshing] = useState(false);
  const workspaceCtx = useContext(WorkspaceContext);
  const createFormCtx = useContext(CreateUpdateResourceContext);
  const navigate = useNavigate();
  const apiCall = useAuthApiCall();
  const [apiError, setApiError] = useState({} as APIError);
  const { accounts } = useMsal();
  const account = useAccount(accounts[0] || {});

  const latestUpdate = useComponentManager(
    workspaceService,
    (r: Resource) => {
      props.updateWorkspaceService(r as WorkspaceService);
      setWorkspaceService(r as WorkspaceService);
    },
    (r: Resource) => {
      props.removeWorkspaceService(r as WorkspaceService);
      navigate(
        `/${ApiEndpoint.Workspaces}/${workspaceCtx.workspace.id}/${ApiEndpoint.WorkspaceServices}`,
      );
    },
  );

  // Fetch data function that can be called for both initial load and refresh
  const fetchData = async (showRefreshing = false) => {
    if (!workspaceCtx.workspace.id) return;

    if (showRefreshing) {
      setIsRefreshing(true);
    }

    setHasUserResourceTemplates(false);
    try {
      let svc = props.workspaceService || ({} as WorkspaceService);
      // did we get passed the workspace service, or shall we get it from the api?
      if (
        props.workspaceService &&
        props.workspaceService.id &&
        props.workspaceService.id === workspaceServiceId
      ) {
        setWorkspaceService(props.workspaceService);
      } else {
        let ws = await apiCall(
          `${ApiEndpoint.Workspaces}/${workspaceCtx.workspace.id}/${ApiEndpoint.WorkspaceServices}/${workspaceServiceId}`,
          HttpMethod.Get,
          workspaceCtx.workspaceApplicationIdURI,
        );
        setWorkspaceService(ws.workspaceService);
        svc = ws.workspaceService;
      }

      // get the user resources
      const u = await apiCall(
        `${ApiEndpoint.Workspaces}/${workspaceCtx.workspace.id}/${ApiEndpoint.WorkspaceServices}/${workspaceServiceId}/${ApiEndpoint.UserResources}`,
        HttpMethod.Get,
        workspaceCtx.workspaceApplicationIdURI,
      );

      // get user resource templates - to check
      const ut = await apiCall(
        `${ApiEndpoint.Workspaces}/${workspaceCtx.workspace.id}/${ApiEndpoint.WorkspaceServiceTemplates}/${svc.templateName}/${ApiEndpoint.UserResourceTemplates}`,
        HttpMethod.Get,
        workspaceCtx.workspaceApplicationIdURI,
      );
      setHasUserResourceTemplates(
        ut && ut.templates && ut.templates.length > 0,
      );
      setUserResources(u.userResources);

      // Fetch users for caching owner information
      try {
        const usersResponse = await apiCall(
          `${ApiEndpoint.Workspaces}/${workspaceCtx.workspace.id}/${ApiEndpoint.Users}`,
          HttpMethod.Get,
          workspaceCtx.workspaceApplicationIdURI,
        );
        
        const cache = new Map<string, CachedUser>();
        if (usersResponse.users) {
          usersResponse.users.forEach((user: any) => {
            cache.set(user.id, {
              displayName: user.displayName,
              email: user.email || user.userPrincipalName
            });
          });
        }
        setUsersCache(cache);
      } catch (userError) {
        console.warn("Failed to fetch workspace users for owner cache:", userError);
        // Continue without user cache - owner will show as ID
      }

      setLoadingState(LoadingState.Ok);
    } catch (err: any) {
      err.userMessage = "Error retrieving resources";
      setApiError(err);
      setLoadingState(LoadingState.Error);
    } finally {
      if (showRefreshing) {
        setIsRefreshing(false);
      }
    }
  };

  // Initial data load
  useEffect(() => {
    fetchData();
  }, [
    apiCall,
    props.workspaceService,
    workspaceCtx.workspace.id,
    workspaceCtx.workspaceApplicationIdURI,
    workspaceServiceId,
  ]);

  // Polling for status updates (Issue 4)
  useEffect(() => {
    // Poll every 30 seconds to refresh resource status
    const pollInterval = setInterval(() => {
      if (loadingState === LoadingState.Ok) {
        fetchData(true);
      }
    }, 30000); // 30 seconds

    // Cleanup: stop polling when component unmounts
    return () => {
      clearInterval(pollInterval);
    };
  }, [loadingState, workspaceCtx.workspace.id, workspaceServiceId]);

  const addUserResource = (u: UserResource) => {
    let ur = [...userResources];
    ur.push(u);
    setUserResources(ur);
  };

  const updateUserResource = (u: UserResource) => {
    let ur = [...userResources];
    let i = ur.findIndex((f: UserResource) => f.id === u.id);
    ur.splice(i, 1, u);
    setUserResources(ur);
  };

  const removeUserResource = (u: UserResource) => {
    let ur = [...userResources];
    let i = ur.findIndex((f: UserResource) => f.id === u.id);
    ur.splice(i, 1);
    setUserResources(ur);
  };

  // Group resources by ownership (Issue 1: My Resources)
  const getCurrentUserId = () => {
    return account?.localAccountId?.split(".")[0];
  };

  const { myResources, otherResources } = React.useMemo(() => {
    const currentUserId = getCurrentUserId();
    if (!currentUserId) {
      return { myResources: [], otherResources: userResources };
    }

    const my: UserResource[] = [];
    const other: UserResource[] = [];

    userResources.forEach((resource) => {
      if (resource.ownerId === currentUserId) {
        my.push(resource);
      } else {
        other.push(resource);
      }
    });

    return { myResources: my, otherResources: other };
  }, [userResources, account]);

  switch (loadingState) {
    case LoadingState.Ok:
      return (
        <>
          <Routes>
            <Route
              path="*"
              element={
                <>
                  <ResourceHeader
                    resource={workspaceService}
                    latestUpdate={latestUpdate}
                  />
                  <ResourceBody resource={workspaceService} />
                  {hasUserResourceTemplates && (
                    <Stack className="tre-panel">
                      <Stack.Item>
                        <Stack horizontal horizontalAlign="space-between">
                          <h1>Resources</h1>
                          <Stack horizontal tokens={{ childrenGap: 10 }}>
                            <IconButton
                              iconProps={{ iconName: "Refresh" }}
                              title="Refresh resources"
                              ariaLabel="Refresh resources"
                              disabled={isRefreshing}
                              onClick={() => fetchData(true)}
                            />
                            <SecuredByRole
                              allowedWorkspaceRoles={[
                                WorkspaceRoleName.WorkspaceOwner,
                                WorkspaceRoleName.WorkspaceResearcher,
                                WorkspaceRoleName.AirlockManager,
                              ]}
                              element={
                                <PrimaryButton
                                  iconProps={{ iconName: "Add" }}
                                  text="Create new"
                                  disabled={
                                    !workspaceService.isEnabled ||
                                    latestUpdate.componentAction ===
                                      ComponentAction.Lock ||
                                    successStates.indexOf(
                                      workspaceService.deploymentStatus,
                                    ) === -1
                                  }
                                  title={
                                    !workspaceService.isEnabled ||
                                    latestUpdate.componentAction ===
                                      ComponentAction.Lock ||
                                    successStates.indexOf(
                                      workspaceService.deploymentStatus,
                                    ) === -1
                                      ? "Service must be enabled, successfully deployed, and not locked"
                                      : "Create a User Resource"
                                  }
                                  onClick={() => {
                                    createFormCtx.openCreateForm({
                                      resourceType: ResourceType.UserResource,
                                      resourceParent: workspaceService,
                                      onAdd: (r: Resource) =>
                                        addUserResource(r as UserResource),
                                      workspaceApplicationIdURI:
                                        workspaceCtx.workspaceApplicationIdURI,
                                    });
                                  }}
                                />
                              }
                            />
                          </Stack>
                        </Stack>
                      </Stack.Item>
                      {userResources && userResources.length > 0 ? (
                        <>
                          {myResources.length > 0 && (
                            <Stack.Item>
                              <h2 style={{ marginTop: 20, marginBottom: 10 }}>My Resources</h2>
                              <ResourceCardList
                                resources={myResources}
                                selectResource={(r: Resource) =>
                                  setSelectedUserResource(r as UserResource)
                                }
                                updateResource={(r: Resource) =>
                                  updateUserResource(r as UserResource)
                                }
                                removeResource={(r: Resource) =>
                                  removeUserResource(r as UserResource)
                                }
                                emptyText=""
                                isExposedExternally={
                                  workspaceService.properties.is_exposed_externally
                                }
                                usersCache={usersCache}
                              />
                            </Stack.Item>
                          )}
                          {otherResources.length > 0 && (
                            <Stack.Item>
                              <h2 style={{ marginTop: 20, marginBottom: 10 }}>
                                {myResources.length > 0 ? "Other Resources" : "All Resources"}
                              </h2>
                              <ResourceCardList
                                resources={otherResources}
                                selectResource={(r: Resource) =>
                                  setSelectedUserResource(r as UserResource)
                                }
                                updateResource={(r: Resource) =>
                                  updateUserResource(r as UserResource)
                                }
                                removeResource={(r: Resource) =>
                                  removeUserResource(r as UserResource)
                                }
                                emptyText=""
                                isExposedExternally={
                                  workspaceService.properties.is_exposed_externally
                                }
                                usersCache={usersCache}
                              />
                            </Stack.Item>
                          )}
                        </>
                      ) : (
                        <Stack.Item>
                          <ResourceCardList
                            resources={[]}
                            selectResource={(r: Resource) =>
                              setSelectedUserResource(r as UserResource)
                            }
                            updateResource={(r: Resource) =>
                              updateUserResource(r as UserResource)
                            }
                            removeResource={(r: Resource) =>
                              removeUserResource(r as UserResource)
                            }
                            emptyText="This workspace service contains no user resources."
                            isExposedExternally={
                              workspaceService.properties.is_exposed_externally
                            }
                            usersCache={usersCache}
                          />
                        </Stack.Item>
                      )}
                    </Stack>
                  )}
                </>
              }
            />
            <Route
              path="user-resources/:userResourceId/*"
              element={
                <UserResourceItem
                  userResource={selectedUserResource}
                  updateUserResource={(u: UserResource) =>
                    updateUserResource(u)
                  }
                  removeUserResource={(u: UserResource) =>
                    removeUserResource(u)
                  }
                />
              }
            />
          </Routes>
        </>
      );
    case LoadingState.Error:
      return <ExceptionLayout e={apiError} />;
    default:
      return (
        <div style={{ marginTop: "20px" }}>
          <Spinner
            label="Loading Workspace Service"
            ariaLive="assertive"
            labelPosition="top"
            size={SpinnerSize.large}
          />
        </div>
      );
  }
};
