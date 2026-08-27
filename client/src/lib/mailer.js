import nodemailer from "nodemailer";

let _transporter = null;

function getTransporter() {
  if (_transporter) return _transporter;
  _transporter = nodemailer.createTransport({
    host: "smtp.gmail.com",
    port: 465,
    secure: true,
    auth: {
      user: process.env.EMAIL_USER,
      pass: process.env.EMAIL_APP_PASSWORD,
    },
  });
  return _transporter;
}

export async function sendEmail({ to, subject, html }) {
  const transporter = getTransporter();
  return transporter.sendMail({
    from: process.env.EMAIL_USER,
    to,
    subject,
    html,
  });
}

export async function sendResetPasswordEmail({ to, rawToken }) {
  const appUrl = process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3000";
  const resetUrl = `${appUrl}/reset-password/${rawToken}`;

  const html = `
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin:0;padding:0;background-color:#f4f5f7;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
      <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f5f7;padding:40px 20px;">
        <tr>
          <td align="center">
            <table width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background-color:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.08);">
              <tr>
                <td style="padding:32px 40px 16px;">
                  <h1 style="margin:0;font-size:20px;font-weight:700;color:#1a1a2e;">LedgerLens</h1>
                </td>
              </tr>
              <tr>
                <td style="padding:8px 40px 24px;">
                  <h2 style="margin:0;font-size:18px;font-weight:600;color:#1a1a2e;">Reset your password</h2>
                </td>
              </tr>
              <tr>
                <td style="padding:0 40px 24px;">
                  <p style="margin:0;font-size:14px;line-height:1.6;color:#4a4a68;">
                    We received a request to reset the password for your LedgerLens account.
                    Click the button below to choose a new password:
                  </p>
                </td>
              </tr>
              <tr>
                <td style="padding:0 40px 32px;">
                  <a href="${resetUrl}" style="display:inline-block;background-color:#4f46e5;color:#ffffff;font-size:14px;font-weight:600;text-decoration:none;padding:10px 24px;border-radius:8px;">
                    Reset password
                  </a>
                </td>
              </tr>
              <tr>
                <td style="padding:0 40px 24px;">
                  <p style="margin:0;font-size:13px;line-height:1.6;color:#6b7280;">
                    This link expires in <strong>30 minutes</strong>.
                  </p>
                  <p style="margin:12px 0 0;font-size:13px;line-height:1.6;color:#6b7280;">
                    If you didn't request a password reset, you can safely ignore this email.
                    Your password will remain unchanged.
                  </p>
                </td>
              </tr>
              <tr>
                <td style="padding:16px 40px;border-top:1px solid #eef0f4;">
                  <p style="margin:0;font-size:12px;color:#9ca3af;">
                    LedgerLens &mdash; Financial reconciliation, without the manual investigation.
                  </p>
                </td>
              </tr>
            </table>
          </td>
        </tr>
      </table>
    </body>
    </html>
  `;

  return sendEmail({
    to,
    subject: "Reset your LedgerLens password",
    html,
  });
}

export async function sendInvitationEmail({ to, workspaceName, invitedByName, acceptUrl }) {
  const html = `
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin:0;padding:0;background-color:#f4f5f7;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
      <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f5f7;padding:40px 20px;">
        <tr>
          <td align="center">
            <table width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background-color:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.08);">
              <tr>
                <td style="padding:32px 40px 16px;">
                  <h1 style="margin:0;font-size:20px;font-weight:700;color:#1a1a2e;">LedgerLens</h1>
                </td>
              </tr>
              <tr>
                <td style="padding:8px 40px 24px;">
                  <h2 style="margin:0;font-size:18px;font-weight:600;color:#1a1a2e;">You've been invited to join a workspace</h2>
                </td>
              </tr>
              <tr>
                <td style="padding:0 40px 24px;">
                  <p style="margin:0;font-size:14px;line-height:1.6;color:#4a4a68;">
                    <strong>${invitedByName}</strong> has invited you to collaborate in the
                    <strong>${workspaceName}</strong> workspace on LedgerLens.
                  </p>
                </td>
              </tr>
              <tr>
                <td style="padding:0 40px 32px;">
                  <a href="${acceptUrl}" style="display:inline-block;background-color:#4f46e5;color:#ffffff;font-size:14px;font-weight:600;text-decoration:none;padding:10px 24px;border-radius:8px;">
                    Accept invitation
                  </a>
                </td>
              </tr>
              <tr>
                <td style="padding:0 40px 24px;">
                  <p style="margin:0;font-size:13px;line-height:1.6;color:#6b7280;">
                    This invitation expires in <strong>7 days</strong>.
                  </p>
                  <p style="margin:12px 0 0;font-size:13px;line-height:1.6;color:#6b7280;">
                    If you don't have a LedgerLens account yet, you'll be able to create one
                    after clicking the link above.
                  </p>
                </td>
              </tr>
              <tr>
                <td style="padding:16px 40px;border-top:1px solid #eef0f4;">
                  <p style="margin:0;font-size:12px;color:#9ca3af;">
                    LedgerLens &mdash; Financial reconciliation, without the manual investigation.
                  </p>
                </td>
              </tr>
            </table>
          </td>
        </tr>
      </table>
    </body>
    </html>
  `;

  return sendEmail({
    to,
    subject: `You've been invited to ${workspaceName} on LedgerLens`,
    html,
  });
}
