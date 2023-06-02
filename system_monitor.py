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

BYTES_TO_GB = 2**30

def handle_exceptions(*exception_types):
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except exception_types as e:
                logging.error(f"Failed to execute {func.__qualname__}: {e}")
                raise
        return wrapper
    return decorator

def manage_gpu_resource(func):
    def wrapper(*args, **kwargs):
        try:
            pynvml.nvmlInit()
            result = func(*args, **kwargs)
        except pynvml.NVMLError as e:
            logging.error("Failed to initialize GPU or get handle")
            raise e
        finally:
            pynvml.nvmlShutdown()
        return result
    return wrapper

class ResourceMonitor(ABC):
    """Abstract base class for all resource monitors."""
    @abstractmethod
    def get_usage(self):
        """Retrieve the resource usage statistics."""
        pass

    @abstractmethod
    def check_health(self, device_name: str, threshold: int) -> bool:
        """Check the health of the resource."""
        pass

class DiskMonitor(ResourceMonitor):
    """
    DiskMonitor is a concrete implementation of the ResourceMonitor abstract base class.
    It monitors the disk usage and health of the system.
    """
    def __init__(self, notifier):
        self.notifier = notifier

    def get_usage(self, disk: str) -> Tuple[float, float, float]:
        """Retrieve disk usage statistics for a given disk."""
        if not os.path.exists(disk) or not os.path.isdir(disk):
            logging.error("Disk path %s not found or is not a directory.", disk)
            raise FileNotFoundError("Disk path not found or is not a directory.")

        try:
            du = shutil.disk_usage(disk)
            total, free = du.total / BYTES_TO_GB, du.free / BYTES_TO_GB
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
            self.notifier.alert_format(device_name, "Disks", threshold)
            logging.warning("Disk %s - Total space: %.1f GB, Free space: %.1f GB, Percentage free: %.1f%%", disk, total, free, percent_free)
            return False
        return True

class CpuMonitor(ResourceMonitor):
    """
    CpuMonitor is a concrete implementation of the ResourceMonitor abstract base class.
    It monitors the CPU usage and health of the system.
    """
    def __init__(self, notifier):
        self.notifier = notifier

    @handle_exceptions(psutil.Error)
    def get_usage(self) -> float:
        """Retrieve CPU usage statistics."""
        return psutil.cpu_percent(1)
    
    def check_health(self, device_name: str, threshold: int) -> bool:
        """Check the CPU health."""
        cpu_usage = self.get_usage()
        if cpu_usage >= threshold:
            self.notifier.alert_format(device_name, "CPU", threshold)
            logging.warning("%s usage: %s%%", cpuinfo.get_cpu_info()['brand_raw'], cpu_usage)
            return False
        return True

class RamMonitor(ResourceMonitor):
    """
    RamMonitor is a concrete implementation of the ResourceMonitor abstract base class.
    It monitors the RAM usage and health of the system.
    """
    def __init__(self, notifier):
        self.notifier = notifier

    @handle_exceptions(psutil.Error)
    def get_usage(self) -> Tuple[float, float]:
        """Retrieve RAM usage statistics."""
        ram = psutil.virtual_memory()
        return ram.total / BYTES_TO_GB, ram.percent
    
    def check_health(self, device_name: str, threshold: int) -> bool:
        """Check the RAM health."""
        total_ram, percent_ram_used = self.get_usage()
        if percent_ram_used >= threshold:
            self.notifier.alert_format(device_name, "RAM", threshold)
            logging.warning("Total System RAM: %.0f GB, RAM usage: %s%%", total_ram, percent_ram_used)
            return False
        return True

class GpuMonitor(ResourceMonitor):
    """
    GpuMonitor is a concrete implementation of the ResourceMonitor abstract base class.
    It monitors the GPU usage, memory utilization, and temperature of the system.
    """
    def __init__(self, notifier):
        self.notifier = notifier

    @manage_gpu_resource
    @handle_exceptions(NVMLError) 
    def get_usage(self) -> Optional[Tuple[int, float, float, int, str]]:
        """Retrieve GPU usage statistics."""
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        # GPU utilization (percent)
        gpu_utilization = pynvml.nvmlDeviceGetUtilizationRates(handle).gpu
        total_memory = pynvml.nvmlDeviceGetMemoryInfo(handle).total
        # Memory utilization (bytes)
        used_memory = pynvml.nvmlDeviceGetMemoryInfo(handle).used
        memory_utilization = (used_memory / total_memory) * 100
        # Temperature (Celsius)
        gpu_temperature = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
        # Get GPU name
        gpu_name = pynvml.nvmlDeviceGetName(handle)
        return gpu_utilization, total_memory / BYTES_TO_GB, memory_utilization, gpu_temperature, gpu_name

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
                self.notifier.alert_format(device_name, info["resource_name"], info["threshold"])
                logging.warning("%s - GPU Utilization: %s%%, GPU Memory Utilization: %.1f%%, GPU Total Memory: %.0f, "
                            "GPU Temperature: %s\u2103", gpu_name, gpu_utilization, memory_utilization, gpu_total_memory, gpu_temperature)
            return False
        return True

class SystemMonitor:
    """
    The SystemMonitor class is a utility for monitoring various system resources.

    It provides methods to monitor system resources like Disk, CPU, RAM, and NVDIA GPU, 
    if present. The class uses external modules to gather the required data and it logs 
    and raises any exceptions or errors encountered during this process.

    Attributes
    ----------
    config : ConfigParser
        An instance of the ConfigParser class to read configuration settings.
    notifier : Notifier
        An instance of a Notifier class to send alerts if resource usage crosses thresholds.
    gpu_monitor : GpuMonitor or None
        An instance of the GpuMonitor class to monitor GPU usage, if a GPU is present.
    disks : list
        A list of the disk partitions to be monitored.
    """
    def __init__(self, config, notifier):
        self.config = config
        self.disk_monitor = DiskMonitor(notifier)
        self.cpu_monitor = CpuMonitor(notifier)
        self.ram_monitor = RamMonitor(notifier)
        self.gpu_monitor = GpuMonitor(notifier) if self.check_gpu_presence() else None

    def check_gpu_presence(self):
        """Check if a GPU is present on the system."""
        try:
            pynvml.nvmlInit()
            return any(pynvml.nvmlDeviceGetName(pynvml.nvmlDeviceGetHandleByIndex(i)).lower().startswith("nvidia") 
                for i in range(pynvml.nvmlDeviceGetCount()))
        except NVMLError:
            logging.warning("NVML Shared Library Not Found or NVIDIA GPU Driver Not Detected. GPU will not be monitored.")
            return False
        finally:
            pynvml.nvmlShutdown()

    def check_health(self, disk) -> bool:
        """Check the health of the system."""
        device_name = socket.gethostname()
        is_disk_healthy = self.disk_monitor.check_health(device_name, disk, self.config.get_value('general', 'disk_threshold', data_type=int))
        is_cpu_healthy = self.cpu_monitor.check_health(device_name, self.config.get_value('general', 'cpu_threshold', data_type=int))
        is_ram_healthy = self.ram_monitor.check_health(device_name, self.config.get_value('general', 'ram_threshold', data_type=int))
        is_gpu_healthy = self.gpu_monitor.check_health(device_name,
            self.config.get_value('general', 'gpu_threshold', data_type=int),
            self.config.get_value('general', 'gpu_memory_threshold', data_type=int),
            self.config.get_value('general', 'gpu_temp_threshold', data_type=int)) if self.gpu_monitor else True

        return is_disk_healthy and is_cpu_healthy and is_ram_healthy and is_gpu_healthy

# pylint: disable=all
