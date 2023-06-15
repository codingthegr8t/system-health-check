# System health-check
System Health Monitor is a Python script designed to monitor the health of system resources and send alerts via e-mail when usage thresholds are exceeded. 
The application is flexible and user-configurable, allowing you to tailor monitoring to your specific needs.

## Features
1.  Monitor the usage of the following system resources: CPU, RAM, Disk and GPU (gpu monitor is for now only available for nvdia graphic card).
2.  Send email alerts when resource usage exceeds a user-specified threshold.
3.  Dynamically adapt to changes in the configuration file without requiring a restart.
4.  Comprehensive logging of events and errors.

# Getting Started
## Prerequisites
The application requires Python 3.7 or higher.

Before you begin, ensure you have installed all necessary packages by running: `pip3 install -r requirements.txt`

## Configuration
The `src/config/config.ini` file is used to configure the application. This file contains three sections: general, time, and email.
* In the *general* section, you specify the resources to monitor and their respective thresholds.
* In the *time* section, you define the check frequency (in seconds) and the wait time to resend email alerts (also in seconds).
* The *email* section is used to configure the SMTP server details for sending alert emails.
 >  **Note:** Every system is different edit the config.ini file to your needs.

## Running the Application
To start the system health monitor, run the main.py script:
*  `python main.py`
*  `./main.py`
> The application will begin monitoring your system resources based on your config.ini settings and log events to logfile.log.

## Recommendations:
The System Health Monitor script can run continuously, providing consistent system health monitoring. 
However, the specific method of implementation will depend on your needs and the nature of your system.

Here are two common scenarios and how to handle them:
1.  Continuous System (Server, etc.): If you are running a system that is intended to operate indefinitely without shutdowns (like a server), you would need to run in the background, you can use nohup, screen, or tmux (Unix-based system).
example with nohup:
* `nohup ./main.py &` 
> *This will start the script in the background, and it will keep running even if you log out.*
2.  Start at System Boot: If you want the script to start every time your system starts up, you will need to use system services or task schedulers. This ensures that the script starts monitoring system resources as soon as the system boots up, even if no user is logged in. The method to achieve this varies between operating systems:
+ **Linux**: On Linux systems, **cron jobs** can be used to schedule tasks, but they are not always suitable for tasks that need to run indefinitely after boot. Instead, consider using a service manager like **systemd**. Here's a helpful guide on creating a Linux service with systemd: [systemd](https://medium.com/@benmorel/creating-a-linux-service-with-systemd-611b5c8b91d6).

+ **Windows**: On Windows systems, you can use the Task Scheduler to create a task that runs the Python script at startup. Here's a step-by-step guide: [Windows Task Scheduler](https://www.windowscentral.com/how-create-automated-task-using-task-scheduler-windows-10) to create a task that runs the Python script at startup.

**Please make sure to test the setup thoroughly to ensure that the script starts correctly and functions as expected.**

# Contact

If you have any questions or feedback, feel free to contact us at schuilenburgchris@gmail.com.
