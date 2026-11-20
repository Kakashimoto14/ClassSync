"""HTML and plain-text renderers for transactional account verification mail."""

# Email HTML uses long, intentionally inline attributes for broad client compatibility.
# ruff: noqa: E501

from html import escape


def render_verification_email(code: str, app_url: str) -> tuple[str, str]:
    safe_code = escape(code, quote=True)
    safe_login_url = escape(app_url.rstrip("/") + "/auth/login", quote=True)
    html = f"""<!doctype html>
<html lang="en"><body style="margin:0;padding:24px 12px;background:#F5F7FA;color:#1E293B;font-family:Arial,Helvetica,sans-serif">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#F5F7FA"><tr><td align="center">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:560px;background:#FFFFFF;border:1px solid #E2E8F0;border-radius:14px;overflow:hidden">
<tr><td style="height:5px;background:#872E49;font-size:0">&nbsp;</td></tr>
<tr><td style="padding:24px 28px;border-bottom:1px solid #F1F5F9">
<strong style="font-size:20px;color:#0F172A">Class<span style="color:#872E49">Sync</span></strong>
<div style="margin-top:4px;color:#64748B;font-size:11px;letter-spacing:1px;text-transform:uppercase">Colegio de Montalban · Campus Scheduling Portal</div></td></tr>
<tr><td style="padding:26px 28px"><h1 style="margin:0 0 10px;font-size:22px;color:#0F172A">Verify your sign-in</h1>
<p style="margin:0 0 18px;color:#475569;font-size:14px;line-height:1.6">Enter this one-time code in ClassSync to continue. It expires in five minutes and can only be used once.</p>
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin-bottom:20px;background:#F8FAFC;border:1px solid #E2E8F0;border-radius:12px"><tr><td align="center" style="padding:18px 12px">
<div style="margin-bottom:8px;color:#64748B;font-size:11px;font-weight:bold;letter-spacing:1px;text-transform:uppercase">Your verification code</div>
<div style="font-family:'Courier New',monospace;color:#0F172A;font-size:30px;font-weight:bold;letter-spacing:8px;padding-left:8px">{safe_code}</div>
<div style="margin-top:8px;color:#64748B;font-size:12px">This code expires in <strong>5 minutes</strong> · Single use</div></td></tr></table>
<p style="margin:0 0 18px;text-align:center"><a href="{safe_login_url}" style="display:inline-block;padding:11px 24px;border-radius:9px;background:#872E49;color:#FFFFFF;font-size:14px;font-weight:bold;text-decoration:none">Open ClassSync</a></p>
<p style="margin:0 0 18px;color:#475569;font-size:13px;text-align:center">If the button does not work, <a href="{safe_login_url}" style="color:#872E49;font-weight:bold">click here to continue</a>.</p>
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#FFFBEB;border:1px solid #FDE68A;border-radius:9px"><tr><td style="padding:11px 13px;color:#92400E;font-size:12px;line-height:1.5"><strong>Did not request this?</strong> Ignore this email. Never share your code or password.</td></tr></table></td></tr>
<tr><td align="center" style="padding:17px 24px;background:#F8FAFC;border-top:1px solid #F1F5F9;color:#64748B;font-size:11px">ClassSync · Academic &amp; Scheduling Services<br/>Need help? Contact the Office of the Registrar.</td></tr>
</table></td></tr></table></body></html>"""
    text = (
        f"Your ClassSync verification code is {code}. It expires in 5 minutes and can only be "
        "used once. Open ClassSync from this email, or click here to continue. If you did not "
        "request this, ignore this message."
    )
    return html, text


def render_password_reset_email(reset_url: str) -> tuple[str, str]:
    safe_reset_url = escape(reset_url, quote=True)
    html = f"""<!doctype html>
<html lang="en"><body style="margin:0;padding:24px 12px;background:#F5F7FA;color:#1E293B;font-family:Arial,Helvetica,sans-serif">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#F5F7FA"><tr><td align="center">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:560px;background:#FFFFFF;border:1px solid #E2E8F0;border-radius:14px;overflow:hidden">
<tr><td style="height:5px;background:#872E49;font-size:0">&nbsp;</td></tr>
<tr><td style="padding:24px 28px;border-bottom:1px solid #F1F5F9">
<strong style="font-size:20px;color:#0F172A">Class<span style="color:#872E49">Sync</span></strong>
<div style="margin-top:4px;color:#64748B;font-size:11px;letter-spacing:1px;text-transform:uppercase">Colegio de Montalban · Campus Scheduling Portal</div></td></tr>
<tr><td style="padding:26px 28px"><h1 style="margin:0 0 10px;font-size:22px;color:#0F172A">Reset your password</h1>
<p style="margin:0 0 20px;color:#475569;font-size:14px;line-height:1.6">Use the button below to choose a new ClassSync password. If you did not request this change, you can ignore this message.</p>
<p style="margin:0 0 18px;text-align:center"><a href="{safe_reset_url}" style="display:inline-block;padding:12px 26px;border-radius:9px;background:#872E49;color:#FFFFFF;font-size:14px;font-weight:bold;text-decoration:none">Reset Password</a></p>
<p style="margin:0;color:#475569;font-size:13px;text-align:center">If the button does not work, <a href="{safe_reset_url}" style="color:#872E49;font-weight:bold">click here to continue</a>.</p></td></tr>
<tr><td align="center" style="padding:17px 24px;background:#F8FAFC;border-top:1px solid #F1F5F9;color:#64748B;font-size:11px">ClassSync · Academic &amp; Scheduling Services<br/>Need help? Contact the Office of the Registrar.</td></tr>
</table></td></tr></table></body></html>"""
    text = (
        "A request was made to reset your ClassSync password. Open the Reset Password button "
        "in the HTML version of this email to continue. If you did not request this, ignore "
        "this message."
    )
    return html, text
