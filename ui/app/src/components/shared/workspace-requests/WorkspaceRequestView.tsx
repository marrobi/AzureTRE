import {
  DefaultButton,
  Dialog,
  DialogFooter,
  DocumentCard,
  DocumentCardActivity,
  DocumentCardDetails,
  DocumentCardTitle,
  DocumentCardType,
  FontIcon,
  getTheme,
  IStackItemStyles,
  IStackStyles,
  IStackTokens,
  mergeStyles,
  MessageBar,
  MessageBarType,
  Modal,
  Panel,
  PanelType,
  Persona,
  PersonaSize,
  PrimaryButton,
  Spinner,
  SpinnerSize,
  Stack,
} from "@fluentui/react";
import moment from "moment";
import React, { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { HttpMethod, useAuthApiCall } from "../../../hooks/useAuthApiCall";
import {
  WorkspaceRequest,
  WorkspaceRequestAction,
  WorkspaceRequestReviewDecision,
  WorkspaceRequestStatus,
} from "../../../models/workspaceRequest";
import { ApiEndpoint } from "../../../models/apiEndpoints";
import { APIError } from "../../../models/exceptions";
import { ResourceType } from "../../../models/resourceType";
import { destructiveButtonStyles } from "../../../styles";
import { ExceptionLayout } from "../ExceptionLayout";
import { CreateUpdateResource } from "../create-update-resource/CreateUpdateResource";
import { WorkspaceRequestReviewDialog } from "./WorkspaceRequestReviewDialog";

interface WorkspaceRequestViewProps {
  requests: WorkspaceRequest[];
  onUpdateRequest: () => void;
}

export const WorkspaceRequestView: React.FunctionComponent<
  WorkspaceRequestViewProps
> = (props: WorkspaceRequestViewProps) => {
  const { requestId } = useParams();
  const [request, setRequest] = useState<WorkspaceRequest>();
  const [hideSubmitDialog, setHideSubmitDialog] = useState(true);
  const [hideCancelDialog, setHideCancelDialog] = useState(true);
  const [reviewIsOpen, setReviewIsOpen] = useState(false);
  const [deployIsOpen, setDeployIsOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(false);
  const [apiError, setApiError] = useState({} as APIError);
  const apiCall = useAuthApiCall();
  const navigate = useNavigate();

  useEffect(() => {
    let req = props.requests.find(
      (r) => r.id === requestId,
    ) as WorkspaceRequest;

    if (!req) {
      apiCall(
        `${ApiEndpoint.WorkspaceRequests}/${requestId}`,
        HttpMethod.Get,
      ).then((result) => {
        const wsRequest = result.workspaceRequest as WorkspaceRequest;
        wsRequest.allowedUserActions = result.allowedUserActions;
        setRequest(wsRequest);
      });
    } else {
      setRequest(req);
    }
  }, [apiCall, requestId, props.requests]);

  const dismissPanel = useCallback(() => navigate("../"), [navigate]);

  const submitRequest = useCallback(async () => {
    if (request) {
      setSubmitting(true);
      setSubmitError(false);
      try {
        const response = await apiCall(
          `${ApiEndpoint.WorkspaceRequests}/${request.id}/${ApiEndpoint.WorkspaceRequestSubmit}`,
          HttpMethod.Post,
        );
        props.onUpdateRequest();
        setRequest(response.workspaceRequest);
        setHideSubmitDialog(true);
      } catch (err: any) {
        err.userMessage = "Error submitting workspace request";
        setApiError(err);
        setSubmitError(true);
      }
      setSubmitting(false);
    }
  }, [apiCall, request, props]);

  const cancelRequest = useCallback(async () => {
    if (request) {
      setSubmitting(true);
      setSubmitError(false);
      try {
        const response = await apiCall(
          `${ApiEndpoint.WorkspaceRequests}/${request.id}/${ApiEndpoint.WorkspaceRequestCancel}`,
          HttpMethod.Post,
        );
        props.onUpdateRequest();
        setRequest(response.workspaceRequest);
        setHideCancelDialog(true);
      } catch (err: any) {
        err.userMessage = "Error cancelling workspace request";
        setApiError(err);
        setSubmitError(true);
      }
      setSubmitting(false);
    }
  }, [apiCall, request, props]);

  const renderFooter = useCallback(() => {
    if (!request) return <></>;
    return (
      <>
        {request.status === WorkspaceRequestStatus.Draft && (
          <div style={{ marginTop: "10px", marginBottom: "10px" }}>
            <MessageBar>
              This request is currently in draft. Submit when you are ready
              for it to be reviewed.
            </MessageBar>
          </div>
        )}
        {request.status === WorkspaceRequestStatus.Approved && (
          <div style={{ marginTop: "10px", marginBottom: "10px" }}>
            <MessageBar messageBarType={MessageBarType.success}>
              This request has been approved. An admin can now deploy the
              workspace using the &quot;Deploy Workspace&quot; button below.
            </MessageBar>
          </div>
        )}
        <div style={{ textAlign: "end" }}>
          {request.allowedUserActions?.includes(
            WorkspaceRequestAction.Cancel,
          ) && (
            <DefaultButton
              onClick={() => {
                setSubmitError(false);
                setHideCancelDialog(false);
              }}
              styles={destructiveButtonStyles}
            >
              Cancel request
            </DefaultButton>
          )}
          {request.allowedUserActions?.includes(
            WorkspaceRequestAction.Submit,
          ) && (
            <PrimaryButton
              onClick={() => {
                setSubmitError(false);
                setHideSubmitDialog(false);
              }}
            >
              Submit
            </PrimaryButton>
          )}
          {request.allowedUserActions?.includes(
            WorkspaceRequestAction.Review,
          ) && (
            <PrimaryButton onClick={() => setReviewIsOpen(true)}>
              Review
            </PrimaryButton>
          )}
          {request.allowedUserActions?.includes(
            WorkspaceRequestAction.Deploy,
          ) && (
            <PrimaryButton
              iconProps={{ iconName: "CloudAdd" }}
              onClick={() => setDeployIsOpen(true)}
            >
              Deploy Workspace
            </PrimaryButton>
          )}
        </div>
      </>
    );
  }, [request]);

  return (
    <>
      <Panel
        headerText={
          request && request.title
            ? request.title
            : "View workspace request"
        }
        isOpen={true}
        isLightDismiss={true}
        onDismiss={dismissPanel}
        onRenderFooterContent={renderFooter}
        isFooterAtBottom={true}
        closeButtonAriaLabel="Close"
        type={PanelType.custom}
        customWidth="450px"
      >
        {request ? (
          <>
            <Stack
              horizontal
              horizontalAlign="space-between"
              style={{ marginTop: "40px" }}
              styles={underlineStackStyles}
            >
              <Stack.Item styles={stackItemStyles}>
                <b>Id</b>
              </Stack.Item>
              <Stack.Item styles={stackItemStyles}>
                <p>{request.id}</p>
              </Stack.Item>
            </Stack>

            <Stack
              horizontal
              horizontalAlign="space-between"
              styles={underlineStackStyles}
            >
              <Stack.Item styles={stackItemStyles}>
                <b>Requestor</b>
              </Stack.Item>
              <Stack.Item styles={stackItemStyles}>
                <Persona
                  size={PersonaSize.size32}
                  text={request.requestor?.name}
                />
              </Stack.Item>
            </Stack>

            <Stack
              horizontal
              horizontalAlign="space-between"
              styles={underlineStackStyles}
            >
              <Stack.Item styles={stackItemStyles}>
                <b>Workspace Type</b>
              </Stack.Item>
              <Stack.Item styles={stackItemStyles}>
                <p>{request.workspaceType}</p>
              </Stack.Item>
            </Stack>

            <Stack
              horizontal
              horizontalAlign="space-between"
              styles={underlineStackStyles}
            >
              <Stack.Item styles={stackItemStyles}>
                <b>Status</b>
              </Stack.Item>
              <Stack.Item styles={stackItemStyles}>
                <p>{request.status.replace("_", " ")}</p>
              </Stack.Item>
            </Stack>

            <Stack
              horizontal
              horizontalAlign="space-between"
              styles={underlineStackStyles}
            >
              <Stack.Item styles={stackItemStyles}>
                <b>Created</b>
              </Stack.Item>
              <Stack.Item styles={stackItemStyles}>
                <p>
                  {moment
                    .unix(request.createdWhen)
                    .format("DD/MM/YYYY")}
                </p>
              </Stack.Item>
            </Stack>

            <Stack
              horizontal
              horizontalAlign="space-between"
              styles={underlineStackStyles}
            >
              <Stack.Item styles={stackItemStyles}>
                <b>Updated</b>
              </Stack.Item>
              <Stack.Item styles={stackItemStyles}>
                <p>{moment.unix(request.updatedWhen).fromNow()}</p>
              </Stack.Item>
            </Stack>

            <Stack
              style={{ marginTop: "20px" }}
              styles={underlineStackStyles}
            >
              <Stack.Item styles={stackItemStyles}>
                <b>Business Justification</b>
              </Stack.Item>
            </Stack>
            <Stack>
              <Stack.Item styles={stackItemStyles}>
                <p>{request.businessJustification}</p>
              </Stack.Item>
            </Stack>

            {request.properties &&
              Object.keys(request.properties).length > 0 && (
                <>
                  <Stack
                    style={{ marginTop: "20px" }}
                    styles={underlineStackStyles}
                  >
                    <Stack.Item styles={stackItemStyles}>
                      <b>Workspace Options</b>
                    </Stack.Item>
                  </Stack>
                  {Object.entries(request.properties).map(([key, value]) => (
                    <Stack
                      key={key}
                      horizontal
                      horizontalAlign="space-between"
                      styles={underlineStackStyles}
                    >
                      <Stack.Item styles={stackItemStyles}>
                        <span>
                          {key
                            .replace(/_/g, " ")
                            .replace(/\b\w/g, (c) => c.toUpperCase())}
                        </span>
                      </Stack.Item>
                      <Stack.Item styles={stackItemStyles}>
                        <p>{String(value)}</p>
                      </Stack.Item>
                    </Stack>
                  ))}
                </>
              )}

            {request.reviews && request.reviews.length > 0 && (
              <>
                <Stack
                  style={{ marginTop: "20px", marginBottom: "20px" }}
                  styles={underlineStackStyles}
                >
                  <Stack.Item styles={stackItemStyles}>
                    <b>Reviews</b>
                  </Stack.Item>
                </Stack>
                <Stack tokens={stackTokens}>
                  {request.reviews.map((review, i) => (
                    <DocumentCard
                      key={i}
                      aria-label="Review"
                      type={DocumentCardType.compact}
                    >
                      <DocumentCardDetails>
                        <DocumentCardActivity
                          activity={moment
                            .unix(review.dateCreated)
                            .fromNow()}
                          people={[
                            {
                              name: review.reviewer.name,
                              profileImageSrc: "",
                            },
                          ]}
                        />
                        <DocumentCardTitle
                          title={review.decisionExplanation}
                          shouldTruncate
                          showAsSecondaryTitle
                        />
                      </DocumentCardDetails>
                      <div style={{ margin: 10 }}>
                        {review.reviewDecision ===
                          WorkspaceRequestReviewDecision.Approved && (
                          <>
                            <FontIcon
                              aria-label="Approved"
                              iconName="Completed"
                              className={approvedIcon}
                            />
                            Approved
                          </>
                        )}
                        {review.reviewDecision ===
                          WorkspaceRequestReviewDecision.Rejected && (
                          <>
                            <FontIcon
                              aria-label="Rejected"
                              iconName="ErrorBadge"
                              className={rejectedIcon}
                            />
                            Rejected
                          </>
                        )}
                      </div>
                    </DocumentCard>
                  ))}
                </Stack>
              </>
            )}
          </>
        ) : (
          <div style={{ marginTop: "70px" }}>
            <Spinner
              label="Loading..."
              ariaLive="assertive"
              labelPosition="top"
              size={SpinnerSize.large}
            />
          </div>
        )}
        <Dialog
          hidden={hideSubmitDialog}
          onDismiss={() => {
            setHideSubmitDialog(true);
            setSubmitError(false);
          }}
          dialogContentProps={{
            title: "Submit workspace request?",
            subText:
              "Once submitted, your request will be reviewed by a TRE Admin.",
          }}
        >
          {submitError && <ExceptionLayout e={apiError} />}
          {submitting ? (
            <Spinner
              label="Submitting..."
              ariaLive="assertive"
              labelPosition="top"
              size={SpinnerSize.large}
            />
          ) : (
            <DialogFooter>
              <DefaultButton
                onClick={() => {
                  setHideSubmitDialog(true);
                  setSubmitError(false);
                }}
                text="Cancel"
              />
              <PrimaryButton onClick={submitRequest} text="Submit" />
            </DialogFooter>
          )}
        </Dialog>
        <Dialog
          hidden={hideCancelDialog}
          onDismiss={() => {
            setHideCancelDialog(true);
            setSubmitError(false);
          }}
          dialogContentProps={{
            title: "Cancel workspace request?",
            subText:
              "Are you sure you want to cancel this workspace request?",
          }}
        >
          {submitError && <ExceptionLayout e={apiError} />}
          {submitting ? (
            <Spinner
              label="Cancelling..."
              ariaLive="assertive"
              labelPosition="top"
              size={SpinnerSize.large}
            />
          ) : (
            <DialogFooter>
              <DefaultButton
                onClick={cancelRequest}
                text="Cancel Request"
                styles={destructiveButtonStyles}
              />
              <DefaultButton
                onClick={() => {
                  setHideCancelDialog(true);
                  setSubmitError(false);
                }}
                text="Back"
              />
            </DialogFooter>
          )}
        </Dialog>
        <Modal
          titleAriaId={`title-${request?.id}`}
          isOpen={reviewIsOpen}
          onDismiss={() => setReviewIsOpen(false)}
          containerClassName={modalStyles}
        >
          <WorkspaceRequestReviewDialog
            request={request}
            onReviewComplete={(updatedRequest) => {
              setRequest(updatedRequest);
              props.onUpdateRequest();
              setReviewIsOpen(false);
            }}
            onClose={() => setReviewIsOpen(false)}
          />
        </Modal>
        <CreateUpdateResource
          isOpen={deployIsOpen}
          onClose={() => setDeployIsOpen(false)}
          resourceType={ResourceType.Workspace}
        />
      </Panel>
    </>
  );
};

const { palette } = getTheme();
const stackTokens: IStackTokens = { childrenGap: 20 };

const underlineStackStyles: IStackStyles = {
  root: {
    borderBottom: "#f2f2f2 solid 1px",
  },
};

const stackItemStyles: IStackItemStyles = {
  root: {
    alignItems: "center",
    display: "flex",
    height: 50,
    margin: "0px 5px",
  },
};

const approvedIcon = mergeStyles({
  color: palette.green,
  marginRight: 5,
  fontSize: 12,
});

const rejectedIcon = mergeStyles({
  color: palette.red,
  marginRight: 5,
  fontSize: 12,
});

const modalStyles = mergeStyles({
  display: "flex",
  flexFlow: "column nowrap",
  alignItems: "stretch",
});
