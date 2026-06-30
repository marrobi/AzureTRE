# UI Changes - Visual Guide

This document illustrates the UI improvements made in this PR.

## 1. My Resources Grouping (Issue #2832)

### Before
All user resources were displayed in a single list, making it difficult for workspace owners to find their own resources among resources owned by other researchers.

### After
User resources are now grouped into two sections:

```
┌─────────────────────────────────────────────────────────┐
│ Resources                                    [Refresh] [Create new] │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ My Resources                                            │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐      │
│ │ Windows VM  │ │ Linux VM    │ │ Jupyter     │      │
│ │ researcher1 │ │ researcher1 │ │ researcher1 │      │
│ │ ● Running   │ │ ● Stopped   │ │ ● Running   │      │
│ └─────────────┘ └─────────────┘ └─────────────┘      │
│                                                         │
│ Other Resources                                         │
│ ┌─────────────┐ ┌─────────────┐                       │
│ │ RStudio VM  │ │ Data Science│                       │
│ │ researcher2 │ │ researcher3 │                       │
│ │ ● Running   │ │ ● Deploying │                       │
│ └─────────────┘ └─────────────┘                       │
└─────────────────────────────────────────────────────────┘
```

**Key Changes:**
- "My Resources" section shows resources owned by the logged-in user (based on MSAL account.localAccountId)
- "Other Resources" section shows resources owned by other users
- If user only has their own resources, only "My Resources" section is shown
- If there are only other users' resources, section is labeled "All Resources"

---

## 2. Refresh Buttons (Issue #3983)

Refresh buttons have been added to multiple pages using a consistent Fluent UI IconButton with the Refresh icon (🔄).

### Workspace List Page
```
┌─────────────────────────────────────────────────────────┐
│ Workspaces                               [Create new]   │
├─────────────────────────────────────────────────────────┤
│ [Search: name or ID...] [🔄 Refresh] [Sort] [Clear]    │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐      │
│ │ Research    │ │ Development │ │ Production  │      │
│ │ Workspace   │ │ Workspace   │ │ Workspace   │      │
│ └─────────────┘ └─────────────┘ └─────────────┘      │
└─────────────────────────────────────────────────────────┘
```

### Workspace Services Page
```
┌─────────────────────────────────────────────────────────┐
│ Workspace Services                [🔄] [Create new]     │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────┐ ┌─────────────┐                       │
│ │ Guacamole   │ │ Azure ML    │                       │
│ │ Service     │ │ Workspace   │                       │
│ └─────────────┘ └─────────────┘                       │
└─────────────────────────────────────────────────────────┘
```

### User Resources Page (within Workspace Service)
```
┌─────────────────────────────────────────────────────────┐
│ Resources                            [🔄] [Create new]   │
├─────────────────────────────────────────────────────────┤
│ My Resources                                            │
│ ┌─────────────┐ ┌─────────────┐                       │
│ │ Windows VM  │ │ Linux VM    │                       │
│ └─────────────┘ └─────────────┘                       │
└─────────────────────────────────────────────────────────┘
```

### Shared Services Page
```
┌─────────────────────────────────────────────────────────┐
│ Shared Services                      [🔄] [Create new]  │
├─────────────────────────────────────────────────────────┤
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐      │
│ │ Firewall    │ │ Gitea       │ │ Nexus       │      │
│ └─────────────┘ └─────────────┘ └─────────────┘      │
└─────────────────────────────────────────────────────────┘
```

**Key Changes:**
- Refresh icon button placed consistently in page headers
- Clicking refresh re-fetches data from the API without full page reload
- Button uses standard Fluent UI IconButton component
- Airlock page already had a refresh button (no changes needed)

---

## 3. Automatic Polling (Issue #4204)

User resources now automatically refresh every 30 seconds to keep VM status current.

### Polling Behavior
```
Time: 0s    - User navigates to User Resources page
              ├─ Initial data load
              └─ Polling starts

Time: 30s   - Automatic refresh #1
              └─ VM status updated (Running → Stopping)

Time: 60s   - Automatic refresh #2
              └─ VM status updated (Stopping → Stopped)

Time: 90s   - Automatic refresh #3
              └─ Context menu actions updated

User leaves page
              └─ Polling stops (cleanup via useEffect)
```

**Key Changes:**
- Polling interval: 30 seconds
- Only active while user is viewing the user resources page
- Automatically stops when component unmounts
- Updates VM power states and available actions (Start/Stop buttons)
- Helps keep UI in sync with actual VM state without manual refresh

---

## Technical Implementation

### Files Modified:
1. **WorkspaceServiceItem.tsx** - Added resource grouping logic and polling
2. **WorkspaceList.tsx** - Added refresh button to command bar
3. **WorkspaceServices.tsx** - Added refresh button to header
4. **SharedServices.tsx** - Added refresh button to header
5. **RootLayout.tsx** - Extracted getWorkspaces function for reuse
6. **RootDashboard.tsx** - Pass refresh callback to WorkspaceList
7. **WorkspaceProvider.tsx** - Added refreshWorkspaceServices function

### Key Technologies:
- React hooks (useState, useEffect, useMemo)
- MSAL for user authentication (account.localAccountId)
- Fluent UI IconButton component
- setInterval/clearInterval for polling with proper cleanup
