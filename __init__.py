"""
Python library for reading and editing Bethesda Skyrim string files.
Supports .strings, .dlstrings, and .ilstrings formats.
"""

from .core import BethesdaStringFile, StringDataObject
from .operations import FilterFunction, ModificationFunction
from .encoding import EncodingConverter

__version__ = "0.1.0"
__all__ = [
    "BethesdaStringFile",
    "StringDataObject", 
    "FilterFunction",
    "ModificationFunction",
    "EncodingConverter"
]
