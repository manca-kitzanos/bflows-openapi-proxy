import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from . import settings
import logging

logger = logging.getLogger(__name__)

def send_notification_email(recipient_email, subject, message):
    """
    Send an email notification to the specified recipient.
    
    Args:
        recipient_email (str): The email address of the recipient
        subject (str): The subject of the email
        message (str): The body message of the email
    
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    # Use the provided email or fall back to the default
    recipient = recipient_email or settings.DEFAULT_NOTIFICATION_EMAIL
    
    # Create a multipart message
    msg = MIMEMultipart()
    msg["From"] = settings.DEFAULT_FROM_EMAIL
    msg["To"] = recipient
    msg["Subject"] = subject
    
    # Add message body
    msg.attach(MIMEText(message, "plain"))
    
    try:
        # Create SMTP session
        server = smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT)
        
        # Use TLS if configured
        if settings.EMAIL_USE_TLS:
            server.starttls()
        
        # Login if credentials provided
        if settings.EMAIL_HOST_USER and settings.EMAIL_HOST_PASSWORD:
            server.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
        
        # Send email
        server.send_message(msg)
        server.quit()
        
        logger.info(f"Email notification sent to {recipient}")
        return True
    
    except Exception as e:
        logger.error(f"Failed to send email notification: {str(e)}")
        return False

def send_callback_notification(recipient_email, callback_type, identifier, data=None):
    """
    Send a notification when a callback is received.
    
    Args:
        recipient_email (str): The email to send the notification to
        callback_type (str): The type of callback (e.g. 'company-full', 'negative-event')
        identifier (str): The company identifier
        data (dict, optional): Additional data to include in the notification
    """
    subject = f"Callback Notification: {callback_type} data ready"
    
    message_lines = [
        f"Notification: {callback_type} data is now available",
        f"Identifier: {identifier}",
        "",
        "The requested data has been successfully received and processed.",
        "You can now retrieve the complete information using the API.",
        "",
    ]
    
    if data:
        message_lines.append("Summary of the data:")
        for key, value in data.items():
            if isinstance(value, str) and len(value) < 50:  # Only include short string values
                message_lines.append(f"- {key}: {value}")
    
    message_lines.append("")
    message_lines.append("This is an automated message, please do not reply.")
    
    message = "\n".join(message_lines)
    
    return send_notification_email(recipient_email, subject, message)
