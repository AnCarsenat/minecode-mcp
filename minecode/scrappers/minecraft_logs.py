"""
Minecraft Log File Locator
Finds and retrieves logs from various Minecraft launchers
"""

import os
import platform
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# Constants
MAX_LOG_LINES = 1000  # Maximum number of lines to return for safety


def get_default_minecraft_dir() -> Path:
    """Get the default Minecraft directory based on the operating system."""
    system = platform.system()
    
    if system == "Windows":
        return Path(os.environ.get("APPDATA", "")) / ".minecraft"
    elif system == "Darwin":  # macOS
        return Path.home() / "Library" / "Application Support" / "minecraft"
    else:  # Linux and others
        return Path.home() / ".minecraft"


def get_prism_launcher_dir() -> Path:
    """Get the Prism Launcher directory based on the operating system."""
    system = platform.system()
    
    if system == "Windows":
        return Path(os.environ.get("APPDATA", "")) / "PrismLauncher"
    elif system == "Darwin":  # macOS
        return Path.home() / "Library" / "Application Support" / "PrismLauncher"
    else:  # Linux
        # Check XDG_DATA_HOME first, fallback to .local/share
        xdg_data = os.environ.get("XDG_DATA_HOME")
        if xdg_data:
            return Path(xdg_data) / "PrismLauncher"
        return Path.home() / ".local" / "share" / "PrismLauncher"


def get_tlauncher_dir() -> Path:
    """Get the TLauncher directory based on the operating system."""
    system = platform.system()
    
    if system == "Windows":
        return Path(os.environ.get("APPDATA", "")) / ".minecraft"
    elif system == "Darwin":  # macOS
        return Path.home() / "Library" / "Application Support" / "minecraft"
    else:  # Linux
        return Path.home() / ".minecraft"


def find_latest_log(base_dir: Path) -> Optional[Path]:
    """Find the latest.log file in the logs directory."""
    logs_dir = base_dir / "logs"
    
    if not logs_dir.exists():
        return None
    
    latest_log = logs_dir / "latest.log"
    if latest_log.exists():
        return latest_log
    
    return None


def find_all_logs(base_dir: Path, limit: int = 10) -> List[Path]:
    """Find all log files in the logs directory, sorted by modification time."""
    logs_dir = base_dir / "logs"
    
    if not logs_dir.exists():
        return []
    
    log_files = []
    
    # Add latest.log first if it exists
    latest_log = logs_dir / "latest.log"
    if latest_log.exists() and latest_log.is_file():
        log_files.append(latest_log)
    
    # Find all .log and .log.gz files
    for log_file in logs_dir.glob("*.log"):
        if log_file.name != "latest.log" and log_file.is_file():
            log_files.append(log_file)
    
    for log_file in logs_dir.glob("*.log.gz"):
        if log_file.is_file():
            log_files.append(log_file)
    
    # Sort by modification time (newest first), keeping latest.log at the top
    if len(log_files) > 1:
        latest = log_files[0] if log_files[0].name == "latest.log" else None
        others = [f for f in log_files if f.name != "latest.log"]
        others.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        log_files = ([latest] if latest else []) + others
    
    return log_files[:limit]


def find_prism_instance_logs(prism_dir: Path, instance_name: Optional[str] = None) -> Dict[str, List[Path]]:
    """Find logs for Prism Launcher instances."""
    instances_dir = prism_dir / "instances"
    
    if not instances_dir.exists():
        return {}
    
    instances = {}
    
    if instance_name:
        # Look for specific instance
        instance_dir = instances_dir / instance_name / ".minecraft"
        if instance_dir.exists():
            logs = find_all_logs(instance_dir)
            if logs:
                instances[instance_name] = logs
    else:
        # Find all instances
        for instance_path in instances_dir.iterdir():
            if instance_path.is_dir():
                minecraft_dir = instance_path / ".minecraft"
                if minecraft_dir.exists():
                    logs = find_all_logs(minecraft_dir)
                    if logs:
                        instances[instance_path.name] = logs
    
    return instances


def calculate_line_count(content: str) -> int:
    """
    Calculate the number of lines in the content.
    
    Args:
        content: The log content string
    
    Returns:
        Number of lines in the content
    """
    if not content:
        return 0
    # Use splitlines() to properly handle different line ending conventions
    return len(content.splitlines())


