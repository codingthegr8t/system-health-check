#!/usr/bin/env python3
import logging
import time
from configparser import NoSectionError, NoOptionError
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from system_monitor import SystemMonitor
from notifier import Notifier
from config_reader import ConfigReader, ConfigValidator

class ConfigFileHandler(FileSystemEventHandler):
    def __init__(self, config):
        self.config = config
        self.config_modified = False

    def on_closed(self, event):
        if not event.is_directory and event.src_path.endswith('config_test.ini'):
            try:
                self.config.read_config()
                self.config_modified = True
            except ValueError as err:
                logging.error("Error reading config: %s", err)

def setup_logger(config):
    """Settings for the logging"""
    level = getattr(logging, config.get_value('general', 'log_level', fallback='INFO'))
    logging.basicConfig(
        handlers=[
            logging.FileHandler('logfile.log'),
            logging.StreamHandler()
        ],
        format='%(asctime)s - %(levelname)s - %(message)s - %(filename)s - %(lineno)d',
        datefmt='%H:%M:%S %d-%m-%y',
        level=level
    )

def main():
    config_reader = ConfigReader()
    config_validator = ConfigValidator(config_reader.config)

    try:
        config_validator.validate_config()
    except ValueError as err:
        print(f"Config validation failed: {err}")
        return
    
    # Set up the logger
    setup_logger(config_reader)

    handler = ConfigFileHandler(config_reader)
    observer = Observer()
    observer.schedule(handler, path='./config_test.ini', recursive=False)
    logging.getLogger('watchdog').setLevel(logging.WARNING)
    observer.start()

    notifier = Notifier(
        config_reader.get_value('email', 'smtp_server'),
        config_reader.get_value('email', 'smtp_port', data_type=int),
        config_reader.get_value('email', 'smtp_username'),
        config_reader.get_value('email', 'smtp_password'),
        config_reader.get_value('email', 'recipient'),
    )
    # send a test email
    # notifier.send_test_email()

    monitor = SystemMonitor(config_reader, notifier)

    try:
        while True:
            # reload the config at each check
            if handler.config_modified:
                try:
                    config_reader.read_config()
                    setup_logger(config_reader)
                    handler.config_modified = False
                except (ValueError, NoSectionError, NoOptionError) as err:
                    logging.error("Error reloading config: %s", err)

            # set wait time for check up notice
            next_check = config_reader.get_value('time', 'check_frequency', data_type=int)
            _next_check, timeframe = notifier.format_wait_time(next_check)
            # check for multiple disks
            health_checks = {disk: monitor.check_health(disk) for disk in config_reader.get_value('general', 'disks').split(',')}
            if all(health_checks.values()):
                logging.info("System health check passed.")
                logging.info("The next monitoring will be in %.0f %s", _next_check, timeframe)
            else:
                logging.warning("System health check failed")
                logging.info("The next monitoring will be in %.0f %s", _next_check, timeframe)

            time.sleep(config_reader.get_value('time', 'check_frequency', data_type=int))

    except ValueError as err:
        logging.error("Exiting due to configuration error: %s", err)
        observer.stop()
    except KeyboardInterrupt:
        observer.stop()
        logging.info("System monitoring stopped")
    finally:
        observer.join()

if __name__ == "__main__":
    main()

# pylint: disable=all