import smtplib
import logging
import sys
import time
import socket
from email.message import EmailMessage
from configuration import Configuration

class Notifier:
    def __init__(self, smtp_server, smtp_port, smtp_username, smtp_password, recipient):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.smtp_username = smtp_username
        self.smtp_password = smtp_password
        self.recipient = recipient
        self.config = Configuration()

    def send_test_email(self):
        try:
            subject = "Test Email from System Health Monitor"
            body = "This is a test email sent by the system monitoring script. If you're reading this, then the email functionality is working correctly."
            self.send_alert(subject, body)
        except KeyboardInterrupt:
            logging.info("System monitoring stopped")
            sys.exit(0)

    def create_email(self, subject, body):
        msg = EmailMessage()
        msg.set_content(body)
        msg["Subject"] = subject
        msg["From"] = self.smtp_username
        msg["To"] = self.recipient
        msg["Importance"] = "High"
        return msg

    def send_alert(self, subject, body):
        """Sends an alert email using SMTP"""
        msg = self.create_email(subject, "\n" + body)
        retry_count = 0
        while retry_count < 6:
            result = self.try_send_message(msg)
            if result == "success":
                logging.info("Alert email sent successfully.")
                return
            elif result == "auth_error":
                logging.error("SMTP authentication error occurred. Please check your SMTP username and password (Learn more at https://support.google.com/mail/?p=BadCredentials).")
                return
            elif result == "connect_error":
                logging.error(f"Unable to connect to the SMTP server. Please check your SMTP server settings.")
                return
            elif result == "response_error":
                logging.error(f"Unexpected response from the SMTP server. Please check your SMTP server settings.")
                return
            elif result == "recipients_refused":
                logging.error(f"Recipient refused: {self.recipient}. Please check the recipient's email address.")
                return
            else:
                check_network_connection()
                wait_time = enforce_max_wait_time(self.config.wait_time_to_resend_email)
                wait_time_str, timeframe = format_wait_time(wait_time)
                logging.error(f"Failed to send alert email. Retrying in {wait_time_str:.0f} {timeframe}.")
                time.sleep(wait_time)
                retry_count += 1

        if retry_count == 6:
            logging.critical(f"Failed to send alert email after {6} retries. Exiting the program.")
            sys.exit(1)

    def try_send_message(self, msg):
        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
            return "success"
        except smtplib.SMTPAuthenticationError:
            return "auth_error"
        except (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected):
            return "connect_error"
        except smtplib.SMTPResponseException:
            return "response_error"
        except smtplib.SMTPRecipientsRefused:
            return "recipients_refused"
        except (smtplib.SMTPException, OSError):
            return "other_error"

    def alert_format(self, device_name, resource_name, threshold):
        subject = self.config.alert_subject_template.format(device_name=device_name, resource_name=resource_name)
        body = self.config.alert_body_template.format(device_name=device_name, resource_name=resource_name, threshold=threshold)
        self.send_alert(subject, body)

def check_network_connection(host="www.google.com", port=80):
    """Check network connection for email error """
    try:
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except Exception as e:
        logging.error(f"Network connection unavailable. {e}")
        return False

def format_wait_time(wait_time):
    """Formatting the waiting timeframe"""
    if wait_time < 60:
        return wait_time, 'seconds'
    elif wait_time < 3600:
        return wait_time / 60, 'minutes'
    else:
        return wait_time / 3600, 'hours'
    
def enforce_max_wait_time(wait_time):
    """Enforces a maximum wait time of 12 hours."""
    if wait_time > 43200:
        logging.warning("Wait time exceeded limit of 12 hours, setting to default 1 hours.")
        return 3600
    return wait_time