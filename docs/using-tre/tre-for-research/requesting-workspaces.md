# Requesting a Workspace

This guide explains how TRE Users can request new workspaces through the workspace request workflow. Instead of asking a TRE Admin to create a workspace directly, you can submit a formal request that goes through an approval process.

!!! info
    The workspace request feature must be enabled by your TRE administrator. If you don't see "Workspace Requests" in the navigation menu, this feature may not be enabled in your environment.

## Step 1: Create a New Request

1. Open the TRE UI and navigate to **Workspace Requests** in the left-hand menu (under **Requests**).

2. Click **+ New request** in the top-right corner.

3. Fill in the request form:
    - **Title** — A short, descriptive name for your workspace (e.g., "Genomics Research Environment").
    - **Workspace Type** — Select the workspace template from the dropdown. This determines what type of workspace will be provisioned.
    - **Business Justification** — Explain why you need this workspace. This will be reviewed by a TRE Admin when deciding whether to approve your request.

4. If the selected workspace template has fields marked for inclusion in the request form, additional **Workspace Options** will appear below the business justification. Fill these in as needed — they allow you to specify key configuration preferences upfront.

5. Click **Create** to save your request as a draft.

## Step 2: Submit Your Request

Once your draft request is created, you'll see it in the request detail view with a **Draft** status.

1. Review the details of your request to make sure everything is correct.

2. Click **Submit** to send the request for admin review.

3. Your request status will change to **Submitted**.

!!! tip
    You can cancel a request at any time while it is in **Draft** or **Submitted** status by clicking the **Cancel request** button.

## Step 3: Wait for Review

After submitting your request, a TRE Admin will review it. During this time:

- Your request status will show as **Submitted** or **In Review**.
- You can check the status of your request at any time by navigating to the **Workspace Requests** page and clicking on your request.

## Step 4: Check the Outcome

Once reviewed, your request will be either **Approved** or **Rejected**:

- **Approved** — A TRE Admin will deploy the workspace. Once deployed, you'll find the new workspace in the **Workspaces** section of the TRE UI.
- **Rejected** — The reviewer will provide an explanation for why the request was rejected. You can view this in the **Reviews** section of your request detail. You may create a new request that addresses the reviewer's concerns.
