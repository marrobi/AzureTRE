import { User } from "./user";

export interface WorkspaceRequest {
  id: string;
  resourceVersion: number;
  requestor: User;
  createdWhen: number;
  updatedBy: User;
  updatedWhen: number;
  history: Array<WorkspaceRequestHistoryItem>;
  title: string;
  businessJustification: string;
  workspaceType: string;
  properties: Record<string, unknown>;
  status: WorkspaceRequestStatus;
  allowedUserActions: Array<WorkspaceRequestAction>;
  reviews?: Array<WorkspaceRequestReview>;
  etag?: string;
}

export interface WorkspaceRequestHistoryItem {
  resourceVersion: number;
  updatedWhen: number;
  updatedBy: User;
  properties: Record<string, unknown>;
}

export enum WorkspaceRequestStatus {
  Draft = "draft",
  Submitted = "submitted",
  InReview = "in_review",
  Approved = "approved",
  Rejected = "rejected",
  Cancelled = "cancelled",
}

export interface NewWorkspaceRequest {
  title: string;
  businessJustification: string;
  workspaceType: string;
  properties: Record<string, unknown>;
}

export enum WorkspaceRequestAction {
  Submit = "submit",
  Cancel = "cancel",
  Review = "review",
}

export enum WorkspaceRequestReviewDecision {
  Approved = "approved",
  Rejected = "rejected",
}

export interface WorkspaceRequestReview {
  id: string;
  dateCreated: number;
  reviewDecision: WorkspaceRequestReviewDecision;
  decisionExplanation: string;
  reviewer: User;
}
