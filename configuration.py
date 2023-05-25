import configparser
from configparser import NoSectionError, NoOptionError

class Configuration:
    def __init__(self, config_file='config.ini'):
        self.config = configparser.ConfigParser()
        self.config_file = config_file
        self.read_config()
        
    def __getitem__(self, key):
        return getattr(self, key, None)

    @property
    def log_level(self):
        return self.config.get('general', 'log_level', fallback='INFO')

    def read_config(self):
        self.config.read(self.config_file)

        try:
            self.disks = self.config.get('general', 'disks').split(', ')
            self.disk_threshold = self.config.getint('general', 'disk_threshold')
            self.cpu_threshold = self.config.getint('general', 'cpu_threshold')
            self.ram_threshold = self.config.getint('general', 'ram_threshold')
            self.gpu_threshold = self.config.getint('general', 'gpu_threshold')
            self.gpu_memory_threshold = self.config.getint('general', 'gpu_memory_threshold')
            self.gpu_temp_threshold = self.config.getint('general', 'gpu_temp_threshold')
        except NoSectionError as err:
            raise NoSectionError(f"{err}, Check if the 'general' section exists in the config.ini file or "
                                    "check if the config.ini file exist in the current directory when running this script") from err
        except NoOptionError as err:
            raise NoOptionError(f"{err}, Check if the corresponding option exists in the 'general' section of the config.ini file.", err.option) from err
        except ValueError as err:
            raise ValueError(f"Configuration cannot be empty or the incorrect value has been set [ {err} ] Check the config file for incorrect usage.") from err

        try:
            self.check_frequency = self.config.getint('time', 'check_frequency')
            self.wait_time_to_resend_email = self.config.getint('time', 'wait_time_to_resend_email')
        except NoSectionError as err:
            raise NoSectionError(f"{err}, Check if the 'time' section exists in the config.ini file") from err
        except NoOptionError as err:
            raise NoOptionError(f"{err}, Check if the corresponding option exists in the 'time' section of the config.ini file.", err.option) from err
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
        except NoSectionError as err:
            raise NoSectionError(f"{err}, Check if the 'email' section exists in the config.ini file") from err
        except NoOptionError as err:
            raise NoOptionError(f"{err}, Check if the corresponding option exists in the 'email' section of the config.ini file.", err.option) from err
        except ValueError as err:
            raise ValueError(f"Configuration cannot be empty or the incorrect value has been set [ {err} ] Check the config file for incorrect usage.") from err
