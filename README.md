# System health-check
System Health Monitor is a Python application designed to monitor the health of system resources and send alerts when usage thresholds are exceeded. 
The application is flexible and user-configurable, allowing you to tailor monitoring to your specific needs.

## Features
1.  Monitor the usage of the following system resources: CPU, RAM, Disk and GPU (gpu monitor is only available for nvdia cards).
2.  Send email alerts when resource usage exceeds a user-specified threshold.
3.  Dynamically adapt to changes in the configuration file without requiring a restart.
4.  Comprehensive logging of events and errors.

# Getting Started
## Prerequisites
The application requires Python 3.7 or higher.

Before you begin, ensure you have installed all necessary packages by running: `pip install -r requirements.txt`

## Configuration
The `config.ini` file is used to configure the application. This file contains three sections: general, time, and email.
In the *general* section, you specify the resources to monitor and their respective thresholds.
In the *time* section, you define the check frequency (in seconds) and the wait time to resend email alerts (also in seconds).
The *email* section is used to configure the SMTP server details for sending alert emails.

## Running the Application
To start the system health monitor, run the main.py script:
  `python main.py`
or 
  `./main.py`
The application will begin monitoring your system resources based on your config.ini settings and log events to logfile.log. 
If you want to use schedule tasks this option is possible but I would not recommend using cronjob.
The script already has build-in runtime so cronjob would be not needed. 
  
  
