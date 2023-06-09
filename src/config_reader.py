from typing import Optional, Union, Type
import configparser

class ConfigReader:
    """
    A class used to read the configuration file and provide configuration values.

    ...

    Attributes
    ----------
    config : configparser.ConfigParser
        The parser object to read the configuration file.
    config_file : str
        The name of the configuration file.

    Methods
    -------
    read_config():
        Reads the configuration file.
    get_value(section, key, fallback=None, data_type=str):
        Returns the configuration value for the given section and key.
    """
    def __init__(self, config_file: str ='./config/config.ini'):
        self.config = configparser.ConfigParser()
        self.config_file = config_file
        self.read_config()

    def read_config(self):
        self.config.read(self.config_file)

    def get_value(self, section: str, key: str, fallback: Optional[Union[str, int, bool]] = None, data_type: Type[Union[str, int, bool]] = str) -> Union[str, int, bool]:
        try:
            if data_type == int:
                return self.config.getint(section, key, fallback=fallback)
            # # For now I am leaving this here for future features
            # elif data_type == bool:
            #     return self.config.getboolean(section, key, fallback=fallback)
            else:
                return self.config.get(section, key, fallback=fallback)
        except (configparser.NoSectionError, configparser.NoOptionError) as err:
            raise KeyError(f"Unable to fetch '{key}' from section '{section}'.") from err
        except ValueError as err:
            raise ValueError(f"Configuration cannot be empty or incorrect value has been set: [{err}],"
                             " Check the config file for incorrect usage.") from err

class ConfigValidator:
    """
    A class used to validate the configuration file.

    ...

    Attributes
    ----------
    config : configparser.ConfigParser
        The parser object to validate the configuration file.

    Methods
    -------
    validate_config():
        Validates the configuration file to ensure all necessary sections and options are present.
    """
    def __init__(self, config):
        self.config = config

    def validate_config(self):
        """List of sections and option that are needed be present in the config.ini"""
        necessary_options = [
            ("general", ["disks", "disk_threshold", "cpu_threshold", "ram_threshold", "gpu_threshold",
                        "gpu_memory_threshold", "gpu_temp_threshold"]),
            ("time", ["check_frequency", "email_retry_delay", "alert_cooldown_time"]),
            ("email", ["smtp_server", "smtp_port", "smtp_username", "smtp_password", "recipient", 
                       "alert_subject_template", "alert_body_template"])
        ]
        for section, options in necessary_options:
            if not self.config.has_section(section):
                raise ValueError(f"Section '{section}' is missing in configuration.")
            for option in options:
                if not self.config.has_option(section, option):
                    raise ValueError(f"Option '{option}' is missing in section '{section}' in configuration.")

# pylint: disable=all