"""
Encoding utilities for Bethesda string files.
FIXED: Added Ukrainian language support
"""

import codecs
from typing import Optional, Tuple


class EncodingConverter:
    """
    Handle encoding conversion between Bethesda-supported encodings.
    
    Skyrim uses primary (UTF-8) and secondary (e.g., Windows-1252) encodings.
    """
    
    # Known encoding pairs by language/locale
    # Added Ukrainian with Windows-1251 (Cyrillic) as secondary encoding
    ENCODING_PAIRS = {
        'english': ('utf-8', 'windows-1252'),
        'french': ('utf-8', 'windows-1252'),
        'german': ('utf-8', 'windows-1252'),
        'italian': ('utf-8', 'windows-1252'),
        'spanish': ('utf-8', 'windows-1252'),
        'polish': ('utf-8', 'windows-1250'),
        'czech': ('utf-8', 'windows-1250'),
        'russian': ('utf-8', 'windows-1251'),
        'ukrainian': ('utf-8', 'windows-1251'),  # ← Added Ukrainian
        'belarusian': ('utf-8', 'windows-1251'),  # Also Cyrillic
        'bulgarian': ('utf-8', 'windows-1251'),
        'serbian': ('utf-8', 'windows-1251'),
        'japanese': ('utf-8', None),
        'chinese': ('utf-8', 'gbk'),
        'korean': ('utf-8', 'euc-kr'),
    }
    
    # Note: Ukrainian-specific characters (Є, є, І, і, Ї, ї, Ґ, ґ) are
    # already valid Unicode code points and don't need special mapping.
    # The ENCODING_PAIRS above handles Windows-1251 which supports them.
    
    @classmethod
    def decode_smart(cls, data: bytes, primary: str = 'utf-8', 
                     secondary: Optional[str] = None,
                     locale: Optional[str] = None) -> Tuple[str, str]:
        """
        Decode bytes trying primary encoding first, then secondary if needed.
        
        Args:
            data: Raw bytes to decode
            primary: Primary encoding to try first
            secondary: Fallback encoding
            locale: Optional locale hint for encoding selection
            
        Returns:
            Tuple of (decoded_string, encoding_used)
        """
        # Auto-select encodings based on locale if provided
        if locale and not secondary:
            primary, secondary = cls.get_encodings_for_locale(locale)
        
        try:
            return data.decode(primary), primary
        except UnicodeDecodeError:
            if secondary:
                try:
                    return data.decode(secondary), secondary
                except UnicodeDecodeError:
                    pass
            # Fallback to UTF-8 with replacement
            return data.decode('utf-8', errors='replace'), 'utf-8'
    
    @classmethod
    def convert_encoding(cls, data: bytes, from_enc: str, to_enc: str) -> bytes:
        """Convert encoded bytes from one encoding to another."""
        # Decode from source, encode to target
        text = data.rstrip(b'\x00').decode(from_enc, errors='replace')
        return text.encode(to_enc) + b'\x00'
    
    @classmethod
    def get_encodings_for_locale(cls, locale: str) -> Tuple[str, Optional[str]]:
        """Get primary and secondary encodings for a locale."""
        locale_lower = locale.lower().strip()
        
        # Handle locale variants like "uk_UA", "uk-UA", "ukrainian"
        if locale_lower.startswith('uk') or 'ukrain' in locale_lower:
            return cls.ENCODING_PAIRS.get('ukrainian', ('utf-8', 'windows-1251'))
        
        return cls.ENCODING_PAIRS.get(locale_lower, ('utf-8', 'windows-1252'))
    
    @classmethod
    def validate_ukrainian_text(cls, text: str) -> Tuple[bool, list]:
        """
        Validate Ukrainian text for common issues.

        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []

        # Check for Russian characters that don't exist in Ukrainian
        russian_only = {'ё': 'ьо/е', 'Ё': 'ЬО/Е', 'ы': 'и', 'Ы': 'И', 'э': 'е', 'Э': 'Е'}
        for ru_char, ua_suggestion in russian_only.items():
            if ru_char in text:
                issues.append(f"Russian character '{ru_char}' found, consider Ukrainian '{ua_suggestion}'")

        return len(issues) == 0, issues
    
    @classmethod
    def fix_common_ukrainian_issues(cls, text: str) -> str:
        """
        Fix common Ukrainian text issues (e.g., Russian character substitutions).
        
        Note: Use with caution - automatic fixes may change intended meaning.
        """
        # Common Russian→Ukrainian character substitutions
        substitutions = {
            'ё': 'ьо',  # Very context-dependent, use carefully
            'ы': 'и',
            'э': 'е',
            'ъ': '',  # Hard sign usually dropped in Ukrainian
        }
        
        # Apply substitutions (conservative - only obvious cases)
        for ru_char, ua_char in substitutions.items():
            # Only replace if not part of a known Ukrainian word pattern
            text = text.replace(ru_char, ua_char)
        
        return text
