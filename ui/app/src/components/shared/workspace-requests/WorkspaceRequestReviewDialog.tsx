import {
  DefaultButton,
  Dialog,
  DialogFooter,
  FontWeights,
  getTheme,
  IButtonStyles,
  IconButton,
  IIconProps,
  mergeStyleSets,
  PrimaryButton,
  Spinner,
  SpinnerSize,
  TextField,
} from "@fluentui/react";
import { useCallback, useState } from "react";
import { HttpMethod, useAuthApiCall } from "../../../hooks/useAuthApiCall";
import { WorkspaceRequest } from "../../../models/workspaceRequest";
import { ApiEndpoint } from "../../../models/apiEndpoints";
import { APIError } from "../../../models/exceptions";
import { destructiveButtonStyles, successButtonStyles } from "../../../styles";
import { ExceptionLayout } from "../ExceptionLayout";

interface WorkspaceRequestReviewDialogProps {
  request: WorkspaceRequest | undefined;
  onReviewComplete: (request: WorkspaceRequest) => void;
  onClose: () => void;
}

export const WorkspaceRequestReviewDialog: React.FunctionComponent<
  WorkspaceRequestReviewDialogProps
> = (props: WorkspaceRequestReviewDialogProps) => {
  const [reviewExplanation, setReviewExplanation] = useState("");
  const [reviewing, setReviewing] = useState(false);
  const [reviewError, setReviewError] = useState(false);
  const [apiError, setApiError] = useState({} as APIError);
  const [showApproveConfirmation, setShowApproveConfirmation] = useState(false);
  const [showRejectConfirmation, setShowRejectConfirmation] = useState(false);
  const apiCall = useAuthApiCall();

  const reviewRequest = useCallback(
    async (isApproved: boolean) => {
      if (props.request && reviewExplanation) {
        setReviewing(true);
        setReviewError(false);
        try {
          const review = {
            approval: isApproved,
            decisionExplanation: reviewExplanation,
          };
          const response = await apiCall(
            `${ApiEndpoint.WorkspaceRequests}/${props.request.id}/${ApiEndpoint.WorkspaceRequestReview}`,
            HttpMethod.Post,
            undefined,
            review,
          );
          const updatedRequest = response.workspaceRequest as WorkspaceRequest;
          updatedRequest.allowedUserActions = response.allowedUserActions;
          props.onReviewComplete(updatedRequest);
        } catch (err: any) {
          err.userMessage = "Error reviewing workspace request";
          setApiError(err);
          setReviewError(true);
        }
        setReviewing(false);
      }
    },
    [apiCall, props, reviewExplanation],
  );

  return (
    <>
      <div className={contentStyles.header}>
        <span id={`title-${props.request?.id}`}>
          Review: {props.request?.title}
        </span>
        <IconButton
          styles={iconButtonStyles}
          iconProps={cancelIcon}
          ariaLabel="Close popup modal"
          onClick={props.onClose}
        />
      </div>
      <div className={contentStyles.body}>
        <p>
          Review the workspace request details and provide your decision
          below.
        </p>
        <p>
          <b>Business Justification:</b>{" "}
          {props.request?.businessJustification}
        </p>
        <p>
          <b>Workspace Type:</b> {props.request?.workspaceType}
        </p>
        <TextField
          label="Reason for decision"
          placeholder="Please provide a brief explanation of your decision."
          value={reviewExplanation}
          onChange={(_e: React.FormEvent, newValue?: string) =>
            setReviewExplanation(newValue || "")
          }
          multiline
          rows={6}
          required
        />
        {reviewError && <ExceptionLayout e={apiError} />}
        {reviewing ? (
          <Spinner
            label="Submitting review..."
            ariaLive="assertive"
            labelPosition="top"
            size={SpinnerSize.large}
            style={{ marginTop: 20 }}
          />
        ) : (
          <DialogFooter>
            <DefaultButton onClick={props.onClose} text="Cancel" />
            <DefaultButton
              iconProps={{ iconName: "Cancel" }}
              onClick={() => setShowRejectConfirmation(true)}
              text="Reject"
              styles={destructiveButtonStyles}
              disabled={reviewExplanation.length <= 0}
            />
            <DefaultButton
              iconProps={{ iconName: "Accept" }}
              onClick={() => setShowApproveConfirmation(true)}
              text="Approve"
              styles={successButtonStyles}
              disabled={reviewExplanation.length <= 0}
            />
          </DialogFooter>
        )}
      </div>

      <Dialog
        hidden={!showApproveConfirmation}
        onDismiss={() => setShowApproveConfirmation(false)}
        dialogContentProps={{
          title: "Approve Workspace Request?",
          subText: `Are you sure you want to approve "${props.request?.title}"?`,
        }}
      >
        <DialogFooter>
          <PrimaryButton
            onClick={() => {
              setShowApproveConfirmation(false);
              reviewRequest(true);
            }}
            text="Yes, Approve"
            styles={successButtonStyles}
          />
          <DefaultButton
            onClick={() => setShowApproveConfirmation(false)}
            text="Cancel"
          />
        </DialogFooter>
      </Dialog>

      <Dialog
        hidden={!showRejectConfirmation}
        onDismiss={() => setShowRejectConfirmation(false)}
        dialogContentProps={{
          title: "Reject Workspace Request?",
          subText: `Are you sure you want to reject "${props.request?.title}"?`,
        }}
      >
        <DialogFooter>
          <PrimaryButton
            onClick={() => {
              setShowRejectConfirmation(false);
              reviewRequest(false);
            }}
            text="Yes, Reject"
            styles={destructiveButtonStyles}
          />
          <DefaultButton
            onClick={() => setShowRejectConfirmation(false)}
            text="Cancel"
          />
        </DialogFooter>
      </Dialog>
    </>
  );
};

const theme = getTheme();
const contentStyles = mergeStyleSets({
  header: [
    theme.fonts.xLarge,
    {
      flex: "1 1 auto",
      borderTop: `4px solid ${theme.palette.themePrimary}`,
      color: theme.palette.neutralPrimary,
      display: "flex",
      alignItems: "center",
      fontWeight: FontWeights.semibold,
      padding: "12px 12px 14px 24px",
    },
  ],
  body: {
    flex: "4 4 auto",
    padding: "0 24px 24px 24px",
    overflowY: "hidden",
    selectors: {
      p: { margin: "14px 0" },
      "p:first-child": { marginTop: 0 },
      "p:last-child": { marginBottom: 0 },
    },
    width: 600,
  },
});

const iconButtonStyles: Partial<IButtonStyles> = {
  root: {
    color: theme.palette.neutralPrimary,
    marginLeft: "auto",
    marginTop: "4px",
    marginRight: "2px",
  },
  rootHovered: {
    color: theme.palette.neutralDark,
  },
};

const cancelIcon: IIconProps = { iconName: "Cancel" };
