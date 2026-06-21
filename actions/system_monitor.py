try:
    import psutil
    _PSUTIL = True
except ImportError:
    _PSUTIL = False
import platform
import json
from datetime import datetime

def get_system_info() -> str:
    """Get comprehensive system information."""
    try:
        info = {
            "os": platform.system(),
            "os_version": platform.version(),
            "architecture": platform.machine(),
            "cpu_count": psutil.cpu_count(),
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_total": psutil.virtual_memory().total,
            "memory_used": psutil.virtual_memory().used,
            "memory_percent": psutil.virtual_memory().percent,
            "disk_usage": {part.mountpoint: {
                "total": psutil.disk_usage(part.mountpoint).total,
                "used": psutil.disk_usage(part.mountpoint).used,
                "free": psutil.disk_usage(part.mountpoint).free,
                "percent": psutil.disk_usage(part.mountpoint).percent
            } for part in psutil.disk_partitions()},
            "network": {iface: {
                "bytes_sent": psutil.net_io_counters(pernic=True)[iface].bytes_sent,
                "bytes_recv": psutil.net_io_counters(pernic=True)[iface].bytes_recv
            } for iface in psutil.net_io_counters(pernic=True)},
            "processes": len(psutil.pids()),
            "uptime": psutil.boot_time(),
            "timestamp": datetime.now().isoformat()
        }
        return json.dumps(info, indent=2)
    except Exception as e:
        return f"Failed to get system info: {e}"

def system_monitor(parameters: dict = None, response=None, player=None) -> str:
    params = parameters or {}
    action = params.get("action", "info").lower()

    if action == "info":
        return get_system_info()
    else:
        return f"Unknown system monitor action: {action}"