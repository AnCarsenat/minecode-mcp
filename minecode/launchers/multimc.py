"""
MultiMC and Prism Launcher implementations
Supports MultiMC and its fork Prism Launcher
"""

import json
from pathlib import Path
from typing import Optional, List, Dict, Any
import platform

from .base import BaseLauncher, LauncherInfo


class MultiMCLauncher(BaseLauncher):
    """Handler for MultiMC launcher"""
    
    LAUNCHER_NAME = "MultiMC"
    
    def __init__(self, launcher_path: Optional[Path] = None):
        """
        Initialize MultiMC handler.
        
        Args:
            launcher_path: Path to MultiMC installation
        """
        if launcher_path is None:
            launcher_path = self._get_default_path()
        
        super().__init__(launcher_path)
    
    @staticmethod
    def _get_default_path() -> Path:
        """Get the default MultiMC directory path based on OS"""
        if platform.system() == "Windows":
            # Check common installation locations
            candidates = [
                Path.home() / "AppData" / "Local" / "MultiMC",
                Path("C:\\MultiMC"),
                Path("C:\\Program Files") / "MultiMC",
            ]
            for candidate in candidates:
                if candidate.exists():
                    return candidate
            return Path.home() / "AppData" / "Local" / "MultiMC"
        elif platform.system() == "Darwin":  # macOS
            return Path.home() / "Applications" / "MultiMC.app" / "Contents" / "MacOS"
        else:  # Linux
            return Path.home() / ".local" / "share" / "multimc"
    
    def detect(self) -> bool:
        """Check if MultiMC is installed"""
        return (self.launcher_path / "instances").exists()
    
    def get_launcher_info(self) -> LauncherInfo:
        """Get information about MultiMC"""
        # Try to read version from launcher config
        version = None
        version_file = self.launcher_path / "version.txt"
        if version_file.exists():
            try:
                version = version_file.read_text(encoding='utf-8').strip()
            except IOError:
                pass
        
        return LauncherInfo(
            name=self.LAUNCHER_NAME,
            version=version,
            path=self.launcher_path,
            java_executable=self._find_java_executable(),
            launcher_type="multimc"
        )
    
    def get_instances(self) -> List[Dict[str, Any]]:
        """Get list of MultiMC instances"""
        instances = []
        instances_dir = self.launcher_path / "instances"
        
        if not instances_dir.exists():
            return instances
        
        for instance_path in instances_dir.iterdir():
            if not instance_path.is_dir():
                continue
            
            # Read instance.cfg
            instance_cfg = instance_path / "instance.cfg"
            if not instance_cfg.exists():
                continue
            
            try:
                config = {}
                with open(instance_cfg, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if '=' in line and not line.startswith('['):
                            key, value = line.split('=', 1)
                            config[key.strip()] = value.strip()
                
                instances.append({
                    "name": instance_path.name,
                    "version": config.get("InstanceType", "Unknown"),
                    "path": str(instance_path),
                    "type": "instance",
                    "launcher": "multimc"
                })
            except IOError:
                continue
        
        return instances
    
    def get_logs(self, instance_name: str) -> Optional[str]:
        """Get latest log content from a MultiMC instance"""
        logs_dir = self.get_instance_logs_directory(instance_name)
        
        if not logs_dir or not logs_dir.exists():
            return None
        
        # MultiMC typically stores logs as latest.log
        latest_log = logs_dir / "latest.log"
        if latest_log.exists():
            try:
                with open(latest_log, 'r', encoding='utf-8', errors='ignore') as f:
                    return f.read()
            except IOError as e:
                return f"Error reading log: {e}"
        
        return None
    
    def clear_logs(self, instance_name: str) -> bool:
        """Clear logs for a MultiMC instance"""
        logs_dir = self.get_instance_logs_directory(instance_name)
        
        if not logs_dir or not logs_dir.exists():
            return False
        
        try:
            # Clear all log files
            for log_file in logs_dir.glob("*.log"):
                log_file.unlink()
            return True
        except (IOError, OSError) as e:
            print(f"Error clearing logs: {e}")
            return False
    
    def get_instance_logs_directory(self, instance_name: str) -> Optional[Path]:
        """Get logs directory for a MultiMC instance"""
        instance_path = self.launcher_path / "instances" / instance_name
        
        if not instance_path.exists():
            return None
        
        logs_dir = instance_path / ".minecraft" / "logs"
        return logs_dir if logs_dir.exists() else None
    
    @staticmethod
    def _find_java_executable() -> Optional[Path]:
        """Try to find Java executable"""
        import shutil
        java_path = shutil.which("java")
        return Path(java_path) if java_path else None


class PrismLauncherHandler(MultiMCLauncher):
    """Handler for Prism Launcher (fork of MultiMC)"""
    
    LAUNCHER_NAME = "Prism Launcher"
    
    def __init__(self, launcher_path: Optional[Path] = None):
        """
        Initialize Prism Launcher handler.
        
        Args:
            launcher_path: Path to Prism Launcher installation
        """
        if launcher_path is None:
            launcher_path = self._get_default_path()
        
        super().__init__(launcher_path)
    
    @staticmethod
    def _get_default_path() -> Path:
        """Get the default Prism Launcher directory path based on OS"""
        if platform.system() == "Windows":
            candidates = [
                Path.home() / "AppData" / "Local" / "Prism Launcher",
                Path("C:\\Prism Launcher"),
                Path("C:\\Program Files") / "Prism Launcher",
            ]
            for candidate in candidates:
                if candidate.exists():
                    return candidate
            return Path.home() / "AppData" / "Local" / "Prism Launcher"
        elif platform.system() == "Darwin":  # macOS
            return Path.home() / "Applications" / "Prism Launcher.app" / "Contents" / "MacOS"
        else:  # Linux
            return Path.home() / ".local" / "share" / "PrismLauncher"
    
    def detect(self) -> bool:
        """Check if Prism Launcher is installed"""
        return (self.launcher_path / "instances").exists()
    
    def get_launcher_info(self) -> LauncherInfo:
        """Get information about Prism Launcher"""
        version = None
        version_file = self.launcher_path / "prismlauncher_version.txt"
        if version_file.exists():
            try:
                version = version_file.read_text(encoding='utf-8').strip()
            except IOError:
                pass
        
        return LauncherInfo(
            name=self.LAUNCHER_NAME,
            version=version,
            path=self.launcher_path,
            java_executable=self._find_java_executable(),
            launcher_type="prism"
        )
