"""
ALAIA — Premium branded HTML email templates.
All OTP/transactional emails use a single consistent design.
"""
from django.core.mail import send_mail
from django.conf import settings


def _base_html(title, heading, body_html, footer_note=""):
    """Wraps content in the ALAIA branded email shell."""
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
</head>
<body style="margin:0;padding:0;background-color:#f5f0e8;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color:#f5f0e8;padding:40px 20px;">
    <tr>
      <td align="center">
        <table role="presentation" width="560" cellspacing="0" cellpadding="0" style="background-color:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(42,37,32,0.08);">

          <!-- Header -->
          <tr>
            <td style="background-color:#2a2520;padding:32px 40px;text-align:center;">
              <h1 style="margin:0;font-size:24px;font-weight:600;letter-spacing:3px;color:#c9b8a8;">ALAIA</h1>
              <p style="margin:6px 0 0;font-size:11px;letter-spacing:1.5px;color:rgba(201,184,168,0.6);text-transform:uppercase;">Architectural Footwear</p>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding:44px 40px 20px;">
              <h2 style="margin:0 0 8px;font-size:20px;font-weight:600;color:#2a2520;letter-spacing:0.5px;">{heading}</h2>
              <div style="width:40px;height:2px;background:#c9b8a8;margin:0 0 24px;border-radius:1px;"></div>
              {body_html}
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding:0 40px 36px;">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                <tr>
                  <td style="border-top:1px solid #eee;padding-top:24px;">
                    {f'<p style="margin:0 0 16px;font-size:12px;color:#999;line-height:1.6;">{footer_note}</p>' if footer_note else ''}
                    <p style="margin:0;font-size:11px;color:#bbb;letter-spacing:0.5px;">
                      &copy; 2025 ALAIA. All rights reserved.<br>
                      Crafting minimalist footwear through architectural design.
                    </p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""


def _otp_body(otp, message_intro):
    """Shared OTP display block."""
    return f"""
<p style="margin:0 0 24px;font-size:14px;color:#555;line-height:1.7;">
  {message_intro}
</p>

<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin:0 0 24px;">
  <tr>
    <td align="center">
      <div style="display:inline-block;background:#f5f0e8;border:1px solid #e5ddd3;border-radius:8px;padding:20px 48px;">
        <span style="font-size:32px;font-weight:700;letter-spacing:8px;color:#2a2520;font-family:'Courier New',monospace;">{otp}</span>
      </div>
    </td>
  </tr>
</table>

<p style="margin:0 0 8px;font-size:13px;color:#888;line-height:1.6;">
  <strong style="color:#666;">⏱ This code expires in 60 seconds.</strong>
</p>
<p style="margin:0;font-size:12px;color:#aaa;line-height:1.6;">
  If you didn't request this code, please ignore this email. Your account remains secure.
</p>
"""


def send_signup_otp(email, otp):
    """OTP email for new account signup verification."""
    body = _otp_body(
        otp,
        "Welcome to ALAIA! To complete your registration, please enter the verification code below:"
    )
    html = _base_html(
        title="Verify Your Email — ALAIA",
        heading="Verify Your Email",
        body_html=body,
        footer_note="You're receiving this email because you signed up for an ALAIA account."
    )
    send_mail(
        subject="ALAIA — Verify Your Email",
        message=f"Your ALAIA verification code is: {otp}",
        from_email=settings.EMAIL_HOST_USER,
        recipient_list=[email],
        html_message=html,
    )


def send_signup_otp_resend(email, otp):
    """Resent OTP email for signup verification."""
    body = _otp_body(
        otp,
        "Here's your new verification code. Please use this to complete your registration:"
    )
    html = _base_html(
        title="New Verification Code — ALAIA",
        heading="New Verification Code",
        body_html=body,
        footer_note="You're receiving this because you requested a new verification code."
    )
    send_mail(
        subject="ALAIA — New Verification Code",
        message=f"Your new ALAIA verification code is: {otp}",
        from_email=settings.EMAIL_HOST_USER,
        recipient_list=[email],
        html_message=html,
    )


def send_password_reset_otp(email, otp):
    """OTP email for password reset."""
    body = _otp_body(
        otp,
        "We received a request to reset your password. Enter the code below to proceed:"
    )
    html = _base_html(
        title="Password Reset — ALAIA",
        heading="Reset Your Password",
        body_html=body,
        footer_note="If you didn't request a password reset, no action is needed."
    )
    send_mail(
        subject="ALAIA — Password Reset Code",
        message=f"Your ALAIA password reset code is: {otp}",
        from_email=settings.EMAIL_HOST_USER,
        recipient_list=[email],
        html_message=html,
    )


def send_email_change_otp(email, otp):
    """OTP email for email address change verification."""
    body = _otp_body(
        otp,
        "You've requested to update your email address. Please verify this new email by entering the code below:"
    )
    html = _base_html(
        title="Email Change Verification — ALAIA",
        heading="Confirm Your New Email",
        body_html=body,
        footer_note="If you didn't request this change, please contact our support team immediately."
    )
    send_mail(
        subject="ALAIA — Confirm Your New Email",
        message=f"Your ALAIA email verification code is: {otp}",
        from_email=settings.EMAIL_HOST_USER,
        recipient_list=[email],
        html_message=html,
    )
