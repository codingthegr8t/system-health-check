#!/usr/bin/env python3
import logging
import time
import os
from configparser import NoSectionError, NoOptionError
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from system_monitors import system_monitor
from notification_alerts import email_notifier
from config_reader import ConfigReader, ConfigValidator
from time_manager import TimeManager

class ConfigFileHandler(FileSystemEventHandler):
    def __init__(self, config):
        self.config = config
        self.config_modified = False

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith('./config/config.ini'):
            try:
                self.config.read_config()
                self.config_modified = True
            except ValueError as err:
                logging.error("Error reading config: %s", err)

def setup_logger(config):
    """Settings for the logging"""
    log_level = config.get_value('general', 'log_level', fallback='INFO').upper()
    level = getattr(logging, log_level, None)
    log_dir = './log'
    log_file = os.path.join(log_dir, 'logfile.log')

    # Check if the directory exists, if not, create it
    if not os.path.isdir(log_dir):
        os.makedirs(log_dir)

    try:
        logging.basicConfig(
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ],
        format='%(asctime)s - %(levelname)s - %(message)s - %(filename)s - %(lineno)d',
        datefmt='%H:%M:%S %d-%m-%y',
        level=level
    )
    except FileNotFoundError as file_err:
        print(f"Error while setting up logging: {file_err}")

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
    observer.schedule(handler, path='./config/config.ini', recursive=False)
    logging.getLogger('watchdog').setLevel(logging.WARNING)
    observer.start()

    notifier = email_notifier.Notifier(
        config_reader.get_value('email', 'smtp_server'),
        config_reader.get_value('email', 'smtp_port', data_type=int),
        config_reader.get_value('email', 'smtp_username'),
        config_reader.get_value('email', 'smtp_password'),
        config_reader.get_value('email', 'recipient'),
    )
    monitor = system_monitor.SystemMonitor(config_reader, notifier)

    # send a test email
    notifier.send_test_email()

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
            _next_check, timeframe = TimeManager.format_wait_time(next_check)

            # check health of multiple disks
            health_checks = {disk: monitor.check_health(disk) for disk in config_reader.get_value('general', 'disks').split(', ')}
            if all(health_checks.values()):
                logging.info("✅ System health check passed")
                logging.info("The next monitoring will be in %.0f %s", _next_check, timeframe)
            else:
                logging.warning("❌ System health check failed")
                logging.info("The next monitoring will be in %.0f %s", _next_check, timeframe)

            time.sleep(next_check)

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
