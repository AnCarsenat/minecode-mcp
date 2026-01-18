"""
Minecraft Launcher Support Module
Provides abstractions and implementations for various Minecraft launchers
"""

from .base import BaseLauncher, LauncherInfo
from .vanilla_launcher import VanillaLauncher
from .multimc import MultiMCLauncher
from .prism_launcher import PrismLauncherHandler
from .curseforge import CurseForgeLauncher
from .manager import LauncherManager

__all__ = [
    "BaseLauncher",
    "LauncherInfo",
    "VanillaLauncher",
    "MultiMCLauncher",
    "PrismLauncherHandler",
    "CurseForgeLauncher",
    "LauncherManager",
]
