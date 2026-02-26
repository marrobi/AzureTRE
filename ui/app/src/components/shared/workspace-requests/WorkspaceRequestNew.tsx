import {
  DefaultButton,
  Dialog,
  DialogFooter,
  Dropdown,
  IDropdownOption,
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
import {
  ResourceTemplate,
  sanitiseTemplateForRJSF,
} from "../../../models/resourceTemplate";
import { LoadingState } from "../../../models/loadingState";
import Form from "@rjsf/fluent-ui";
import validator from "@rjsf/validator-ajv8";

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
  const [workspaceTemplates, setWorkspaceTemplates] = useState<
    ResourceTemplate[]
  >([]);
  const [selectedTemplate, setSelectedTemplate] =
    useState<ResourceTemplate | null>(null);
  const [templateSchema, setTemplateSchema] = useState<any | null>(null);
  const [templateFormData, setTemplateFormData] = useState<any>({});
  const [templatesLoading, setTemplatesLoading] = useState(
    LoadingState.Loading,
  );
  const navigate = useNavigate();
  const apiCall = useAuthApiCall();

  // Fetch available workspace templates
  useEffect(() => {
    const getTemplates = async () => {
      try {
        const response = await apiCall(
          `${ApiEndpoint.WorkspaceTemplates}`,
          HttpMethod.Get,
        );
        setWorkspaceTemplates(response.templates || []);
        setTemplatesLoading(LoadingState.Ok);
      } catch (err: any) {
        err.userMessage = "Error fetching workspace templates";
        setApiCreateError(err);
        setTemplatesLoading(LoadingState.Error);
      }
    };
    getTemplates();
  }, [apiCall]);

  // When a template is selected, fetch its full schema
  useEffect(() => {
    const getTemplateSchema = async () => {
      if (!selectedTemplate) {
        setTemplateSchema(null);
        return;
      }
      try {
        const templateResponse = (await apiCall(
          `${ApiEndpoint.WorkspaceTemplates}/${selectedTemplate.name}`,
          HttpMethod.Get,
        )) as ResourceTemplate;
        const sanitised = sanitiseTemplateForRJSF(templateResponse);
        setTemplateSchema(sanitised);
      } catch (err: any) {
        err.userMessage = "Error fetching template schema";
        setApiCreateError(err);
        setTemplateSchema(null);
      }
    };
    getTemplateSchema();
  }, [apiCall, selectedTemplate]);

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

  const onTemplateChange = useCallback(
    (_event: React.FormEvent<HTMLDivElement>, option?: IDropdownOption) => {
      if (option) {
        const template = workspaceTemplates.find(
          (t) => t.name === option.key,
        );
        setSelectedTemplate(template || null);
        setNewRequest((request) => ({
          ...request,
          workspaceType: option.key as string,
        }));
        setTemplateFormData({});
      }
    },
    [workspaceTemplates],
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
        const requestPayload = {
          ...newRequest,
          properties: templateFormData,
        };
        const response = await apiCall(
          ApiEndpoint.WorkspaceRequests,
          HttpMethod.Post,
          undefined,
          requestPayload,
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
  }, [apiCall, newRequest, props, requestValid, templateFormData]);

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

  const templateOptions: IDropdownOption[] = workspaceTemplates.map((t) => ({
    key: t.name,
    text: t.title || t.name,
  }));

  // Use the supplied uiSchema or create a blank one
  const uiSchema = (templateSchema && templateSchema.uiSchema) || {};
  uiSchema.overview = { "ui:widget": "textarea" };
  if (!uiSchema["ui:order"] || uiSchema["ui:order"].length === 0) {
    uiSchema["ui:order"] = ["display_name", "description", "overview", "*"];
  }

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
        {templatesLoading === LoadingState.Loading ? (
          <Spinner label="Loading templates..." size={SpinnerSize.small} />
        ) : templatesLoading === LoadingState.Error ? (
          <ExceptionLayout e={apiCreateError} />
        ) : (
          <Dropdown
            label="Workspace Type"
            placeholder="Select a workspace template"
            options={templateOptions}
            selectedKey={newRequest.workspaceType || undefined}
            onChange={onTemplateChange}
            required
          />
        )}
        <TextField
          label="Business Justification"
          placeholder="Explain why you need this workspace."
          value={newRequest.businessJustification}
          onChange={onChangeBusinessJustification}
          multiline
          rows={6}
          required
        />
        {templateSchema && (
          <>
            <h3 style={{ marginTop: 16, marginBottom: 0 }}>
              Workspace Properties
            </h3>
            <Form
              omitExtraData={true}
              schema={templateSchema}
              formData={templateFormData}
              uiSchema={uiSchema}
              validator={validator}
              onChange={(e: any) => setTemplateFormData(e.formData)}
              children={<></>}
            />
          </>
        )}
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
