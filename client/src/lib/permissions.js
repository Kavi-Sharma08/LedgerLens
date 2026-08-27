// Workspace authorization model (mirrors server/app/models/enums.py — keep
// these two files in sync). The backend remains the single enforcement point;
// this module only drives UI affordances from the same owner-controlled grants
// that the server returns on WorkspacePublic.rolePermissions.

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

/**
 * Whether a member with `role` holds `permission`, given the workspace's
 * owner-controlled per-role grants. The OWNER always retains every permission.
 * An unconfigured workspace (empty/None grants) falls back to the defaults,
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
