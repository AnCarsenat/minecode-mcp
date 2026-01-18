"""
Vanilla Minecraft Launcher implementation
Supports the official Minecraft Launcher from Mojang/Microsoft
"""

import json
from pathlib import Path
from typing import Optional, List, Dict, Any
import platform

from .base import BaseLauncher, LauncherInfo


class VanillaLauncher(BaseLauncher):
    """Handler for the official Minecraft Launcher"""
    
    LAUNCHER_NAME = "Minecraft Launcher"
    
    def __init__(self, launcher_path: Optional[Path] = None):
        """
        Initialize Vanilla Launcher handler.
        
        Args:
            launcher_path: Path to .minecraft directory
        """
        if launcher_path is None:
            launcher_path = self._get_default_path()
        
        super().__init__(launcher_path)
    
    @staticmethod
    def _get_default_path() -> Path:
        """Get the default .minecraft directory path based on OS"""
        if platform.system() == "Windows":
            return Path.home() / "AppData" / "Roaming" / ".minecraft"
        elif platform.system() == "Darwin":  # macOS
            return Path.home() / "Library" / "Application Support" / "minecraft"
        else:  # Linux
            return Path.home() / ".minecraft"
    
    def detect(self) -> bool:
        """Check if Vanilla Launcher is installed"""
        return (self.launcher_path / "launcher_profiles.json").exists()
    
    def get_launcher_info(self) -> LauncherInfo:
        """Get information about the Vanilla Launcher"""
        profiles_file = self.launcher_path / "launcher_profiles.json"
        version = None
        
        if profiles_file.exists():
            try:
                with open(profiles_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    version = data.get("launcherVersion", {}).get("name")
            except (json.JSONDecodeError, IOError):
                pass
        
        return LauncherInfo(
            name=self.LAUNCHER_NAME,
            version=version,
            path=self.launcher_path,
            java_executable=self._find_java_executable(),
            launcher_type="vanilla"
        )
    
    def get_instances(self) -> List[Dict[str, Any]]:
        """Get list of game versions/profiles"""
        instances = []
        profiles_file = self.launcher_path / "launcher_profiles.json"
        
        if not profiles_file.exists():
            return instances
        
        try:
            with open(profiles_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                profiles = data.get("profiles", {})
                
                for profile_name, profile_data in profiles.items():
                    version = profile_data.get("lastVersionId", "Unknown")
                    game_dir = Path(profile_data.get("gameDir", self.launcher_path / "versions" / version))
                    
                    instances.append({
                        "name": profile_name,
                        "version": version,
                        "path": str(game_dir),
                        "type": "profile",
                        "launcher": "vanilla"
                    })
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error reading launcher profiles: {e}")
        
        return instances
    
    def get_logs(self, instance_name: str) -> Optional[str]:
        """Get latest log content from a profile"""
        logs_dir = self.get_instance_logs_directory(instance_name)
        
        if not logs_dir or not logs_dir.exists():
            return None
        
        # Find latest log file
        log_files = sorted(logs_dir.glob("*.log"), key=lambda x: x.stat().st_mtime, reverse=True)
        
        if not log_files:
            return None
        
        try:
            with open(log_files[0], 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except IOError as e:
            return f"Error reading log: {e}"
    
    def clear_logs(self, instance_name: str) -> bool:
        """Clear logs for a profile"""
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
        """Get logs directory for a profile"""
        # Get game directory from profiles
        profiles_file = self.launcher_path / "launcher_profiles.json"
        
        if not profiles_file.exists():
            return None
        
        try:
            with open(profiles_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                profile = data.get("profiles", {}).get(instance_name)
                
                if profile:
                    game_dir = Path(profile.get("gameDir", self.launcher_path))
                    logs_dir = game_dir / "logs"
                    return logs_dir if logs_dir.exists() else None
        except (json.JSONDecodeError, IOError):
            pass
        
        return None
    
    @staticmethod
    def _find_java_executable() -> Optional[Path]:
        """Try to find Java executable"""
        import shutil
        java_path = shutil.which("java")
        return Path(java_path) if java_path else None
