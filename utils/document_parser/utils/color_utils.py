"""
Color utility functions.

Functions for working with colors in different formats
(HEX, RGB, integer).
"""

import math
from typing import Tuple


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """
    Convert HEX color to RGB tuple.
    
    Args:
        hex_color: HEX color string (with or without #, short or long format)
        
    Returns:
        Tuple of (R, G, B) values (0-255)
        
    Examples:
        >>> hex_to_rgb("#ff0000")
        (255, 0, 0)
        >>> hex_to_rgb("ff0000")
        (255, 0, 0)
        >>> hex_to_rgb("#f00")
        (255, 0, 0)
    """
    # Remove # prefix if present
    hex_color = hex_color.lstrip('#')
    
    # Handle short format (3 chars)
    if len(hex_color) == 3:
        hex_color = ''.join(c * 2 for c in hex_color)
    
    # Parse RGB values
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    
    return (r, g, b)


def rgb_to_hex(r: int, g: int, b: int) -> str:
    """
    Convert RGB values to HEX color string.
    
    Args:
        r: Red value (0-255)
        g: Green value (0-255)
        b: Blue value (0-255)
        
    Returns:
        HEX color string with # prefix
        
    Examples:
        >>> rgb_to_hex(255, 0, 0)
        '#ff0000'
    """
    # Clamp values to valid range
    r = max(0, min(255, r))
    g = max(0, min(255, g))
    b = max(0, min(255, b))
    
    return f"#{r:02x}{g:02x}{b:02x}"


def int_to_hex(color_int: int) -> str:
    """
    Convert integer color value to HEX string.
    
    Args:
        color_int: Integer color value (0xRRGGBB format)
        
    Returns:
        HEX color string with # prefix
        
    Examples:
        >>> int_to_hex(0xFF0000)
        '#ff0000'
    """
    r = (color_int >> 16) & 0xFF
    g = (color_int >> 8) & 0xFF
    b = color_int & 0xFF
    return f"#{r:02x}{g:02x}{b:02x}"


def hex_to_int(hex_color: str) -> int:
    """
    Convert HEX color string to integer value.
    
    Args:
        hex_color: HEX color string (with or without #)
        
    Returns:
        Integer color value in 0xRRGGBB format
        
    Examples:
        >>> hex_to_int("#ff0000")
        16711680
    """
    hex_color = hex_color.lstrip('#')
    
    # Handle short format
    if len(hex_color) == 3:
        hex_color = ''.join(c * 2 for c in hex_color)
    
    return int(hex_color, 16)


def color_distance(color1: str, color2: str) -> float:
    """
    Calculate Euclidean distance between two colors in RGB space.
    
    Args:
        color1: First HEX color
        color2: Second HEX color
        
    Returns:
        Distance value (0 for identical colors, ~441.67 for black/white)
        
    Examples:
        >>> color_distance("#000000", "#000000")
        0.0
        >>> color_distance("#000000", "#ffffff") > 400
        True
    """
    r1, g1, b1 = hex_to_rgb(color1)
    r2, g2, b2 = hex_to_rgb(color2)
    
    return math.sqrt((r2 - r1) ** 2 + (g2 - g1) ** 2 + (b2 - b1) ** 2)


def is_dark_color(hex_color: str, threshold: float = 128.0) -> bool:
    """
    Check if a color is dark based on luminance.
    
    Uses relative luminance formula:
    L = 0.299 * R + 0.587 * G + 0.114 * B
    
    Args:
        hex_color: HEX color string
        threshold: Luminance threshold (default 128)
        
    Returns:
        True if color is dark, False otherwise
        
    Examples:
        >>> is_dark_color("#000000")
        True
        >>> is_dark_color("#ffffff")
        False
    """
    r, g, b = hex_to_rgb(hex_color)
    
    # Calculate relative luminance
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    
    return luminance < threshold


def normalize_color(color: str) -> str:
    """
    Normalize color to lowercase HEX format with # prefix.
    
    Args:
        color: Color string in any supported format
        
    Returns:
        Normalized HEX color string
        
    Examples:
        >>> normalize_color("#FF0000")
        '#ff0000'
        >>> normalize_color("ff0000")
        '#ff0000'
        >>> normalize_color("#f00")
        '#ff0000'
    """
    # Remove # prefix if present
    color = color.lstrip('#')
    
    # Handle short format
    if len(color) == 3:
        color = ''.join(c * 2 for c in color)
    
    return f"#{color.lower()}"
