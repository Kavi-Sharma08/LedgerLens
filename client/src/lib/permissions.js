// Workspace authorization model (mirrors server/app/models/enums.py — keep
// these two files' permission keys in sync). The backend remains the single
// enforcement point; this module only drives UI affordances from the same
// owner-controlled grants that the server returns on WorkspacePublic
// .rolePermissions and from the member's role.
//
// Two layers live here:
//   1. The granular permission keys the server actually enforces
//      (ALL_PERMISSIONS / DEFAULT_ROLE_PERMISSIONS).
//   2. A small set of higher-level *capabilities* that bundle those keys for
//      the permission editor. A capability maps to one or more granular keys;
//      toggling a capability in the UI simply edits the same role_permissions
//      document the backend trusts.
//
// No second authorization system is created: capability -> permission expansion
// is a UI convenience. The server still checks the granular keys directly.

// --- Granular permissions (server-authoritative) ---------------------------

export const ALL_PERMISSIONS = [
  "view_data",
  "manage_sources",
  "upload_files",
  "run_reconciliation",
  "approve_matches",
  "reject_matches",
  "manage_exceptions",
  "invite_members",
  "manage_members",
  "view_audit_log",
  "manage_workspace_settings",
];

export const PERMISSION_LABELS = {
  view_data: "View financial data",
  manage_sources: "Manage sources",
  upload_files: "Upload files",
  run_reconciliation: "Run reconciliation",
  approve_matches: "Approve matches",
  reject_matches: "Reject matches",
  manage_exceptions: "Manage exceptions",
  invite_members: "Invite members",
  manage_members: "Manage members & roles",
  view_audit_log: "View audit log",
  manage_workspace_settings: "Manage workspace settings",
};

// Baseline grants used to seed a new workspace. MEMBER and VIEWER start
// read-only; operational actions are only enabled when the owner grants them.
export const DEFAULT_ROLE_PERMISSIONS = {
  ADMIN: [
    "view_data",
    "manage_sources",
    "upload_files",
    "run_reconciliation",
    "approve_matches",
    "reject_matches",
    "manage_exceptions",
    "invite_members",
    "manage_members",
    "view_audit_log",
  ],
  MEMBER: ["view_data"],
  VIEWER: ["view_data"],
};

// --- Higher-level capabilities (UI grouping of granular keys) --------------

// Each capability is a human-readable bundle the Owner can toggle at once.
// `permissions` lists every granular server key the capability implies.
export const CAPABILITIES = [
  {
    id: "view_financial_data",
    name: "View financial data",
    group: "Financial Data",
    description:
      "See transactions, financial sources, reconciliation results, and exceptions in this workspace.",
    permissions: ["view_data"],
  },
  {
    id: "manage_financial_data",
    name: "Manage financial data",
    group: "Financial Data",
    description:
      "Create and manage financial sources, and upload statement files to import records.",
    permissions: ["manage_sources", "upload_files"],
  },
  {
    id: "run_reconciliation",
    name: "Run reconciliation",
    group: "Reconciliation",
    description:
      "Start reconciliation runs that compare records across your sources.",
    permissions: ["run_reconciliation"],
  },
  {
    id: "review_reconciliation",
    name: "Review reconciliation",
    group: "Reconciliation",
    description:
      "Review matched records and approve or reject the engine's matches.",
    permissions: ["approve_matches", "reject_matches"],
  },
  {
    id: "manage_exceptions",
    name: "Manage exceptions",
    group: "Exceptions",
    description:
      "Investigate flagged exceptions, update their status, and add notes.",
    permissions: ["manage_exceptions"],
  },
  {
    id: "manage_members",
    name: "Manage members",
    group: "Workspace",
    description:
      "Invite people to the workspace, remove members, and change their roles.",
    permissions: ["invite_members", "manage_members"],
  },
  {
    id: "view_audit_log",
    name: "View audit log",
    group: "Workspace",
    description:
      "Read the immutable record of important actions in this workspace.",
    permissions: ["view_audit_log"],
  },
  {
    id: "manage_settings",
    name: "Manage settings",
    group: "Workspace",
    description: "Rename the workspace and manage role permissions.",
    permissions: ["manage_workspace_settings"],
  },
];

