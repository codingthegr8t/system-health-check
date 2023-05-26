#!/usr/bin/env python3
import logging
import time
from configparser import NoSectionError, NoOptionError
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from system_monitor import SystemMonitor
from notifier import Notifier
from configuration import Configuration

class ConfigFileHandler(FileSystemEventHandler):
    def __init__(self, config):
        self.config = config
        self.config_modified = False

    def on_closed(self, event):
        if not event.is_directory and event.src_path.endswith('config.ini'):
            try:
                self.config.read_config()
                self.config_modified = True
            except ValueError as err:
                logging.error("Error reading config: %s", err)

def setup_logger(config):
    """Settings for the logging"""
    level = getattr(logging, config.log_level, 'INFO')
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
    try:
        config = Configuration()
    except IOError as err:
        logging.error("Error in configuration: %s", err)
        return
    
    # Set up the logger
    setup_logger(config)

    handler = ConfigFileHandler(config)
    observer = Observer()
    observer.schedule(handler, path='./config.ini', recursive=False)
    logging.getLogger('watchdog').setLevel(logging.WARNING)
    observer.start()

    notifier = Notifier(
        config['smtp_server'],
        config['smtp_port'],
        config['smtp_username'],
        config['smtp_password'],
        config['recipient'],
    )
    # send a test email
    notifier.send_test_email()

    monitor = SystemMonitor(config, notifier)

    try:
        while True:
            # reload the config at each check
            if handler.config_modified:
                try:
                    config.read_config()
                    setup_logger(config)
                    handler.config_modified = False
                except (ValueError, NoSectionError, NoOptionError) as err:
                    logging.error("Error reloading config: %s", err)

            # set wait time for check up notice
            next_check = config.check_frequency
            _next_check, timeframe = notifier.format_wait_time(next_check)

            health_checks = {disk: monitor.check_health(disk) for disk in monitor.config['disks']}
            if all(health_checks.values()):
                logging.info("System health check passed.")
                logging.info("The next monitoring will be in %.0f %s", _next_check, timeframe)
            else:
                logging.warning("System health check failed")
                logging.info("The next monitoring will be in %.0f %s", _next_check, timeframe)

            time.sleep(config.check_frequency)

    except ValueError:
        logging.error("Exiting due to configuration error.")
        observer.stop()
    except KeyboardInterrupt:
        observer.stop()
        logging.info("System monitoring stopped")
    finally:
        observer.join()

if __name__ == "__main__":
    main()
