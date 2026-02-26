import {
  DefaultButton,
  Dialog,
  DialogFooter,
  IStackTokens,
  Panel,
  PanelType,
  PrimaryButton,
  Spinner,
  SpinnerSize,
  Stack,
  TextField,
} from "@fluentui/react";
import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { HttpMethod, useAuthApiCall } from "../../../hooks/useAuthApiCall";
import {
  NewWorkspaceRequest,
  WorkspaceRequest,
} from "../../../models/workspaceRequest";
import { ApiEndpoint } from "../../../models/apiEndpoints";
import { APIError } from "../../../models/exceptions";
import { ExceptionLayout } from "../ExceptionLayout";

interface WorkspaceRequestNewProps {
  onCreateRequest: (request: WorkspaceRequest) => void;
}

export const WorkspaceRequestNew: React.FunctionComponent<
  WorkspaceRequestNewProps
> = (props: WorkspaceRequestNewProps) => {
  const [newRequest, setNewRequest] = useState<NewWorkspaceRequest>({
    title: "",
    businessJustification: "",
    workspaceType: "",
    properties: {},
  });
  const [requestValid, setRequestValid] = useState(false);
  const [hideCreateDialog, setHideCreateDialog] = useState(true);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState(false);
  const [apiCreateError, setApiCreateError] = useState({} as APIError);
  const navigate = useNavigate();
  const apiCall = useAuthApiCall();

  const onChangeTitle = useCallback(
    (
      _event: React.FormEvent<HTMLInputElement | HTMLTextAreaElement>,
      newValue?: string,
    ) => {
      setNewRequest((request) => ({
        ...request,
        title: newValue || "",
      }));
    },
    [],
  );

  const onChangeBusinessJustification = useCallback(
    (
      _event: React.FormEvent<HTMLInputElement | HTMLTextAreaElement>,
      newValue?: string,
    ) => {
      setNewRequest((request) => ({
        ...request,
        businessJustification: newValue || "",
      }));
    },
    [],
  );

  const onChangeWorkspaceType = useCallback(
    (
      _event: React.FormEvent<HTMLInputElement | HTMLTextAreaElement>,
      newValue?: string,
    ) => {
      setNewRequest((request) => ({
        ...request,
        workspaceType: newValue || "",
      }));
    },
    [],
  );

  useEffect(
    () =>
      setRequestValid(
        newRequest.title?.length > 0 &&
          newRequest.businessJustification?.length > 0 &&
          newRequest.workspaceType?.length > 0,
      ),
    [newRequest],
  );

  const create = useCallback(async () => {
    if (requestValid) {
      setCreating(true);
      setCreateError(false);
      try {
        const response = await apiCall(
          ApiEndpoint.WorkspaceRequests,
          HttpMethod.Post,
          undefined,
          newRequest,
        );
        props.onCreateRequest(response.workspaceRequest);
        setHideCreateDialog(true);
      } catch (err: any) {
        err.userMessage = "Error creating workspace request";
        setApiCreateError(err);
        setCreateError(true);
      }
      setCreating(false);
    }
  }, [apiCall, newRequest, props, requestValid]);

  const dismissPanel = useCallback(() => navigate("../"), [navigate]);

  const renderFooter = useCallback(() => {
    return (
      <div style={{ textAlign: "end" }}>
        <PrimaryButton
          onClick={() => setHideCreateDialog(false)}
          disabled={!requestValid}
        >
          Create
        </PrimaryButton>
      </div>
    );
  }, [requestValid]);

  return (
    <Panel
      headerText="New workspace request"
      isOpen={true}
      isLightDismiss={true}
      onDismiss={dismissPanel}
      onRenderFooterContent={renderFooter}
      isFooterAtBottom={true}
      closeButtonAriaLabel="Close"
      type={PanelType.custom}
      customWidth="450px"
    >
      <Stack style={{ marginTop: "40px" }} tokens={stackTokens}>
        <TextField
          label="Title"
          placeholder="Enter a title for your workspace request."
          value={newRequest.title}
          onChange={onChangeTitle}
          rows={1}
          required
        />
        <TextField
          label="Workspace Type"
          placeholder="Enter the workspace template name (e.g. tre-workspace-base)."
          value={newRequest.workspaceType}
          onChange={onChangeWorkspaceType}
          rows={1}
          required
        />
        <TextField
          label="Business Justification"
          placeholder="Explain why you need this workspace."
          value={newRequest.businessJustification}
          onChange={onChangeBusinessJustification}
          multiline
          rows={8}
          required
        />
      </Stack>
      <Dialog
        hidden={hideCreateDialog}
        onDismiss={() => setHideCreateDialog(true)}
        dialogContentProps={{
          title: "Create workspace request?",
          subText:
            "Are you sure you want to create this workspace request? You can submit it for approval afterwards.",
        }}
      >
        {createError && <ExceptionLayout e={apiCreateError} />}
        {creating ? (
          <Spinner
            label="Creating..."
            ariaLive="assertive"
            labelPosition="top"
            size={SpinnerSize.large}
          />
        ) : (
          <DialogFooter>
            <PrimaryButton onClick={create} text="Create" />
            <DefaultButton
              onClick={() => setHideCreateDialog(true)}
              text="Cancel"
            />
          </DialogFooter>
        )}
      </Dialog>
    </Panel>
  );
};

const stackTokens: IStackTokens = { childrenGap: 20 };