export const CAPABILITY_BY_ID = Object.fromEntries(
  CAPABILITIES.map((c) => [c.id, c])
);

// Default capability bundles, derived from DEFAULT_ROLE_PERMISSIONS.
const DEFAULT_CAPABILITIES = {
  ADMIN: [
    "view_financial_data",
    "manage_financial_data",
    "run_reconciliation",
    "review_reconciliation",
    "manage_exceptions",
    "manage_members",
    "view_audit_log",
  ],
  MEMBER: ["view_financial_data"],
  VIEWER: ["view_financial_data"],
};

export const DEFAULT_ROLE_CAPABILITIES = DEFAULT_CAPABILITIES;

// --- Helpers ---------------------------------------------------------------

/**
 * Whether a member with `role` holds the granular `permission`, given the
 * workspace's owner-controlled per-role grants. The OWNER always retains
 * every permission. Unconfigured workspaces fall back to the defaults,
 * matching the server.
 */
export function hasPermission(role, rolePermissions, permission) {
  if (role === "OWNER") return ALL_PERMISSIONS.includes(permission);
  const configured = rolePermissions && Object.keys(rolePermissions).length > 0;
  const grants = configured
    ? rolePermissions[role] || []
    : DEFAULT_ROLE_PERMISSIONS[role] || [];
  return grants.includes(permission);
}

/**
 * Whether a member with `role` holds the higher-level `capabilityId`. A
 * capability is held when every granular permission it implies is granted.
 * The OWNER always holds every capability.
 */
export function hasCapability(role, rolePermissions, capabilityId) {
  const capability = CAPABILITY_BY_ID[capabilityId];
  if (!capability) return false;
  return capability.permissions.every((permission) =>
    hasPermission(role, rolePermissions, permission)
  );
}

/**
 * The set of capability ids currently held by `role` for this workspace.
 * Returns a stable array ([] when nothing is held).
 */
export function getGrantedCapabilities(role, rolePermissions) {
  return CAPABILITIES.filter((c) => hasCapability(role, rolePermissions, c.id)).map(
    (c) => c.id
  );
}

/**
 * Expand a list of capability ids into the granular permission keys they
 * imply (deduplicated). Used by the permission editor to persist grants
 * through the existing role_permissions endpoint.
 */
export function expandCapabilities(capabilityIds) {
  const set = new Set();
  for (const id of capabilityIds) {
    const capability = CAPABILITY_BY_ID[id];
    if (capability) capability.permissions.forEach((p) => set.add(p));
  }
  return [...set];
}

/**
 * Granular permission keys the given role currently holds, as a Set.
 */
export function getGrantedPermissions(role, rolePermissions) {
  if (role === "OWNER") return new Set(ALL_PERMISSIONS);
  const configured = rolePermissions && Object.keys(rolePermissions).length > 0;
  const grants = configured
    ? rolePermissions[role] || []
    : DEFAULT_ROLE_PERMISSIONS[role] || [];
  return new Set(grants);
}

/**
 * The capability/profile object handed to DashboardProvider, resolving the
 * member's role and each permission flag from server data. Pure (server-safe)
 * so the server layout can build it without touching the client context module.
 */
export function buildDashboardProfile({ role, rolePermissions, workspaceId }) {
  const can = {
    viewData: hasPermission(role, rolePermissions, "view_data"),
    viewAudit: hasPermission(role, rolePermissions, "view_audit_log"),
    manageSettings: hasPermission(role, rolePermissions, "manage_workspace_settings"),
    manageMembers: hasPermission(role, rolePermissions, "manage_members"),
    inviteMembers: hasPermission(role, rolePermissions, "invite_members"),
    manageSources: hasPermission(role, rolePermissions, "manage_sources"),
    uploadFiles: hasPermission(role, rolePermissions, "upload_files"),
    runReconciliation: hasPermission(role, rolePermissions, "run_reconciliation"),
    approveMatches: hasPermission(role, rolePermissions, "approve_matches"),
    rejectMatches: hasPermission(role, rolePermissions, "reject_matches"),
    manageExceptions: hasPermission(role, rolePermissions, "manage_exceptions"),
  };
  return { role, rolePermissions, workspaceId, can };
}
