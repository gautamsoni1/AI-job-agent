import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import structlog

from app.config import get_settings

logger = structlog.get_logger()
settings = get_settings()


class EmailService:
    async def _send(self, to_email: str, subject: str, html_body: str) -> bool:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_USERNAME}>"
            msg["To"] = to_email
            msg.attach(MIMEText(html_body, "html"))

            await aiosmtplib.send(
                msg,
                hostname=settings.EMAIL_HOST,
                port=settings.EMAIL_PORT,
                username=settings.EMAIL_USERNAME,
                password=settings.EMAIL_PASSWORD,
                start_tls=True,
            )
            logger.info("email_sent", to=to_email, subject=subject)
            return True
        except Exception as e:
            logger.error("email_send_failed", to=to_email, error=str(e))
            return False

    async def send_verification_email(self, email: str, first_name: str, token: str) -> bool:
        verify_url = f"{settings.FRONTEND_URL}/verify-email?token={token}"
        html = f"""
        <html><body>
        <h2>Welcome to AI Job Agent, {first_name}!</h2>
        <p>Please verify your email address to get started.</p>
        <a href="{verify_url}" style="background:#4F46E5;color:white;padding:12px 24px;text-decoration:none;border-radius:6px;">
            Verify Email
        </a>
        <p>Or copy this link: {verify_url}</p>
        <p>This link expires in 24 hours.</p>
        </body></html>
        """
        return await self._send(email, "Verify your AI Job Agent account", html)

    async def send_password_reset_email(self, email: str, first_name: str, token: str) -> bool:
        reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token}"
        html = f"""
        <html><body>
        <h2>Password Reset Request</h2>
        <p>Hi {first_name}, we received a request to reset your password.</p>
        <a href="{reset_url}" style="background:#DC2626;color:white;padding:12px 24px;text-decoration:none;border-radius:6px;">
            Reset Password
        </a>
        <p>Or copy this link: {reset_url}</p>
        <p>This link expires in 1 hour. If you didn't request this, ignore this email.</p>
        </body></html>
        """
        return await self._send(email, "Reset your AI Job Agent password", html)

    async def send_application_notification(self, email: str, first_name: str, company: str, role: str) -> bool:
        html = f"""
        <html><body>
        <h2>Application Submitted!</h2>
        <p>Hi {first_name}, your application for <strong>{role}</strong> at <strong>{company}</strong> has been tracked.</p>
        <p>Your AI Job Agent is monitoring the status for you.</p>
        </body></html>
        """
        return await self._send(email, f"Application tracked: {role} at {company}", html)

    async def send_job_match_notification(self, email: str, first_name: str, job_count: int) -> bool:
        html = f"""
        <html><body>
        <h2>New Job Matches Found!</h2>
        <p>Hi {first_name}, your AI Job Agent found <strong>{job_count} new job matches</strong> for you.</p>
        <p>Log in to view your personalized job recommendations with AI scores.</p>
        </body></html>
        """
        return await self._send(email, f"🎯 {job_count} new job matches found", html)