def read_log_file(log_path: Path, lines: Optional[int] = None, tail: bool = False) -> str:
    """
    Read a log file and return its content.
    
    Args:
        log_path: Path to the log file
        lines: Number of lines to return (None for all)
        tail: If True, return last N lines; if False, return first N lines
    
    Returns:
        Log content as a string, or an empty string if the file doesn't exist
    
    Raises:
        Returns error message string if reading fails
    """
    if not log_path.exists():
        return ""
    
    try:
        # Handle compressed logs
        if log_path.suffix == ".gz":
            import gzip
            with gzip.open(log_path, "rt", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        else:
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        
        if lines is None:
            return content
        
        # Use splitlines() to properly handle line endings
        log_lines = content.splitlines()
        
        if tail:
            selected_lines = log_lines[-lines:]
        else:
            selected_lines = log_lines[:lines]
        
        return "\n".join(selected_lines)
    
    except Exception as e:
        # Return a clearly marked error string
        return f"ERROR_READING_FILE: {str(e)}"


def detect_launcher_type(minecraft_dir: Path) -> str:
    """
    Detect the launcher type based on directory structure and files.
    
    Returns: "default", "prism", "tlauncher", or "unknown"
    """
    # Check for Prism Launcher indicators
    if (minecraft_dir.parent / "instances").exists():
        return "prism"
    
    # Check for TLauncher indicators (they usually have tlauncher files)
    if (minecraft_dir / "tlauncher_profiles.json").exists():
        return "tlauncher"
    
    # Check if it's in PrismLauncher directory
    if "PrismLauncher" in str(minecraft_dir):
        return "prism"
    
    # Default launcher
    if minecraft_dir.name == ".minecraft":
        return "default"
    
    return "unknown"


def get_logs(
    launcher: Optional[str] = None,
    instance: Optional[str] = None,
    lines: Optional[int] = None,
    tail: bool = True
) -> Dict:
    """
    Get Minecraft logs from various launchers.
    
    Args:
        launcher: Launcher type ("default", "prism", "tlauncher", or None for auto-detect)
        instance: Instance name (for Prism Launcher)
        lines: Number of lines to return (None for all, max MAX_LOG_LINES for safety)
        tail: If True, return last N lines; if False, return first N lines
    
    Returns:
        Dictionary with log information and content
    """
    result = {
        "success": False,
        "launcher": launcher or "auto-detect",
        "logs": []
    }
    
    # Limit lines for safety
    if lines is not None and lines > MAX_LOG_LINES:
        lines = MAX_LOG_LINES
    
    try:
        if launcher == "prism" or launcher is None:
            # Try Prism Launcher
            prism_dir = get_prism_launcher_dir()
            if prism_dir.exists():
                instances = find_prism_instance_logs(prism_dir, instance)
                if instances:
                    result["launcher"] = "prism"
                    result["success"] = True
                    
                    for inst_name, log_files in instances.items():
                        for log_file in log_files[:1]:  # Only get latest log per instance
                            content = read_log_file(log_file, lines, tail)
                            # Check if an error occurred during reading
                            if content.startswith("ERROR_READING_FILE:"):
                                lines_shown = 0
                            else:
                                lines_shown = calculate_line_count(content)
                            result["logs"].append({
                                "instance": inst_name,
                                "file": str(log_file.name),
                                "path": str(log_file),
                                "size": log_file.stat().st_size,
                                "content": content,
                                "lines_shown": lines_shown
                            })
                    
                    if result["logs"]:
                        return result
        
        if launcher == "default" or launcher is None:
            # Try default launcher
            default_dir = get_default_minecraft_dir()
            if default_dir.exists():
                latest_log = find_latest_log(default_dir)
                if latest_log:
                    content = read_log_file(latest_log, lines, tail)
                    # Check if an error occurred during reading
                    if content.startswith("ERROR_READING_FILE:"):
                        lines_shown = 0
                    else:
                        lines_shown = calculate_line_count(content)
                    result["launcher"] = "default"
                    result["success"] = True
                    result["logs"].append({
                        "file": str(latest_log.name),
                        "path": str(latest_log),
                        "size": latest_log.stat().st_size,
                        "content": content,
                        "lines_shown": lines_shown
                    })
                    
                    if result["logs"]:
                        return result
        
        if launcher == "tlauncher" or launcher is None:
            # Try TLauncher (uses same directory as default)
            tlauncher_dir = get_tlauncher_dir()
            if tlauncher_dir.exists():
                latest_log = find_latest_log(tlauncher_dir)
                if latest_log:
                    detected_type = detect_launcher_type(tlauncher_dir)
                    if detected_type == "tlauncher" or launcher == "tlauncher":
                        content = read_log_file(latest_log, lines, tail)
                        # Check if an error occurred during reading
                        if content.startswith("ERROR_READING_FILE:"):
                            lines_shown = 0
                        else:
                            lines_shown = calculate_line_count(content)
                        result["launcher"] = "tlauncher"
                        result["success"] = True
                        result["logs"].append({
                            "file": str(latest_log.name),
                            "path": str(latest_log),
                            "size": latest_log.stat().st_size,
                            "content": content,
                            "lines_shown": lines_shown
                        })
                        
                        if result["logs"]:
                            return result
        
        if not result["logs"]:
            result["error"] = "No Minecraft logs found. Checked paths:\n"
            result["error"] += f"- Default: {get_default_minecraft_dir()}\n"
            result["error"] += f"- Prism: {get_prism_launcher_dir()}\n"
            result["error"] += f"- TLauncher: {get_tlauncher_dir()}"
    
    except Exception as e:
        result["error"] = str(e)
    
    return result
