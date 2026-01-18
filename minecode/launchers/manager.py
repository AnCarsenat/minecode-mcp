"""
Launcher Manager for detecting and managing multiple launchers
"""

from pathlib import Path
from typing import Optional, List, Dict, Any

from .base import BaseLauncher, LauncherInfo
from .vanilla_launcher import VanillaLauncher
from .multimc import MultiMCLauncher, PrismLauncherHandler
from .curseforge import CurseForgeLauncher


class LauncherManager:
    """Manages detection and operations across multiple Minecraft launchers"""
    
    # Supported launchers in order of priority
    SUPPORTED_LAUNCHERS = [
        ("vanilla", VanillaLauncher),
        ("multimc", MultiMCLauncher),
        ("prism", PrismLauncherHandler),
        ("curseforge", CurseForgeLauncher),
    ]
    
    def __init__(self):
        """Initialize the launcher manager"""
        self.detected_launchers: Dict[str, BaseLauncher] = {}
        self._detect_all_launchers()
    
    def _detect_all_launchers(self) -> None:
        """Auto-detect all available launchers"""
        for launcher_name, launcher_class in self.SUPPORTED_LAUNCHERS:
            try:
                launcher = launcher_class()
                if launcher.detect():
                    self.detected_launchers[launcher_name] = launcher
            except Exception as e:
                print(f"Error detecting {launcher_name}: {e}")
    
    def get_available_launchers(self) -> List[str]:
        """Get list of available launcher types"""
        return list(self.detected_launchers.keys())
    
    def get_launcher(self, launcher_type: str) -> Optional[BaseLauncher]:
        """
        Get a specific launcher by type.
        
        Args:
            launcher_type: Type of launcher (vanilla, multimc, prism, curseforge)
            
        Returns:
            Launcher instance or None if not detected
        """
        return self.detected_launchers.get(launcher_type)
    
    def get_all_instances(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get all instances from all detected launchers.
        
        Returns:
            Dictionary mapping launcher type to list of instances
        """
        all_instances = {}
        for launcher_type, launcher in self.detected_launchers.items():
            try:
                all_instances[launcher_type] = launcher.get_instances()
            except Exception as e:
                print(f"Error getting instances from {launcher_type}: {e}")
                all_instances[launcher_type] = []
        
        return all_instances
    
    def get_launcher_infos(self) -> Dict[str, LauncherInfo]:
        """
        Get information about all detected launchers.
        
        Returns:
            Dictionary mapping launcher type to LauncherInfo
        """
        infos = {}
        for launcher_type, launcher in self.detected_launchers.items():
            try:
                infos[launcher_type] = launcher.get_launcher_info()
            except Exception as e:
                print(f"Error getting info from {launcher_type}: {e}")
        
        return infos
    
    def get_logs(self, launcher_type: str, instance_name: str) -> Optional[str]:
        """
        Get logs from a specific instance.
        
        Args:
            launcher_type: Type of launcher
            instance_name: Name of the instance
            
        Returns:
            Log content or error message
        """
        launcher = self.get_launcher(launcher_type)
        if not launcher:
            return f"Launcher {launcher_type} not found"
        
        try:
            logs = launcher.get_logs(instance_name)
            if logs is None:
                return f"No logs found for instance {instance_name}"
            return logs
        except Exception as e:
            return f"Error retrieving logs: {str(e)}"
    
    def clear_logs(self, launcher_type: str, instance_name: str) -> bool:
        """
        Clear logs from a specific instance.
        
        Args:
            launcher_type: Type of launcher
            instance_name: Name of the instance
            
        Returns:
            True if successful, False otherwise
        """
        launcher = self.get_launcher(launcher_type)
        if not launcher:
            print(f"Launcher {launcher_type} not found")
            return False
        
        try:
            return launcher.clear_logs(instance_name)
        except Exception as e:
            print(f"Error clearing logs: {str(e)}")
            return False
    
    def get_instance_logs_directory(self, launcher_type: str, instance_name: str) -> Optional[Path]:
        """
        Get the logs directory for an instance.
        
        Args:
            launcher_type: Type of launcher
            instance_name: Name of the instance
            
        Returns:
            Path to logs directory or None
        """
        launcher = self.get_launcher(launcher_type)
        if not launcher:
            return None
        
        try:
            return launcher.get_instance_logs_directory(instance_name)
        except Exception as e:
            print(f"Error getting logs directory: {str(e)}")
            return None
    
    def register_custom_launcher(self, launcher_type: str, launcher: BaseLauncher) -> None:
        """
        Register a custom launcher implementation.
        
        Args:
            launcher_type: Type identifier for the launcher
            launcher: BaseLauncher instance
        """
        self.detected_launchers[launcher_type] = launcher
