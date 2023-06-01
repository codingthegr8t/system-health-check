from typing import Tuple, Optional
import shutil
import logging
import socket
import psutil
import pynvml
import cpuinfo
import os
from abc import ABC, abstractmethod
from pynvml import NVMLError
from notifier import Notifier
from config_reader import ConfigReader

BYTES_TO_GB = 2**30

class ResourceMonitor(ABC):
    """Abstract base class for all resource monitors."""
    def __init__(self, notifier: Notifier):
        self.notifier = notifier

    def alert_and_log(self, device_name: str, resource_name: str, threshold: int, message: str):
        self.notifier.alert_format(device_name, resource_name, threshold)
        logging.warning(message)

    @abstractmethod
    def get_usage(self):
        """Retrieve the resource usage statistics."""
        pass

    @abstractmethod
    def check_health(self, device_name: str, threshold: int) -> bool:
        """Check the health of the resource."""
        pass

class DiskMonitor(ResourceMonitor):
    def __init__(self, notifier):
        super().__init__(notifier)

    def get_usage(self, disk: str) -> Tuple[float, float, float]:
        """Retrieve disk usage statistics for a given disk."""
        if not os.path.exists(disk) or not os.path.isdir(disk):
            logging.error("Disk path %s not found or is not a directory.", disk)
            raise FileNotFoundError("Disk path not found or is not a directory.")

        try:
            du = shutil.disk_usage(disk)
            total = du.total / BYTES_TO_GB
            free = du.free / BYTES_TO_GB
            percent_free = free / total * 100
        except PermissionError:
            logging.error("Permission denied to access %s.", disk)
            raise
        except OSError as os_error:
            logging.error("OS error when retrieving disk usage: %s", os_error)
            raise
        return total, free, percent_free

    def check_health(self, device_name: str, disk: str, threshold: int) -> bool:
        """Check the Disk health."""
        total, free, percent_free = self.get_usage(disk)
        if percent_free <= threshold:
            message = "Disk %s - Total space: %.1f GB, Free space: %.1f GB, Percentage free: %.1f%%" % (disk, total, free, percent_free)
            self.alert_and_log(device_name, "Disks", threshold, message)
            return False
        return True

class CpuMonitor(ResourceMonitor):
    def __init__(self, notifier):
        super().__init__(notifier)

    def get_usage(self) -> float:
        """Retrieve CPU usage statistics."""
        try:
            usage = psutil.cpu_percent(1)
        except psutil.Error as err:
            logging.error("Failed to get CPU usage: %s", err)
            raise RuntimeError(f"Unexpected error when retrieving CPU usage: {err}") from err
        return usage

    def check_health(self, device_name: str, threshold: int) -> bool:
        """Check the CPU health."""
        cpu_usage = self.get_usage()
        if cpu_usage >= threshold:
            message = "%s usage: %s%%" % (cpuinfo.get_cpu_info()['brand_raw'], cpu_usage)
            self.alert_and_log(device_name, "CPU", threshold, message)
            return False
        return True

class RamMonitor(ResourceMonitor):
    def __init__(self, notifier):
        super().__init__(notifier)

    def get_usage(self) -> Tuple[float, float]:
        """Retrieve RAM usage statistics."""
        try:
            ram = psutil.virtual_memory()
            return ram.total / BYTES_TO_GB, ram.percent
        except psutil.Error as err:
            logging.error("Failed to get RAM usage: %s", err)
            raise RuntimeError(f"Unexpected error when retrieving RAM usage: {err}") from err

    def check_health(self, device_name: str, threshold: int) -> bool:
        """Check the RAM health."""
        total_ram, percent_ram_used = self.get_usage()
        if percent_ram_used >= threshold:
            message = "Total System RAM: %.0f GB, RAM usage: %s%%" % (total_ram, percent_ram_used)
            self.alert_and_log(device_name, "RAM", threshold, message)
            return False
        return True

class GpuMonitor(ResourceMonitor):
    def __init__(self, notifier):
        super().__init__(notifier)

    def get_usage(self) -> Optional[Tuple[int, float, float, int, str]]:
        """Retrieve GPU usage statistics."""
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
            total_memory_in_gb = total_memory / BYTES_TO_GB
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

    def check_health(self, device_name: str, gpu_threshold: int, gpu_memory_threshold: int, gpu_temp_threshold: int) -> bool:
        """Check the GPU's health."""
        gpu_utilization, gpu_total_memory, memory_utilization, gpu_temperature, gpu_name = self.get_usage()
        alert_info = []

        if gpu_utilization >= gpu_threshold:
            alert_info.append({"resource_name": "GPU Usage", "threshold": gpu_threshold})

        if memory_utilization >= gpu_memory_threshold:
            alert_info.append({"resource_name": "GPU Memory Usage", "threshold": gpu_memory_threshold})

        if gpu_temperature >= gpu_temp_threshold:
            alert_info.append({"resource_name": "GPU Temperature", "threshold": gpu_temp_threshold})

        if alert_info:
            for info in alert_info:
                message = "%s - GPU Usage: %s%%, GPU Memory Usage: %.1f%%, GPU Total Memory: %.0f, GPU Temperature: %s\u2103" % (
                            gpu_name, gpu_utilization, memory_utilization, gpu_total_memory, gpu_temperature)
                self.alert_and_log(device_name, info["resource_name"], info["threshold"], message)
            return False

        return True

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
    def __init__(self, config: ConfigReader, notifier: Notifier):
        self.config = config
        self.disk_monitor = DiskMonitor(notifier)
        self.cpu_monitor = CpuMonitor(notifier)
        self.ram_monitor = RamMonitor(notifier)
        self.gpu_monitor = GpuMonitor(notifier) if self.check_gpu_presence() else None
        self.disks = config.get_value('general', 'disks').split(',')

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

    def check_health(self, disk) -> bool:
        """Check the health of the system."""
        device_name = socket.gethostname()
        is_disk_healthy = self.disk_monitor.check_health(device_name, disk, self.config.get_value('general', 'disk_threshold', data_type=int))
        is_cpu_healthy = self.cpu_monitor.check_health(device_name, self.config.get_value('general', 'cpu_threshold', data_type=int))
        is_ram_healthy = self.ram_monitor.check_health(device_name, self.config.get_value('general', 'ram_threshold', data_type=int))
        if self.gpu_monitor:
            is_gpu_healthy = self.gpu_monitor.check_health(device_name, 
                                                        self.config.get_value('general', 'gpu_threshold', data_type=int),
                                                        self.config.get_value('general', 'gpu_memory_threshold', data_type=int),
                                                        self.config.get_value('general', 'gpu_temp_threshold', data_type=int))
        else:
            is_gpu_healthy = True

        return is_disk_healthy and is_cpu_healthy and is_ram_healthy and is_gpu_healthy

# pylint: disable=all
