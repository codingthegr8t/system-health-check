import smtplib
import logging
import sys
import time
import socket
from email.message import EmailMessage
from email_validator import validate_email, EmailNotValidError
from config_reader import ConfigReader
from time_manager import TimeManager

class SMTPError(Exception):
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
        smtp_server: The SMTP server to use for sending emails.
        smtp_port: The port on the SMTP server to use.
        smtp_username: The username to authenticate with the SMTP server.
        smtp_password: The password to authenticate with the SMTP server.
        recipient: The recipient's email address.
    """

    def __init__(self, smtp_server: str, smtp_port: int, smtp_username: str, smtp_password: str, recipient: str):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.smtp_username = smtp_username
        self.smtp_password = smtp_password
        self.recipient = recipient
        self.config = ConfigReader()
        self.alerts_send_tracker = {}

    def validate_email(self, email: str) -> bool:
        """Validate email format."""
        try:
            # validate and get info
            validate_email(email)
            # email is valid
            return True
        except EmailNotValidError as err:
            # email is not valid, exception message
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
        MAX_RETRY = 6
        while retry_count < MAX_RETRY:
            try:
                with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                    server.starttls()
                    server.login(self.smtp_username, self.smtp_password)
                    server.send_message(msg)
                logging.info("✉ E-mail was successfully delivered.")
                return
            except smtplib.SMTPAuthenticationError as auth_err:
                raise SMTPError("SMTP authentication error occurred. Please check your SMTP username and password (Learn more at https://support.google.com/mail/?p=BadCredentials).") from auth_err
            except (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected, smtplib.SMTPResponseException) as server_err:
                raise SMTPError("Unable to connect to the SMTP server. Please check your SMTP server settings.") from server_err
            except smtplib.SMTPRecipientsRefused as recipient_err:
                raise SMTPError(f"Recipient refused: {self.recipient}. Please check the recipient's email address.") from recipient_err
            except (smtplib.SMTPException, OSError):
                self.check_network_connection()
                wait_time = TimeManager.enforce_max_wait_time(self.config.get_value('time', 'email_retry_delay', data_type=int))
                wait_time_str, timeframe = TimeManager.format_wait_time(wait_time)
                logging.error("❌ Failed to send alert email. Retrying in %.0f %s.", wait_time_str, timeframe)
                time.sleep(wait_time)
                retry_count += 1
        if retry_count == MAX_RETRY:
            logging.critical("❌ Failed to send alert email after 6 retries. Exiting the program.")
            sys.exit(1)

    def alert_format(self, device_name: str, resource_name: str, threshold: int) -> None:
        # Retrieve the cooldown time from the configuration (in seconds)
        cooldown_time = self.config.get_value('time', 'alert_cooldown_time', data_type=int)

        # Initialize self.alerts_send_tracker[resource_name] if it hasn't been initialized yet
        if resource_name not in self.alerts_send_tracker:
            self.alerts_send_tracker[resource_name] = 0
            logging.debug(f'Initialized alert time for {resource_name}. Check for name mismatch in var self.alerts_send_tracker and var [resource_name] in the health_check compoment of system_monitor.')

        # Only proceed if enough time has passed since the last alert
        if time.time() - self.alerts_send_tracker[resource_name] > cooldown_time:
            subject = self.config.get_value('email', 'alert_subject_template').format(device_name=device_name, resource_name=resource_name)
            body = self.config.get_value('email', 'alert_body_template').format(device_name=device_name, resource_name=resource_name, threshold=threshold)
            self.send_alert(subject, body)
            # Update the last alert time
            self.alerts_send_tracker[resource_name] = time.time()
            logging.debug('Alert for %s has been sent, updated last_alert_time count.', resource_name)
        else:
            logging.debug('Not enough time has passed since the last alert for %s. No alert sent.', resource_name)

    def send_test_email(self):
        """Check to see if the email function is working."""
        host = socket.gethostname()
        try:
            subject = f"System Health Monitor Test Email from {host} "
            body = "This is a test email sent by the system monitoring script. If you're reading this, then the email functionality is working correctly."
            self.send_alert(subject, body)
        # This is for when the email test didn't send succesfully
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

# pylint: disable=all