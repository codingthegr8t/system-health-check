#!/usr/bin/env python3
import logging
import time
from system_monitor import SystemMonitor
from notifier import Notifier
from configuration import Configuration
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class ConfigFileHandler(FileSystemEventHandler):
    def __init__(self, config):
        self.config = config

    def on_closed(self, event):
        if not event.is_directory and event.src_path.endswith('config.ini'):
            self.config.read_config()

def setup_logger(config):
    level = getattr(logging, config.log_level, 'INFO')
    logging.basicConfig(
        handlers=[
            logging.FileHandler('logfile.log'),
            logging.StreamHandler()
        ],
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S %d-%m-%y',
        level=level
    )

def main():
    config = Configuration()

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
    monitor = SystemMonitor(config, notifier)

    try:
        while True:
            try:
                # reload the config at each check
                config.read_config()

                # update the logger settings
                setup_logger(config)

                health_checks = {disk: monitor.check_health(disk) for disk in monitor.config['disks']}
                if all(health_checks.values()):
                    logging.info("System health check passed.")
                else:
                    logging.warning("System health check failed")
            except Exception as error:
                logging.exception(f"Exception during health check: {error}")
            time.sleep(config.check_frequency)
    except KeyboardInterrupt:
        observer.stop()
        logging.info("System monitoring stopped")
    except Exception as error:
        observer.stop()
        logging.exception(f"Unhandled exception occurred: {error}")

    observer.join()

if __name__ == "__main__":
    main()