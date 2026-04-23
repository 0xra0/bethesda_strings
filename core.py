"""
Core classes for parsing Bethesda string files.
"""

import struct
from dataclasses import dataclass, field
from typing import Optional, Callable, List
from pathlib import Path


@dataclass
class StringDataObject:
    """
    Represents a single string entry from a Bethesda string file.
    
    Mirrors the TypeScript interface from the original library.
    """
    id: int                          # String ID used by game files
    address: int                     # Absolute file offset of directory entry
    relative_offset: int             # Offset from start of string data section
    absolute_offset: int             # Absolute file offset of string data
    null_point: int                  # Position of null terminator
    length: int                      # Length of string (excluding length prefix for dl/ilstrings)
    string_array: bytearray          # Raw bytes of the string (with encoding)
    has_length_prefix: bool = False  # True for .dlstrings/.ilstrings
    
    def get_string(self, encoding: str = 'utf-8', errors: str = 'replace') -> str:
        """Decode the string array to a Python string.
        
        Args:
            encoding: Character encoding to use for decoding
            errors: Error handling scheme passed to bytes.decode()
        """
        data = self.string_array
        # Skip 4-byte length prefix for dlstrings/ilstrings if present
        if self.has_length_prefix and len(data) >= 4:
            data = data[4:]
        # Remove null terminator
        if data and data[-1] == 0:
            data = data[:-1]
        return data.decode(encoding, errors=errors)
    
    def set_string(self, text: str, encoding: str = 'utf-8') -> None:
        """Encode a Python string and update string_array."""
        encoded = text.encode(encoding) + b'\x00'  # Add null terminator
        if self.has_length_prefix:
            # Prepend 4-byte little-endian length (including null)
            length = len(encoded)
            self.string_array = struct.pack('<I', length) + encoded
        else:
            self.string_array = bytearray(encoded)
        # Update derived fields
        self.length = len(encoded) - 1  # Exclude null terminator
        self.null_point = len(self.string_array) - 1


