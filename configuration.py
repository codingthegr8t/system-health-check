import configparser
import logging

class Configuration:
    def __init__(self, config_file='config.ini'):
        self.config = configparser.ConfigParser()
        self.config_file = config_file
        try:
            self.read_config()
        except (OSError, ValueError) as err:
            logging.error("Error reading or parsing configuration file: %s", err)
            raise OSError(f"Cannot open configuration file: {config_file}") from err

    def __getitem__(self, key):
        return self.__dict__[key]

    @property
    def log_level(self):
        return self.config.get('general', 'log_level', fallback='INFO')

    def validate_config(self):
        """
        Validates the configuration file to ensure all necessary sections and options are present.
        
        For each necessary section-option pair, checks if the section and the option both exist 
        in the configuration. If a necessary section or option is missing, raises a ValueError.

        Raises:
            ValueError: If a necessary section or option is missing in the configuration.

        """

        necessary_options = [
            ("general", ["disks", "disk_threshold", "cpu_threshold", "ram_threshold", "gpu_threshold",
                        "gpu_memory_threshold", "gpu_temp_threshold"]),
            ("time", ["check_frequency", "wait_time_to_resend_email"]),
            ("email", ["smtp_server", "smtp_port", "smtp_username", "smtp_password", "recipient"])
        ]
        for section, options in necessary_options:
            if not self.config.has_section(section):
                raise ValueError(f"Section '{section}' is missing in configuration.")
            for option in options:
                if not self.config.has_option(section, option):
                    raise ValueError(f"Option '{option}' is missing in section '{section}' in configuration.")

    def read_config(self):
        self.config.read(self.config_file)
        self.validate_config()

        try:
            self.disks = self.config.get('general', 'disks').split(', ')
            self.disk_threshold = self.config.getint('general', 'disk_threshold')
            self.cpu_threshold = self.config.getint('general', 'cpu_threshold')
            self.ram_threshold = self.config.getint('general', 'ram_threshold')
            self.gpu_threshold = self.config.getint('general', 'gpu_threshold')
            self.gpu_memory_threshold = self.config.getint('general', 'gpu_memory_threshold')
            self.gpu_temp_threshold = self.config.getint('general', 'gpu_temp_threshold')
        except ValueError as err:
            raise ValueError(f"Configuration cannot be empty or the incorrect value has been set [ {err} ] Check the config file for incorrect usage.") from err

        try:
            self.check_frequency = self.config.getint('time', 'check_frequency')
            self.wait_time_to_resend_email = self.config.getint('time', 'wait_time_to_resend_email')
        except ValueError as err:
            raise ValueError(f"Configuration cannot be empty or the incorrect value has been set [ {err} ] Check the config file for incorrect usage.") from err

        try:
            self.smtp_server = self.config.get('email', 'smtp_server')
            self.smtp_port = self.config.getint('email', 'smtp_port')
            self.smtp_username = self.config.get('email', 'smtp_username')
            self.smtp_password = self.config.get('email', 'smtp_password')
            self.recipient = self.config.get('email', 'recipient')
            self.alert_subject_template = self.config.get('email', 'alert_subject_template', fallback='[Alert] {device_name} {resource_name} threshold exceeded')
            self.alert_body_template = self.config.get('email', 'alert_body_template', fallback='Device: {device_name}, {resource_name}: usage is more than {threshold}%.')
        except ValueError as err:
            raise ValueError(f"Configuration cannot be empty or the incorrect value has been set [ {err} ] Check the config file for incorrect usage.") from err
