import smtplib
import logging
import sys
import time
import socket
from email.message import EmailMessage
from email_validator import validate_email, EmailNotValidError
from configuration import Configuration

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
        self.config = Configuration()

    def create_email(self, subject, body):
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

    def validate_email(self, email):
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

    def send_alert(self, subject, body):
        """Sends an alert email and handles potential errors."""
        msg = self.create_email(subject, "\n" + body)
        retry_count = 0
        while retry_count < 6:
            try:
                self.try_send_message(msg)
                logging.info("Alert email sent successfully.")
                return
            except SMTPAuthError as err:
                logging.error(str(err))
                return
            except SMTPConnectError as err:
                logging.error(str(err))
                return
            except SMTPResponseError as err:
                logging.error(str(err))
                return
            except SMTPRecipientsRefusedError as err:
                logging.error(str(err))
                return
            except SMTPGenericError:
                self.check_network_connection()
                wait_time = self.enforce_max_wait_time(self.config.wait_time_to_resend_email)
                wait_time_str, timeframe = self.format_wait_time(wait_time)
                logging.error("Failed to send alert email. Retrying in %.0f %s.", wait_time_str, timeframe)
                time.sleep(wait_time)
                retry_count += 1
        if retry_count == 6:
            logging.critical("Failed to send alert email after 6 retries. Exiting the program.")
            sys.exit(1)

    def try_send_message(self, msg):
        """
        Tries to send an email message using SMTP. 

        This function creates a connection with the SMTP server, logs in using the SMTP username 
        and password, and sends the email message. If any error occurs during this process, 
        it raises an exception specific to that error type.

        Parameters:
            msg (EmailMessage): The email message to be sent.

        Raises:
            SMTPAuthError: If an authentication error occurs with the SMTP server.
            SMTPConnectError: If unable to connect to the SMTP server.
            SMTPResponseError: If an unexpected response is received from the SMTP server.
            SMTPRecipientsRefusedError: If the recipient's email address is refused by the SMTP server.
            SMTPGenericError: For any other errors that may occur.
        """
        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
        except smtplib.SMTPAuthenticationError as auth_err:
            raise SMTPAuthError("SMTP authentication error occurred. Please check your SMTP username and password (Learn more at https://support.google.com/mail/?p=BadCredentials).") from auth_err
        except (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected) as server_err:
            raise SMTPConnectError("Unable to connect to the SMTP server. Please check your SMTP server settings.") from server_err
        except smtplib.SMTPResponseException as exc_err:
            raise SMTPResponseError("Unexpected response from the SMTP server. Please check your SMTP server settings.") from exc_err
        except smtplib.SMTPRecipientsRefused as recipient_err:
            raise SMTPRecipientsRefusedError(f"Recipient refused: {self.recipient}. Please check the recipient's email address.") from recipient_err
        except (smtplib.SMTPException, OSError) as gen_error:
            raise SMTPGenericError("An error occurred while trying to send the email.") from gen_error

    def alert_format(self, device_name, resource_name, threshold):
        """Formatting the email layout for individual monitor component."""
        subject = self.config.alert_subject_template.format(device_name=device_name, resource_name=resource_name)
        body = self.config.alert_body_template.format(device_name=device_name, resource_name=resource_name, threshold=threshold)
        self.send_alert(subject, body)

    def send_test_email(self):
        """Check to see if the email is working."""
        try:
            subject = "Test Email from System Health Monitor"
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
        except socket.error as err:
            logging.error("Network connection unavailable. %s", err)
            return False

    def format_wait_time(self, wait_time):
        """Formatting the waiting timeframe."""
        if wait_time < 60:
            return wait_time, 'seconds'
        elif wait_time < 3600:
            return wait_time / 60, 'minutes'
        else:
            return wait_time / 3600, 'hours'
        
    def enforce_max_wait_time(self, wait_time):
        """Enforces a maximum wait time of 12 hours."""
        if wait_time > 43200:
            logging.warning("Wait time exceeded limit of 12 hours, setting to default 1 hours.")
            return 3600
        return wait_time