class BethesdaStringFile:
    """
    Main class for reading and writing Bethesda string files.
    
    Supports .strings, .dlstrings, and .ilstrings formats.
    """
    
    HEADER_SIZE = 8
    DIRECTORY_ENTRY_SIZE = 8
    
    def __init__(self, file_path: Optional[str] = None,
                 file_extension: Optional[str] = None,
                 buffer: Optional[bytes] = None):
        """
        Initialize from file path or raw buffer.

        Args:
            file_path: Path to .strings/.dlstrings/.ilstrings file
            file_extension: File extension (without dot), e.g., 'dlstrings'
            buffer: Raw bytes buffer (alternative to file_path)
        """
        self.file_extension = (file_extension or '').lower().lstrip('.')
        self.strings: List[StringDataObject] = []
        self._header_count: int = 0
        self._header_data_size: int = 0
        self._raw_buffer: Optional[bytearray] = None
        self._id_index: Optional[dict[int, int]] = None  # id -> index in self.strings

        if buffer is not None:
            self._raw_buffer = bytearray(buffer)
            self._parse()
        elif file_path:
            self.load(file_path)
    
    def load(self, file_path: str) -> None:
        """Load a string file from disk."""
        path = Path(file_path)
        if not self.file_extension:
            self.file_extension = path.suffix.lstrip('.').lower()
        
        with open(path, 'rb') as f:
            self._raw_buffer = bytearray(f.read())
        self._parse()
    
    def save(self, file_path: str) -> None:
        """Write the modified string file to disk."""
        self._rebuild()
        with open(file_path, 'wb') as f:
            f.write(self._raw_buffer)
    
    def _parse(self) -> None:
        """Parse the binary buffer into StringDataObject entries."""
        if not self._raw_buffer or len(self._raw_buffer) < self.HEADER_SIZE:
            raise ValueError("Invalid or empty string file")
        
        # Parse header
        entry_count, data_size = struct.unpack('<II', self._raw_buffer[:self.HEADER_SIZE])
        self._header_count = entry_count
        self._header_data_size = data_size
        
        # Calculate offsets
        directory_start = self.HEADER_SIZE
        data_start = directory_start + (entry_count * self.DIRECTORY_ENTRY_SIZE)
        
        # Has length prefix for dlstrings/ilstrings
        has_length_prefix = self.file_extension in ('dlstrings', 'ilstrings')
        
        # Parse directory entries
        self.strings = []
        for i in range(entry_count):
            entry_offset = directory_start + (i * self.DIRECTORY_ENTRY_SIZE)
            string_id, rel_offset = struct.unpack(
                '<II', 
                self._raw_buffer[entry_offset:entry_offset + self.DIRECTORY_ENTRY_SIZE]
            )
            
            abs_offset = data_start + rel_offset
            
            # Parse string data
            if has_length_prefix:
                # Read length prefix
                if abs_offset + 4 > len(self._raw_buffer):
                    continue
                str_length = struct.unpack(
                    '<I', 
                    self._raw_buffer[abs_offset:abs_offset + 4]
                )[0]
                null_point = abs_offset + 4 + str_length - 1
                string_array = bytearray(
                    self._raw_buffer[abs_offset:abs_offset + 4 + str_length]
                )
            else:
                # Find null terminator for .strings files
                null_point = abs_offset
                # Bounds check: don't scan past end of buffer
                if abs_offset >= len(self._raw_buffer):
                    continue
                while null_point < len(self._raw_buffer) and self._raw_buffer[null_point] != 0:
                    null_point += 1
                # If we hit end of buffer without finding null, skip this entry
                if null_point >= len(self._raw_buffer):
                    continue
                string_array = bytearray(
                    self._raw_buffer[abs_offset:null_point + 1]
                )
            
            string_obj = StringDataObject(
                id=string_id,
                address=entry_offset,
                relative_offset=rel_offset,
                absolute_offset=abs_offset,
                null_point=null_point,
                length=len(string_array) - (4 if has_length_prefix else 1),
                string_array=string_array,
                has_length_prefix=has_length_prefix
            )
            self.strings.append(string_obj)
    
    def _rebuild(self) -> None:
        """Rebuild the binary buffer from modified StringDataObjects.
        
        Updates all StringDataObject offset fields to match the new buffer layout.
        """
        if not self._raw_buffer:
            return

        has_length_prefix = self.file_extension in ('dlstrings', 'ilstrings')

        # Collect all string data, tracking new offsets
        new_data_sections: List[bytearray] = []
        offset_map: dict[int, int] = {}  # old rel_offset -> new rel_offset

        for s in self.strings:
            rel_offset = len(b''.join(new_data_sections))
            offset_map[s.relative_offset] = rel_offset
            new_data_sections.append(s.string_array)

        # Build new buffer
        new_buffer = bytearray()

        # Write header (data size will be updated)
        new_buffer.extend(struct.pack('<II', len(self.strings), 0))

        # Write directory entries with updated offsets
        for s in self.strings:
            new_rel_offset = offset_map[s.relative_offset]
            new_buffer.extend(struct.pack('<II', s.id, new_rel_offset))

        # Write string data and update all StringDataObject offset fields
        data_start = len(new_buffer)
        current_data_offset = 0
        for i, section in enumerate(new_data_sections):
            new_buffer.extend(section)
            # Update the StringDataObject with new offsets
            s = self.strings[i]
            s.relative_offset = current_data_offset
            s.absolute_offset = data_start + current_data_offset
            # null_point is relative to the start of the string_array within the new buffer
            # Recalculate based on actual string_array length
            if s.string_array:
                s.null_point = s.absolute_offset + len(s.string_array) - 1
            current_data_offset += len(section)

        # Update header with actual data size
        actual_data_size = len(new_buffer) - data_start
        struct.pack_into('<I', new_buffer, 4, actual_data_size)

        self._raw_buffer = new_buffer
    
    def filter_and_modify(self, 
                         condition_fx: Callable[[StringDataObject], bool],
                         modification_fx: Callable[[bytearray, Optional[StringDataObject]], bytearray]) -> int:
        """
        Apply filter and modification functions to strings.
        
        Mirrors the original library's pipeline approach.
        
        Args:
            condition_fx: Filter function returning True for strings to modify
            modification_fx: Function that takes string_array and optional StringDataObject,
                           returns modified bytearray
            
        Returns:
            Number of strings that were modified
        """
        modified_count = 0
        for s in self.strings:
            if condition_fx(s):
                original = s.string_array
                modified = modification_fx(bytearray(original), s)
                if modified != original:
                    s.string_array = modified
                    # Update length field if needed
                    if s.has_length_prefix and len(modified) >= 4:
                        struct.pack_into('<I', s.string_array, 0, len(modified))
                    modified_count += 1
        return modified_count
    
    def get_by_id(self, string_id: int) -> Optional[StringDataObject]:
        """Get a string by its ID (O(1) lookup via cached index)."""
        if self._id_index is None:
            self._build_id_index()
        idx = self._id_index.get(string_id)
        if idx is not None and idx < len(self.strings):
            return self.strings[idx]
        return None

    def _build_id_index(self) -> None:
        """Build the id -> index mapping for O(1) lookups."""
        self._id_index = {}
        for i, s in enumerate(self.strings):
            self._id_index[s.id] = i

    def _invalidate_index(self) -> None:
        """Invalidate the ID index (call after modifying string list)."""
        self._id_index = None
    
    def __len__(self) -> int:
        return len(self.strings)
    
    def __iter__(self):
        return iter(self.strings)
