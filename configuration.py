import configparser
from configparser import NoSectionError, NoOptionError

class CustomNoOptionError(NoOptionError):
    """
    Custom exception class for handling missing options in the configuration file.

    The configparser module is designed to only take two arguments, section and option respectively.
    My optionError will need to include the section and option at the same time and also display a 
    custom error message.
    """
    def __init__(self, message, section, option):
        super().__init__(option, section)
        self.message = message

class Configuration:
    """
    Class for handling system configuration based on an INI file.

    The Configuration class uses the configparser module to read the configuration file
    and exposes the configuration data as class properties. It also provides error handling
    for missing sections or options in the configuration file.

    Attributes
    ----------
    config : ConfigParser object
        The ConfigParser object used for reading the configuration file.
    config_file : str
        The path to the configuration file.
        
    Methods
    -------
    __init__(config_file='config.ini'):
        The constructor for the Configuration class.
    __getitem__(key):
        Getter method to return the attribute of the object.
    read_config():
        Reads the configuration file and sets the configuration properties.
    """
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
        
        config_sections = {
            "general": [
                ("disks", str, 'split', ', '),
                ("disk_threshold", int),
                ("cpu_threshold", int),
                ("ram_threshold", int),
                ("gpu_threshold", int),
                ("gpu_memory_threshold", int),
                ("gpu_temp_threshold", int)
            ],
            "time": [
                ("check_frequency", int),
                ("wait_time_to_resend_email", int)
            ],
            "email": [
                ("smtp_server", str),
                ("smtp_port", int),
                ("smtp_username", str),
                ("smtp_password", str),
                ("recipient", str),
                ("alert_subject_template", str),
                ("alert_body_template", str)
            ]
        }

        for section, options in config_sections.items():
            for option in options:
                try:
                    option_name, option_type = option[0], option[1]
                    option_value = self.config.get(section, option_name)
                    if option_type == str and len(option) == 4:
                        # this option needs to be split
                        option_value = option_value.split(option[3])
                    elif option_type == int:
                        option_value = self.config.getint(section, option_name)
                    setattr(self, option_name, option_value)
                except NoSectionError as err:
                    raise NoSectionError(f"{err}, Check if the '{section}' section exists in the config.ini file or "
                                         "check if the correct .ini (defualt: config.ini) file exist in the current directory") from err
                except NoOptionError as err:
                    raise CustomNoOptionError(f"{err}. Check if the '{option_name}' option exists in the '{section}' section of the config.ini file.", section, option_name) from err
                except ValueError as err:
                    raise ValueError(f"Configuration cannot be empty or the incorrect value has been set [ {err} ]. Check the config file for incorrect usage.") from err
