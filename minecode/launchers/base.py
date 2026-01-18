"""
Base launcher interface and data structures
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Dict, Any


@dataclass
class LauncherInfo:
    """Information about a launcher instance"""
    name: str
    version: Optional[str]
    path: Path
    java_executable: Optional[Path]
    launcher_type: str


class BaseLauncher(ABC):
    """Abstract base class for Minecraft launcher implementations"""
    
    def __init__(self, launcher_path: Path):
        """
        Initialize launcher.
        
        Args:
            launcher_path: Path to the launcher installation
        """
        self.launcher_path = Path(launcher_path)
    
    @abstractmethod
    def detect(self) -> bool:
        """
        Check if this launcher is installed at the specified path.
        
        Returns:
            True if launcher is detected, False otherwise
        """
        pass
    
    @abstractmethod
    def get_instances(self) -> List[Dict[str, Any]]:
        """
        Get list of game instances/profiles.
        
        Returns:
            List of instance dictionaries with name, path, version, etc.
        """
        pass
    
    @abstractmethod
    def get_logs(self, instance_name: str) -> Optional[str]:
        """
        Get latest log content from an instance.
        
        Args:
            instance_name: Name of the instance
            
        Returns:
            Log content as string, or None if not found
        """
        pass
    
    @abstractmethod
    def clear_logs(self, instance_name: str) -> bool:
        """
        Clear logs for an instance.
        
        Args:
            instance_name: Name of the instance
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def get_launcher_info(self) -> LauncherInfo:
        """
        Get information about the launcher itself.
        
        Returns:
            LauncherInfo object with launcher details
        """
        pass
    
    def get_instance_logs_directory(self, instance_name: str) -> Optional[Path]:
        """
        Get the logs directory for an instance.
        
        Args:
            instance_name: Name of the instance
            
        Returns:
            Path to logs directory or None if not found
        """
        pass
