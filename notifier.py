from typing import Tuple
import smtplib
import logging
import sys
import time
import socket
from email.message import EmailMessage
from email_validator import validate_email, EmailNotValidError
from config_reader import ConfigReader

class SMTPError(Exception):
    pass

class SMTPAuthError(SMTPError):
    pass

class SMTPConnectError(SMTPError):
    pass

class SMTPResponseError(SMTPError):
    pass

class SMTPRecipientsRefusedError(SMTPError):
    pass

class SMTPGenericError(SMTPError):
    pass

class Notifier:
    """
    The Notifier class is responsible for sending alert notifications through email. 

    It is initialized with SMTP server details and the recipient's email address. It validates
    the email address format and creates an email with a specific subject and body. In case of 
    an error while sending the email, it will retry up to 6 times before stopping, with a delay
    between attempts that does not exceed 12 hours.

    The class also provides a method for sending a test email to verify that the email functionality
    is working correctly. It also checks for network connection availability in case of email 
    sending failure.
    
    Attributes:
        smtp_server (str): The SMTP server to use for sending emails.
        smtp_port (int): The port on the SMTP server to use.
        smtp_username (str): The username to authenticate with the SMTP server.
        smtp_password (str): The password to authenticate with the SMTP server.
        recipient (str): The recipient's email address.
    """
    def __init__(self, smtp_server, smtp_port, smtp_username, smtp_password, recipient):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.smtp_username = smtp_username
        self.smtp_password = smtp_password
        self.recipient = recipient
        self.config = ConfigReader()
        self.last_alert_times = {"CPU": 0, "RAM": 0, "Disks": 0, "GPU Usage": 0, "GPU Memory Usage": 0, "GPU Temperature": 0}

    def validate_email(self, email: str) -> bool:
        """Validate email format."""
        try:
            # validate and get info
            validate_email(email)
            # email is valid
            return True
        except EmailNotValidError as err:
            # email is not valid, exception message is human-readable
            print(str(err))
            return False

    def create_email(self, subject: str, body: str) -> EmailMessage:
        """Creates the email."""
        msg = EmailMessage()
        msg.set_content(body)
        msg["Subject"] = subject
        msg["From"] = self.smtp_username

        # Check if email format is valid before setting
        if self.validate_email(self.recipient):
            msg["To"] = self.recipient
        else:
            raise ValueError(f"'{self.recipient}' is not a valid email format.")

        msg["Importance"] = "High"
        return msg

    def send_alert(self, subject, body):
        """Sends an alert email and handles potential errors."""
        msg = self.create_email(subject, "\n" + body)
        retry_count = 0
        while retry_count < 6:
            try:
                with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                    server.starttls()
                    server.login(self.smtp_username, self.smtp_password)
                    server.send_message(msg)
                logging.info("Alert email sent successfully.")
                return
            except smtplib.SMTPAuthenticationError as auth_err:
                raise SMTPAuthError("SMTP authentication error occurred. Please check your SMTP username and password (Learn more at https://support.google.com/mail/?p=BadCredentials).") from auth_err
            except (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected) as server_err:
                raise SMTPConnectError("Unable to connect to the SMTP server. Please check your SMTP server settings.") from server_err
            except smtplib.SMTPResponseException as exc_err:
                raise SMTPResponseError("Unexpected response from the SMTP server. Please check your SMTP server settings.") from exc_err
            except smtplib.SMTPRecipientsRefused as recipient_err:
                raise SMTPRecipientsRefusedError(f"Recipient refused: {self.recipient}. Please check the recipient's email address.") from recipient_err
            except (smtplib.SMTPException, OSError):
                self.check_network_connection()
                wait_time = self.enforce_max_wait_time(self.config.get_value('time', 'email_retry_delay', data_type=int))
                wait_time_str, timeframe = self.format_wait_time(wait_time)
                logging.error("Failed to send alert email. Retrying in %.0f %s.", wait_time_str, timeframe)
                time.sleep(wait_time)
                retry_count += 1
        if retry_count == 6:
            logging.critical("Failed to send alert email after 6 retries. Exiting the program.")
            sys.exit(1)

    def alert_format(self, device_name: str, resource_name: str, threshold: int) -> None:
        # Retrieve the cooldown time from the configuration (in seconds)
        cooldown_time = self.config.get_value('time', 'alert_cooldown_time', data_type=int)

        # Initialize self.last_alert_times[resource_name] if it hasn't been initialized yet
        if resource_name not in self.last_alert_times:
            self.last_alert_times[resource_name] = 0
            logging.debug(f'Initialized alert time for {resource_name}. Check last_alert_times and resource_name in the compoment if dict name match.')

        # Only proceed if enough time has passed since the last alert
        if time.time() - self.last_alert_times[resource_name] > cooldown_time:
            subject = self.config.get_value('email', 'alert_subject_template').format(device_name=device_name, resource_name=resource_name)
            body = self.config.get_value('email', 'alert_body_template').format(device_name=device_name, resource_name=resource_name, threshold=threshold)
            self.send_alert(subject, body)
            # Update the last alert time
            self.last_alert_times[resource_name] = time.time()
            logging.info(f'Alert for {resource_name} has been sent, updated last_alert_time count.')
        else:
            logging.info(f'Not enough time has passed since the last alert for {resource_name}. No alert sent.')

    def send_test_email(self):
        """Check to see if the email is working."""
        host = socket.gethostname()
        try:
            subject = f"System Health Monitor Test Email from {host} "
            body = "This is a test email sent by the system monitoring script. If you're reading this, then the email functionality is working correctly."
            self.send_alert(subject, body)
        except KeyboardInterrupt:
            logging.info("System monitoring stopped")
            sys.exit(0)

    def check_network_connection(self, host="www.google.com", port=80):
        """Check network connection for email error."""
        try:
            socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
            return True
        except (socket.error, socket.gaierror, socket.timeout) as network_err:
            logging.error("Network connection unavailable. %s", network_err)
            return False

    def format_wait_time(self, wait_time: int) -> Tuple[int, str]:
        """Formatting the waiting timeframe."""
        if wait_time < 60:
            return wait_time, 'seconds'
        elif wait_time < 3600:
            return wait_time / 60, 'minutes'
        else:
            return wait_time / 3600, 'hours'

    def enforce_max_wait_time(self, wait_time: int) -> int:
        """Enforces a maximum wait time of 12 hours."""
        if wait_time > 43200:
            logging.warning("Wait time exceeded limit of 12 hours, setting to default 1 hours.")
            return 3600
        return wait_time

# pylint: disable=all