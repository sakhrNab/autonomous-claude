"""
MCP Module

Manages MCP server discovery, installation, and capability matching.

This module enables the autonomous operator to:
1. Know what MCPs are available
2. Match user intent to required MCPs
3. Auto-install MCPs when needed
4. Stay aware of new capabilities
"""

from .registry import MCPRegistry, MCPServer, MCPCategory, MCPCapability
from .capability_matcher import CapabilityMatcher, IntentAnalysis, CapabilityMatch

__all__ = [
    "MCPRegistry",
    "MCPServer",
    "MCPCategory",
    "MCPCapability",
    "CapabilityMatcher",
    "IntentAnalysis",
    "CapabilityMatch",
]
