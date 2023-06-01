from typing import Tuple, Optional
import shutil
import logging
import socket
import psutil
import pynvml
import cpuinfo
import os
from pynvml import NVMLError
from notifier import Notifier
from config_reader import ConfigReader

class SystemMonitor:
    """
    The SystemMonitor class is a utility for monitoring system resources.

    This class provides methods to monitor various system resources like:
    Disk, CPU, RAM, and NVDIA GPU if present.
    It uses various external modules to gather the required data. 
    Any exception or error while fetching data is logged and raised further.

    It also provides methods to check the health of 
    these resources based on certain configurable thresholds.
    In case of any resource crossing its threshold limit, 
    it sends an alert using the provided notifier.

    Attributes:
    config : A Configuration object to hold all threshold values.
    notifier : A Notifier object to send alerts when resource usage exceeds the threshold.
    gpu_present : A boolean indicating if a NVDIA GPU is present on the system.
    """
    BYTES_TO_GB = 2**30

    def __init__(self, config: ConfigReader, notifier: Notifier):
        self.config = config
        self.notifier = notifier
        self.gpu_present: bool = self.check_gpu_presence()
        self.load_thresholds()

    def load_thresholds(self):
        """Load all thresholds from configuration."""
        self.disk_threshold = self.config.get_value('general', 'disk_threshold', data_type=int)
        self.cpu_threshold = self.config.get_value('general', 'cpu_threshold', data_type=int)
        self.ram_threshold = self.config.get_value('general', 'ram_threshold', data_type=int)
        self.gpu_threshold = self.config.get_value('general', 'gpu_threshold', data_type=int)
        self.gpu_memory_threshold = self.config.get_value('general', 'gpu_memory_threshold', data_type=int)
        self.gpu_temp_threshold = self.config.get_value('general', 'gpu_temp_threshold', data_type=int)

    def get_disk_usage(self, disk: str) -> Tuple[float, float, float]:
        """Retrieve disk usage statistics for a given disk."""
        if not os.path.exists(disk) or not os.path.isdir(disk):
            logging.error("Disk path %s not found or is not a directory.", disk)
            raise FileNotFoundError("Disk path not found or is not a directory.")

        try:
            du = shutil.disk_usage(disk)
            total = du.total / self.BYTES_TO_GB
            free = du.free / self.BYTES_TO_GB
            percent_free = free / total * 100
        except PermissionError:
            logging.error("Permission denied to access %s.", disk)
            raise
        except OSError as os_error:
            logging.error("OS error when retrieving disk usage: %s", os_error)
            raise

        return total, free, percent_free

    def get_cpu_usage(self) -> float:
        """Retrieve CPU usage statistics."""
        try:
            usage = psutil.cpu_percent(1)
        except psutil.Error as err:
            logging.error("Failed to get CPU usage: %s", err)
            raise RuntimeError(f"Unexpected error when retrieving CPU usage: {err}") from err
        return usage

    def get_ram_usage(self) -> Tuple[float, float]:
        """Retrieve RAM usage statistics."""
        try:
            ram = psutil.virtual_memory()
            return ram.total / self.BYTES_TO_GB, ram.percent
        except psutil.Error as err:
            logging.error("Failed to get RAM usage: %s", err)
            raise RuntimeError(f"Unexpected error when retrieving RAM usage: {err}") from err

    def check_gpu_presence(self):
        """Check if a GPU is present on the system."""
        try:
            pynvml.nvmlInit()
            device_count = pynvml.nvmlDeviceGetCount()
            # Check if at least one of the GPUs is from NVIDIA
            if any(pynvml.nvmlDeviceGetName(pynvml.nvmlDeviceGetHandleByIndex(i)).lower().startswith("nvidia") 
                for i in range(device_count)):
                return True
            pynvml.nvmlShutdown()
        except pynvml.NVMLError as nvml_err:
            if nvml_err.value in (pynvml.NVML_ERROR_LIBRARY_NOT_FOUND, pynvml.NVML_ERROR_DRIVER_NOT_LOADED):
                logging.warning("NVML Shared Library Not Found or NVIDIA GPU Driver Not Loaded. GPU will not be monitored.")
                return False
        return False

    def get_gpu_usage(self) -> Optional[Tuple[int, float, float, int, str]]:
        """Retrieve GPU usage statistics."""
        if not self.gpu_present:
            logging.error("GPU not present or not compatible.")
            return None

        try:
            pynvml.nvmlInit()
            # Assuming one GPU. If you have more, you might need to loop over the device ids.
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        except NVMLError as nvml_err:
            logging.error("Failed to initialize GPU or get handle")
            raise nvml_err

        try:
            # GPU utilization (percent)
            gpu_utilization = pynvml.nvmlDeviceGetUtilizationRates(handle).gpu
        except NVMLError as nvml_err:
            if nvml_err.value == pynvml.NVML_ERROR_UNINITIALIZED:
                logging.error("Failed to get GPU utilization: %s", nvml_err)
                raise nvml_err

        try:
            # Total memory (GB)
            total_memory = pynvml.nvmlDeviceGetMemoryInfo(handle).total
            total_memory_in_gb = total_memory / self.BYTES_TO_GB
            # Memory utilization (bytes)
            used_memory = pynvml.nvmlDeviceGetMemoryInfo(handle).used
            memory_utilization = (used_memory / total_memory) * 100  # percentage
        except NVMLError as nvml_err:
            logging.error("Failed to get GPU memory info: %s", nvml_err)
            raise nvml_err

        try:
            # Temperature (Celsius)
            gpu_temperature = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
        except NVMLError as nvml_err:
            logging.error("Failed to get GPU temperature: %s", nvml_err)
            raise nvml_err

        try:
            # Get GPU name
            gpu_name = pynvml.nvmlDeviceGetName(handle)
        except NVMLError as nvml_err:
            logging.error("Failed to get GPU brand name: %s", nvml_err)
            raise nvml_err

        finally:
            pynvml.nvmlShutdown()

        return gpu_utilization, total_memory_in_gb, memory_utilization, gpu_temperature, gpu_name

    def check_disk_health(self, device_name: str, disk: str) -> bool:
        """Check the Disk health."""
        total, free, percent_free = self.get_disk_usage(disk)
        if percent_free <= self.disk_threshold:
            self.notifier.alert_format(device_name, "Disks", self.disk_threshold)
            logging.warning("Disk %s - Total space: %.1f GB, Free space: %.1f GB, Percentage free: %.1f%%", disk, total, free, percent_free)
            return False
        return True

    def check_cpu_health(self, device_name: str) -> bool:
        """Check the CPU health."""
        cpu_usage = self.get_cpu_usage()
        if cpu_usage >= self.cpu_threshold:
            self.notifier.alert_format(device_name, "CPU", self.cpu_threshold)
            logging.warning("%s usage: %s%%", cpuinfo.get_cpu_info()['brand_raw'], cpu_usage)
            return False
        return True

    def check_ram_health(self, device_name: str) -> bool:
        """Check the RAM health."""
        total_ram, percent_ram_used = self.get_ram_usage()
        if percent_ram_used >= self.ram_threshold:
            self.notifier.alert_format(device_name, "RAM", self.ram_threshold)
            logging.warning("Total System RAM: %.0f GB, RAM usage: %s%%", total_ram, percent_ram_used)
            return False
        return True

    def check_gpu_health(self, device_name: str) -> bool:
        """Check the GPU's health."""
        gpu_utilization, gpu_total_memory, memory_utilization, gpu_temperature, gpu_name = self.get_gpu_usage()
        alert_info = []

        if gpu_utilization >= self.gpu_threshold:
            alert_info.append({"resource_name": "GPU Usage", "threshold": self.gpu_threshold})

        if memory_utilization >= self.gpu_memory_threshold:
            alert_info.append({"resource_name": "GPU Memory Usage", "threshold": self.gpu_memory_threshold})

        if gpu_temperature >= self.gpu_temp_threshold:
            alert_info.append({"resource_name": "GPU Temperature", "threshold": self.gpu_temp_threshold})

        if alert_info:
            for info in alert_info:
                self.notifier.alert_format(device_name, info["resource_name"], info["threshold"])
            logging.warning("%s - GPU Usage: %s%%, GPU Memory Usage: %.1f%%, GPU Total Memory: %.0f, "
                            "GPU Temperature: %s\u2103", gpu_name, gpu_utilization, memory_utilization, gpu_total_memory, gpu_temperature)
            return False

        return True

    def check_health(self, disk: str) -> bool:
        """Check the health of the system."""
        device_name = socket.gethostname()

        # Check each resource's health separately
        is_disk_healthy = self.check_disk_health(device_name, disk)
        is_cpu_healthy = self.check_cpu_health(device_name)
        is_ram_healthy = self.check_ram_health(device_name)

        # Only check GPU health if a compatible GPU is present
        is_gpu_healthy = self.check_gpu_health(device_name) if self.gpu_present else True

        return is_disk_healthy and is_cpu_healthy and is_ram_healthy and is_gpu_healthy

# pylint: disable=all
