"""
CurseForge Minecraft launcher implementation
"""

import json
from pathlib import Path
from typing import Optional, List, Dict, Any
import platform

from .base import BaseLauncher, LauncherInfo


class CurseForgeLauncher(BaseLauncher):
    """Handler for CurseForge Minecraft launcher"""
    
    LAUNCHER_NAME = "CurseForge Launcher"
    
    def __init__(self, launcher_path: Optional[Path] = None):
        """
        Initialize CurseForge Launcher handler.
        
        Args:
            launcher_path: Path to CurseForge Launcher installation
        """
        if launcher_path is None:
            launcher_path = self._get_default_path()
        
        super().__init__(launcher_path)
    
    @staticmethod
    def _get_default_path() -> Path:
        """Get the default CurseForge Launcher directory path based on OS"""
        if platform.system() == "Windows":
            return Path.home() / "AppData" / "Local" / "CurseForge"
        elif platform.system() == "Darwin":  # macOS
            return Path.home() / "Library" / "Application Support" / "CurseForge"
        else:  # Linux
            return Path.home() / ".curseforge"
    
    def detect(self) -> bool:
        """Check if CurseForge Launcher is installed"""
        # Check for CurseForge application files
        return (self.launcher_path / "Instances").exists()
    
    def get_launcher_info(self) -> LauncherInfo:
        """Get information about CurseForge Launcher"""
        return LauncherInfo(
            name=self.LAUNCHER_NAME,
            version=None,  # CurseForge doesn't expose version easily
            path=self.launcher_path,
            java_executable=self._find_java_executable(),
            launcher_type="curseforge"
        )
    
    def get_instances(self) -> List[Dict[str, Any]]:
        """Get list of CurseForge modpack instances"""
        instances = []
        instances_dir = self.launcher_path / "Instances"
        
        if not instances_dir.exists():
            return instances
        
        for instance_path in instances_dir.iterdir():
            if not instance_path.is_dir():
                continue
            
            # Read manifest.json or instance info
            manifest_file = instance_path / "manifest.json"
            
            instance_info = {
                "name": instance_path.name,
                "path": str(instance_path),
                "type": "modpack",
                "launcher": "curseforge"
            }
            
            if manifest_file.exists():
                try:
                    with open(manifest_file, 'r', encoding='utf-8') as f:
                        manifest = json.load(f)
                        instance_info["version"] = manifest.get("minecraft", {}).get("version", "Unknown")
                except (json.JSONDecodeError, IOError):
                    instance_info["version"] = "Unknown"
            else:
                instance_info["version"] = "Unknown"
            
            instances.append(instance_info)
        
        return instances
    
    def get_logs(self, instance_name: str) -> Optional[str]:
        """Get latest log content from a CurseForge instance"""
        logs_dir = self.get_instance_logs_directory(instance_name)
        
        if not logs_dir or not logs_dir.exists():
            return None
        
        # CurseForge stores logs in .minecraft/logs
        latest_log = logs_dir / "latest.log"
        if latest_log.exists():
            try:
                with open(latest_log, 'r', encoding='utf-8', errors='ignore') as f:
                    return f.read()
            except IOError as e:
                return f"Error reading log: {e}"
        
        return None
    
    def clear_logs(self, instance_name: str) -> bool:
        """Clear logs for a CurseForge instance"""
        logs_dir = self.get_instance_logs_directory(instance_name)
        
        if not logs_dir or not logs_dir.exists():
            return False
        
        try:
            for log_file in logs_dir.glob("*.log"):
                log_file.unlink()
            return True
        except (IOError, OSError) as e:
            print(f"Error clearing logs: {e}")
            return False
    
    def get_instance_logs_directory(self, instance_name: str) -> Optional[Path]:
        """Get logs directory for a CurseForge instance"""
        instance_path = self.launcher_path / "Instances" / instance_name
        
        if not instance_path.exists():
            return None
        
        # CurseForge typically uses a minecraft directory structure
        logs_dir = instance_path / ".minecraft" / "logs"
        if not logs_dir.exists():
            # Some versions might have different structure
            logs_dir = instance_path / "logs"
        
        return logs_dir if logs_dir.exists() else None
    
    @staticmethod
    def _find_java_executable() -> Optional[Path]:
        """Try to find Java executable"""
        import shutil
        java_path = shutil.which("java")
        return Path(java_path) if java_path else None
