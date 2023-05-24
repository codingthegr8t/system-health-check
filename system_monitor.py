import shutil
import logging
import socket
import psutil
import pynvml
import cpuinfo
from pynvml import NVMLError
from notifier import Notifier
from configuration import Configuration

class SystemMonitor:
    """
    The SystemMonitor class is a utility for monitoring system resources.

    This class provides methods to monitor various system resources like Disk, CPU, RAM, and GPU if present.
    It uses various external modules to gather the required data. 
    Any exception or error while fetching data is logged and raised further.

    It also provides methods to check the health of these resources based on certain configurable thresholds.
    In case of any resource crossing its threshold limit, it sends an alert using the provided notifier.

    Attributes:
    config : A Configuration object to hold all threshold values.
    notifier : A Notifier object to send alerts when resource usage exceeds the threshold.
    gpu_present : A boolean indicating if a GPU is present on the system.
    """
    def __init__(self, config: Configuration, notifier: Notifier):
        self.config = config
        self.notifier = notifier
        self.gpu_present = self.check_gpu_presence()

    def get_disk_usage(self, disk):
        """Retrieve disk usage statistics for a given disk."""
        try:
            du = shutil.disk_usage(disk)
            total = du.total / 2**30     # Convert bytes to GB
            free = du.free / 2**30
            percent_free = free / total * 100
        except FileNotFoundError as file_error:
            logging.error("Disk path %s not found.", disk)
            raise FileNotFoundError(f"Disk path {disk} not found.") from file_error
        except PermissionError as perm_error:
            logging.error("Permission denied to access %s.", disk)
            raise PermissionError(f"Permission denied to access {disk}.") from perm_error
        except OSError as os_error:
            logging.error("OS error when retrieving disk usage: %s", os_error)
            raise
        return total, free, percent_free

    def get_cpu_usage(self):
        """Retrieve CPU usage statistics."""
        try:
            usage = psutil.cpu_percent(1)
            info = cpuinfo.get_cpu_info()
        except psutil.Error as err:
            logging.error("Failed to get CPU usage: %s", err)
            raise RuntimeError(f"Unexpected error when retrieving CPU usage: {err}") from err
        return usage, info['brand_raw']

    def get_ram_usage(self):
        """Retrieve RAM usage statistics."""
        try:
            ram = psutil.virtual_memory()
            return ram.total / (1024.0 ** 3), ram.percent
        except psutil.Error as err:
            logging.error("Failed to get RAM usage: %s", err)
            raise RuntimeError(f"Unexpected error when retrieving RAM usage: {err}") from err

    def check_gpu_presence(self):
        """Check if a GPU is present on the system."""
        try:
            pynvml.nvmlInit()
            device_count = pynvml.nvmlDeviceGetCount()
            if device_count > 0:
                # Check if at least one of the GPUs is from NVIDIA
                for i in range(device_count):
                    handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                    device_name = pynvml.nvmlDeviceGetName(handle)
                    if device_name.lower().startswith("nvidia"):
                        return True
            pynvml.nvmlShutdown()
        except pynvml.NVMLError as nvml_err:
            if nvml_err.value in (pynvml.NVML_ERROR_LIBRARY_NOT_FOUND, pynvml.NVML_ERROR_DRIVER_NOT_LOADED):
                logging.warning("NVML Shared Library Not Found or NVIDIA GPU Driver Not Loaded. GPU will be monitored.")
                return False
        return False

    def get_gpu_usage(self):
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
            total_memory_in_gb = total_memory / (1024 ** 3)
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

    def check_disk_health(self, device_name, disk):
        """Check the Disk health."""
        try:
            # Disk health check
            total, free, percent_free = self.get_disk_usage(disk)
            if percent_free <= self.config.disk_threshold:
                self.notifier.alert_format(device_name, "Disks", self.config.disk_threshold)
                logging.warning("Disk %s - Total space: %.1f GB, Free space: %.1f GB, Percentage free: %.1f%%", disk, total, free, percent_free)
                return False
        except Exception as err:
            logging.error("Error while checking disk health: %s", err)
            raise
        return True

    def check_cpu_health(self, device_name):
        """Check the CPU health."""
        try:
            cpu_usage, cpu_info = self.get_cpu_usage()
            if cpu_usage >= self.config.cpu_threshold:
                self.notifier.alert_format(device_name, "CPU", self.config.cpu_threshold)
                logging.warning("%s usage: %s%%", cpu_info, cpu_usage)
                return False
        except Exception as err:
            logging.error("Error while checking cpu health: %s", err)
            raise
        return True

    def check_ram_health(self, device_name):
        """Check the RAM health."""
        try:
            total_ram, percent_ram_used = self.get_ram_usage()
            if percent_ram_used >= self.config.ram_threshold:
                self.notifier.alert_format(device_name, "RAM", self.config.ram_threshold)
                logging.warning("Total System RAM: %.0f GB, RAM usage: %s%%", total_ram, percent_ram_used)
                return False
        except Exception as err:
            logging.error("Error while checking disk health: %s", err)
            raise
        return True

    def check_gpu_health(self, device_name):
        """Check the GPU's health."""
        try:
            gpu_utilization, gpu_total_memory, memory_utilization, gpu_temperature, gpu_name = self.get_gpu_usage()
            alert_info = []

            if gpu_utilization >= self.config.gpu_threshold:
                alert_info.append({"resource_name": "GPU Utilization", "threshold": self.config.gpu_threshold})

            if memory_utilization >= self.config.gpu_memory_threshold:
                alert_info.append({"resource_name": "GPU Memory Utilization", "threshold": self.config.gpu_memory_threshold})

            if gpu_temperature >= self.config.gpu_temp_threshold:
                alert_info.append({"resource_name": "GPU Temperature", "threshold": self.config.gpu_temp_threshold})

            if alert_info:
                resource_name_formatted = ', '.join([f'{info["resource_name"]}' for info in alert_info])
                threshold_formatted = ', '.join([f'{info["threshold"]}' for info in alert_info])
                self.notifier.alert_format(device_name, resource_name_formatted, threshold_formatted)
                logging.warning("%s - GPU Utilization: %s%%, GPU Memory Utilization: %.1f%%, GPU Total Memory: %.0f, GPU Temperature: %s\u2103", gpu_name, gpu_utilization, memory_utilization, gpu_total_memory, gpu_temperature)
                return False
        except Exception as err:
            logging.error("Error while checking GPU health: %s", err)
            raise
        return True

    def check_health(self, disk):
        """Check the health of the system."""
        device_name = socket.gethostname()

        # Check each resource's health separately
        is_disk_healthy = self.check_disk_health(device_name, disk)
        is_cpu_healthy = self.check_cpu_health(device_name)
        is_ram_healthy = self.check_ram_health(device_name)

        # Only check GPU health if a compatible GPU is present
        is_gpu_healthy = self.check_gpu_health(device_name) if self.gpu_present else True

        return is_disk_healthy and is_cpu_healthy and is_ram_healthy and is_gpu_healthy
    