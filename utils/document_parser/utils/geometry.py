"""
Geometry utility functions.

Functions and classes for geometric calculations used in
document analysis (rectangles, points, overlaps, etc.).
"""

from dataclasses import dataclass
from typing import Optional
import math


@dataclass
class Point:
    """
    A 2D point.
    
    Attributes:
        x: X coordinate
        y: Y coordinate
    """
    x: float
    y: float


@dataclass
class Rect:
    """
    A rectangle defined by two corner points.
    
    Attributes:
        x0: Left boundary
        y0: Top boundary
        x1: Right boundary
        y1: Bottom boundary
    """
    x0: float
    y0: float
    x1: float
    y1: float
    
    @property
    def width(self) -> float:
        """Width of the rectangle."""
        return self.x1 - self.x0
    
    @property
    def height(self) -> float:
        """Height of the rectangle."""
        return self.y1 - self.y0
    
    @property
    def area(self) -> float:
        """Area of the rectangle."""
        return self.width * self.height
    
    @property
    def center(self) -> Point:
        """Center point of the rectangle."""
        return Point(
            x=(self.x0 + self.x1) / 2,
            y=(self.y0 + self.y1) / 2
        )


def rects_overlap(r1: Rect, r2: Rect) -> bool:
    """
    Check if two rectangles overlap.
    
    Args:
        r1: First rectangle
        r2: Second rectangle
        
    Returns:
        True if rectangles overlap, False otherwise
        
    Examples:
        >>> r1 = Rect(0, 0, 50, 50)
        >>> r2 = Rect(25, 25, 75, 75)
        >>> rects_overlap(r1, r2)
        True
    """
    return (r1.x0 < r2.x1 and 
            r1.x1 > r2.x0 and 
            r1.y0 < r2.y1 and 
            r1.y1 > r2.y0)


def rect_contains(outer: Rect, inner: Rect) -> bool:
    """
    Check if one rectangle completely contains another.
    
    Args:
        outer: The containing rectangle
        inner: The potentially contained rectangle
        
    Returns:
        True if outer contains inner, False otherwise
        
    Examples:
        >>> outer = Rect(0, 0, 100, 100)
        >>> inner = Rect(10, 10, 50, 50)
        >>> rect_contains(outer, inner)
        True
    """
    return (outer.x0 <= inner.x0 and 
            outer.y0 <= inner.y0 and 
            outer.x1 >= inner.x1 and 
            outer.y1 >= inner.y1)


def rect_intersection(r1: Rect, r2: Rect) -> Optional[Rect]:
    """
    Calculate the intersection of two rectangles.
    
    Args:
        r1: First rectangle
        r2: Second rectangle
        
    Returns:
        Intersection rectangle, or None if no overlap
        
    Examples:
        >>> r1 = Rect(0, 0, 50, 50)
        >>> r2 = Rect(25, 25, 75, 75)
        >>> rect_intersection(r1, r2)
        Rect(x0=25, y0=25, x1=50, y1=50)
    """
    if not rects_overlap(r1, r2):
        return None
    
    return Rect(
        x0=max(r1.x0, r2.x0),
        y0=max(r1.y0, r2.y0),
        x1=min(r1.x1, r2.x1),
        y1=min(r1.y1, r2.y1)
    )


def rect_union(r1: Rect, r2: Rect) -> Rect:
    """
    Calculate the bounding rectangle that contains both rectangles.
    
    Args:
        r1: First rectangle
        r2: Second rectangle
        
    Returns:
        Union rectangle (smallest rectangle containing both)
        
    Examples:
        >>> r1 = Rect(0, 0, 50, 50)
        >>> r2 = Rect(25, 25, 75, 75)
        >>> rect_union(r1, r2)
        Rect(x0=0, y0=0, x1=75, y1=75)
    """
    return Rect(
        x0=min(r1.x0, r2.x0),
        y0=min(r1.y0, r2.y0),
        x1=max(r1.x1, r2.x1),
        y1=max(r1.y1, r2.y1)
    )


def point_in_rect(point: Point, rect: Rect) -> bool:
    """
    Check if a point is inside a rectangle (inclusive).
    
    Args:
        point: The point to check
        rect: The rectangle
        
    Returns:
        True if point is inside or on the boundary of rect
        
    Examples:
        >>> point_in_rect(Point(50, 50), Rect(0, 0, 100, 100))
        True
    """
    return (rect.x0 <= point.x <= rect.x1 and 
            rect.y0 <= point.y <= rect.y1)


def distance_between_points(p1: Point, p2: Point) -> float:
    """
    Calculate Euclidean distance between two points.
    
    Args:
        p1: First point
        p2: Second point
        
    Returns:
        Distance between points
        
    Examples:
        >>> distance_between_points(Point(0, 0), Point(3, 4))
        5.0
    """
    return math.sqrt((p2.x - p1.x) ** 2 + (p2.y - p1.y) ** 2)


def vertical_overlap(r1: Rect, r2: Rect) -> float:
    """
    Calculate vertical overlap ratio between two rectangles.
    
    The ratio is calculated relative to the smaller rectangle's height.
    
    Args:
        r1: First rectangle
        r2: Second rectangle
        
    Returns:
        Overlap ratio (0.0 to 1.0)
        
    Examples:
        >>> r1 = Rect(0, 0, 50, 100)
        >>> r2 = Rect(60, 25, 110, 75)
        >>> vertical_overlap(r1, r2)
        1.0
    """
    # Calculate vertical overlap
    overlap_top = max(r1.y0, r2.y0)
    overlap_bottom = min(r1.y1, r2.y1)
    
    if overlap_bottom <= overlap_top:
        return 0.0
    
    overlap_height = overlap_bottom - overlap_top
    
    # Use smaller rectangle's height for ratio
    min_height = min(r1.height, r2.height)
    
    if min_height <= 0:
        return 0.0
    
    return min(1.0, overlap_height / min_height)


def horizontal_overlap(r1: Rect, r2: Rect) -> float:
    """
    Calculate horizontal overlap ratio between two rectangles.
    
    The ratio is calculated relative to the smaller rectangle's width.
    
    Args:
        r1: First rectangle
        r2: Second rectangle
        
    Returns:
        Overlap ratio (0.0 to 1.0)
        
    Examples:
        >>> r1 = Rect(0, 0, 100, 50)
        >>> r2 = Rect(50, 60, 150, 110)
        >>> horizontal_overlap(r1, r2)
        0.5
    """
    # Calculate horizontal overlap
    overlap_left = max(r1.x0, r2.x0)
    overlap_right = min(r1.x1, r2.x1)
    
    if overlap_right <= overlap_left:
        return 0.0
    
    overlap_width = overlap_right - overlap_left
    
    # Use smaller rectangle's width for ratio
    min_width = min(r1.width, r2.width)
    
    if min_width <= 0:
        return 0.0
    
    return min(1.0, overlap_width / min_width)
