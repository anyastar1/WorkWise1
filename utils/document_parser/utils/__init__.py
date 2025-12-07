"""Utility functions."""

from .color_utils import (
    hex_to_rgb,
    rgb_to_hex,
    int_to_hex,
    hex_to_int,
    color_distance,
    is_dark_color,
    normalize_color,
)
from .geometry import (
    Point,
    Rect,
    rects_overlap,
    rect_contains,
    rect_intersection,
    rect_union,
    point_in_rect,
    distance_between_points,
    vertical_overlap,
    horizontal_overlap,
)

__all__ = [
    # Color utils
    "hex_to_rgb",
    "rgb_to_hex",
    "int_to_hex",
    "hex_to_int",
    "color_distance",
    "is_dark_color",
    "normalize_color",
    # Geometry
    "Point",
    "Rect",
    "rects_overlap",
    "rect_contains",
    "rect_intersection",
    "rect_union",
    "point_in_rect",
    "distance_between_points",
    "vertical_overlap",
    "horizontal_overlap",
]
