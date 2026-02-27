"""
Esri ArcGIS Pro traverse file format support.

Handles parsing and exporting traverse files in the standard Esri format with
support for DT (direction type), DU (direction units), DD (direction-distance),
AD (angle-distance), TC (tangent curve), and NC (nontangent curve) courses.

Reference: https://pro.arcgis.com/en/pro-app/latest/help/editing/traverse-file-format.htm
"""

import math
from enum import Enum
from dataclasses import dataclass
from typing import List, Optional, Tuple


class DirectionType(Enum):
    """Direction type for traverse courses."""

    QB = "QB"  # Quadrant bearing (e.g., N45-30-15E)
    NA = "NA"  # North azimuth (e.g., 45.50)
    SA = "SA"  # South azimuth (e.g., 45.50)
    P = "P"  # Polar


class DirectionUnits(Enum):
    """Units for direction and angle measurements."""

    DD = "DD"  # Decimal degrees
    DMS = "DMS"  # Degrees/Minutes/Seconds
    R = "R"  # Radians
    G = "G"  # Gradians/Gons


@dataclass
class TraverseCourse:
    """Represents a single course in a traverse."""

    course_type: str  # 'DD', 'AD', 'TC', 'NC'
    direction: Optional[str] = None  # Direction string (e.g., 'N45-30-15E' or '45.50')
    distance: Optional[float] = None  # Distance for DD/AD courses
    angle_offset: Optional[float] = None  # Angle offset for AD courses

    # Curve parameters
    curve_measure_type: Optional[str] = None  # 'D', 'A', 'C', 'R'
    curve_measure_value: Optional[float] = None
    curve_angle_type: Optional[str] = (
        None  # 'D', 'A', 'C', 'R' for TC; 'D', 'A', 'C', 'R' for NC
    )
    curve_angle_value: Optional[float] = None
    curve_direction: Optional[str] = None  # For NC: 'C', 'R', or 'T'
    curve_direction_value: Optional[str] = None  # Direction for NC nontangent curves
    curve_turn: str = "R"  # 'L' or 'R'


class EsriTraverseParser:
    """Parses Esri traverse files."""

    def __init__(self):
        self.direction_type: DirectionType = DirectionType.QB
        self.direction_units: DirectionUnits = DirectionUnits.DMS
        self.start_point: Optional[Tuple[float, float]] = None
        self.end_point: Optional[Tuple[float, float]] = None
        self.courses: List[TraverseCourse] = []
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def parse_file(self, file_path: str) -> bool:
        """
        Parse an Esri traverse file.

        Args:
            file_path: Path to the traverse file

        Returns:
            True if parsing succeeded, False otherwise
        """
        try:
            with open(file_path, "r") as f:
                lines = f.readlines()

            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                self._parse_line(line, line_num)

            return len(self.errors) == 0
        except FileNotFoundError:
            self.errors.append(f"File not found: {file_path}")
            return False
        except Exception as e:
            self.errors.append(f"Error reading file: {e}")
            return False

    def _parse_line(self, line: str, line_num: int) -> None:
        """Parse a single line from the traverse file."""
        parts = line.split()
        if not parts:
            return

        line_type = parts[0].upper()

        if line_type == "DT":
            self._parse_dt(parts, line_num)
        elif line_type == "DU":
            self._parse_du(parts, line_num)
        elif line_type == "SP":
            self._parse_sp(parts, line_num)
        elif line_type == "EP":
            self._parse_ep(parts, line_num)
        elif line_type == "DD":
            self._parse_dd(parts, line_num)
        elif line_type == "AD":
            self._parse_ad(parts, line_num)
        elif line_type == "TC":
            self._parse_tc(parts, line_num)
        elif line_type == "NC":
            self._parse_nc(parts, line_num)
        elif line_type == "CV":
            # Legacy format - skip silently
            self.warnings.append(
                f"Line {line_num}: CV (legacy format) is not supported. Use DD for straight lines or TC/NC for curves."
            )
        else:
            self.warnings.append(
                f"Line {line_num}: Unrecognized course type '{line_type}'"
            )

    def _parse_dt(self, parts: List[str], line_num: int) -> None:
        """Parse direction type (DT) line."""
        if len(parts) < 2:
            self.errors.append(f"Line {line_num}: DT requires a direction type value")
            return

        dt_value = parts[1].upper()
        try:
            self.direction_type = DirectionType[dt_value]
        except KeyError:
            self.errors.append(
                f"Line {line_num}: Invalid direction type '{dt_value}'. Valid: QB, NA, SA, P"
            )

    def _parse_du(self, parts: List[str], line_num: int) -> None:
        """Parse direction units (DU) line."""
        if len(parts) < 2:
            self.errors.append(f"Line {line_num}: DU requires a units value")
            return

        du_value = parts[1].upper()
        try:
            self.direction_units = DirectionUnits[du_value]
        except KeyError:
            self.errors.append(
                f"Line {line_num}: Invalid direction units '{du_value}'. Valid: DD, DMS, R, G"
            )

    def _parse_sp(self, parts: List[str], line_num: int) -> None:
        """Parse start point (SP) line."""
        if len(parts) < 3:
            self.errors.append(f"Line {line_num}: SP requires x and y coordinates")
            return

        try:
            x = float(parts[1])
            y = float(parts[2])
            self.start_point = (x, y)
        except ValueError:
            self.errors.append(f"Line {line_num}: SP has invalid numeric values")

    def _parse_ep(self, parts: List[str], line_num: int) -> None:
        """Parse end point (EP) line."""
        if len(parts) < 3:
            self.errors.append(f"Line {line_num}: EP requires x and y coordinates")
            return

        try:
            x = float(parts[1])
            y = float(parts[2])
            self.end_point = (x, y)
        except ValueError:
            self.errors.append(f"Line {line_num}: EP has invalid numeric values")

    def _parse_dd(self, parts: List[str], line_num: int) -> None:
        """Parse direction-distance (DD) course."""
        if len(parts) < 3:
            self.errors.append(f"Line {line_num}: DD requires direction and distance")
            return

        try:
            direction = parts[1]
            distance = float(parts[2])

            course = TraverseCourse(
                course_type="DD", direction=direction, distance=distance
            )
            self.courses.append(course)
        except ValueError:
            self.errors.append(f"Line {line_num}: DD has invalid distance value")

    def _parse_ad(self, parts: List[str], line_num: int) -> None:
        """Parse angle-distance (AD) course."""
        if len(self.courses) == 0:
            self.errors.append(f"Line {line_num}: AD cannot be the first course")
            return

        if len(parts) < 3:
            self.errors.append(f"Line {line_num}: AD requires angle and distance")
            return

        try:
            angle = self._parse_angle(parts[1])
            distance = float(parts[2])

            course = TraverseCourse(
                course_type="AD", angle_offset=angle, distance=distance
            )
            self.courses.append(course)
        except ValueError as e:
            self.errors.append(f"Line {line_num}: AD parsing error: {e}")

    def _parse_tc(self, parts: List[str], line_num: int) -> None:
        """Parse tangent curve (TC) course."""
        if len(self.courses) == 0:
            self.errors.append(f"Line {line_num}: TC cannot be the first course")
            return

        if len(parts) < 5:
            self.errors.append(
                f"Line {line_num}: TC requires measure type, value, angle type, angle value, and turn direction"
            )
            return

        try:
            measure_type = parts[1].upper()
            measure_value = float(parts[2])
            angle_type = parts[3].upper()
            angle_value = self._parse_angle(parts[4])
            turn = parts[5].upper() if len(parts) > 5 else "R"

            if measure_type not in ["D", "A", "C", "R"]:
                self.errors.append(
                    f"Line {line_num}: TC measure type '{measure_type}' invalid. Valid: D, A, C, R"
                )
                return

            if angle_type not in ["D", "A", "C", "R"]:
                self.errors.append(
                    f"Line {line_num}: TC angle type '{angle_type}' invalid. Valid: D, A, C, R"
                )
                return

            if turn not in ["L", "R"]:
                self.errors.append(
                    f"Line {line_num}: TC turn direction '{turn}' invalid. Valid: L, R"
                )
                return

            course = TraverseCourse(
                course_type="TC",
                curve_measure_type=measure_type,
                curve_measure_value=measure_value,
                curve_angle_type=angle_type,
                curve_angle_value=angle_value,
                curve_turn=turn,
            )
            self.courses.append(course)
        except ValueError as e:
            self.errors.append(f"Line {line_num}: TC parsing error: {e}")

    def _parse_nc(self, parts: List[str], line_num: int) -> None:
        """Parse nontangent curve (NC) course."""
        if len(parts) < 7:
            self.errors.append(
                f"Line {line_num}: NC requires measure type, value, angle type, angle value, direction type, direction value, and turn direction"
            )
            return

        try:
            measure_type = parts[1].upper()
            measure_value = float(parts[2])
            angle_type = parts[3].upper()
            angle_value = self._parse_angle(parts[4])
            direction_type = parts[5].upper()
            direction_value = parts[6]
            turn = parts[7].upper() if len(parts) > 7 else "R"

            if measure_type not in ["D", "A", "C", "R"]:
                self.errors.append(
                    f"Line {line_num}: NC measure type '{measure_type}' invalid. Valid: D, A, C, R"
                )
                return

            if angle_type not in ["D", "A", "C", "R"]:
                self.errors.append(
                    f"Line {line_num}: NC angle type '{angle_type}' invalid. Valid: D, A, C, R"
                )
                return

            if direction_type not in ["C", "R", "T"]:
                self.errors.append(
                    f"Line {line_num}: NC direction type '{direction_type}' invalid. Valid: C, R, T"
                )
                return

            if turn not in ["L", "R"]:
                self.errors.append(
                    f"Line {line_num}: NC turn direction '{turn}' invalid. Valid: L, R"
                )
                return

            course = TraverseCourse(
                course_type="NC",
                curve_measure_type=measure_type,
                curve_measure_value=measure_value,
                curve_angle_type=angle_type,
                curve_angle_value=angle_value,
                curve_direction=direction_type,
                curve_direction_value=direction_value,
                curve_turn=turn,
            )
            self.courses.append(course)
        except ValueError as e:
            self.errors.append(f"Line {line_num}: NC parsing error: {e}")

    def _parse_angle(self, angle_str: str) -> float:
        """
        Parse an angle string based on the current direction units.

        Args:
            angle_str: Angle string (e.g., '45-30-15' for DMS, '45.50' for DD)

        Returns:
            Angle in decimal degrees
        """
        angle_str = angle_str.strip()

        if self.direction_units == DirectionUnits.DMS:
            try:
                # First, try to parse as strict DMS
                return self._parse_dms(angle_str)
            except ValueError:
                # If DMS fails, try to parse as a float (decimal degrees) as a fallback
                try:
                    angle_val = float(angle_str)
                    self.warnings.append(
                        f"Expected DMS format but received decimal value '{angle_str}'. Treating as decimal degrees."
                    )
                    return angle_val
                except ValueError:
                    # If it's not valid DMS and not a valid float, raise the original format error
                    raise ValueError(
                        f"Invalid DMS format: '{angle_str}'. Expected DD-MM-SS or a valid decimal value."
                    )
        elif self.direction_units == DirectionUnits.DD:
            return float(angle_str)
        elif self.direction_units == DirectionUnits.R:
            return math.degrees(float(angle_str))
        elif self.direction_units == DirectionUnits.G:
            return float(angle_str) * 0.9  # Gradians to degrees
        else:
            raise ValueError(f"Unknown direction units: {self.direction_units}")

    def _parse_dms(self, dms_str: str) -> float:
        """
        Parse degrees-minutes-seconds string (e.g., '45-30-15', '90.5', '90-30').

        Returns:
            Decimal degrees
        """
        parts = dms_str.replace("-", " ").split()
        if not (1 <= len(parts) <= 3):
            raise ValueError(f"Invalid DMS format: {dms_str}. Expected 1 to 3 parts.")

        try:
            degrees = float(parts[0]) if len(parts) > 0 else 0.0
            minutes = float(parts[1]) if len(parts) > 1 else 0.0
            seconds = float(parts[2]) if len(parts) > 2 else 0.0

            # Handle negative degrees correctly
            if degrees < 0:
                return degrees - (minutes / 60.0) - (seconds / 3600.0)
            return degrees + (minutes / 60.0) + (seconds / 3600.0)
        except (ValueError, IndexError):
            raise ValueError(f"Invalid numeric values in DMS: {dms_str}")


def bearing_to_azimuth(
    bearing_str: str, direction_type: DirectionType, direction_units: DirectionUnits
) -> float:
    """
    Convert a bearing string to azimuth in decimal degrees.

    Args:
        bearing_str: Bearing string (e.g., 'N45-30-15E')
        direction_type: Type of direction (QB, NA, SA, P)
        direction_units: Units of direction (DD, DMS, R, G)

    Returns:
        Azimuth in decimal degrees (0-360, clockwise from North)
    """
    bearing_str = bearing_str.strip().upper()

    if direction_type == DirectionType.QB:
        return _parse_quadrant_bearing(bearing_str, direction_units)
    elif direction_type == DirectionType.NA:
        return _parse_angle_string(bearing_str, direction_units)
    elif direction_type == DirectionType.SA:
        # South azimuth: add 180 to convert to north azimuth
        sa = _parse_angle_string(bearing_str, direction_units)
        return (sa + 180) % 360
    elif direction_type == DirectionType.P:
        return _parse_angle_string(bearing_str, direction_units)
    else:
        raise ValueError(f"Unknown direction type: {direction_type}")


def _parse_quadrant_bearing(bearing_str: str, direction_units: DirectionUnits) -> float:
    """
    Parse quadrant bearing (e.g., 'N45-30-15E', 'S30W') to azimuth.

    Returns:
        Azimuth in decimal degrees
    """
    if len(bearing_str) < 2:
        raise ValueError("Bearing string too short")

    # First character: N or S (initial quadrant)
    initial = bearing_str[0]
    if initial not in ["N", "S"]:
        raise ValueError(f"Bearing must start with N or S, got {initial}")

    # Last character: E or W (closing quadrant)
    closing = bearing_str[-1]
    if closing not in ["E", "W"]:
        raise ValueError(f"Bearing must end with E or W, got {closing}")

    # Extract angle part (middle)
    angle_str = bearing_str[1:-1]
    angle_deg = _parse_angle_string(angle_str, direction_units)

    # Convert to azimuth based on quadrant
    if initial == "N" and closing == "E":
        return angle_deg
    elif initial == "N" and closing == "W":
        return 360 - angle_deg
    elif initial == "S" and closing == "E":
        return 180 - angle_deg
    elif initial == "S" and closing == "W":
        return 180 + angle_deg
    else:
        raise ValueError(f"Invalid bearing quadrant: {initial}...{closing}")


def _parse_angle_string(angle_str: str, direction_units: DirectionUnits) -> float:
    """
    Parse an angle string based on units.

    Returns:
        Angle in decimal degrees
    """
    if direction_units == DirectionUnits.DMS:
        parts = angle_str.split("-")
        if len(parts) != 3:
            raise ValueError(f"Invalid DMS format: {angle_str}")
        try:
            degrees = float(parts[0])
            minutes = float(parts[1])
            seconds = float(parts[2])
            return degrees + minutes / 60.0 + seconds / 3600.0
        except ValueError:
            raise ValueError(f"Invalid numeric in DMS: {angle_str}")
    elif direction_units == DirectionUnits.DD:
        return float(angle_str)
    elif direction_units == DirectionUnits.R:
        return math.degrees(float(angle_str))
    elif direction_units == DirectionUnits.G:
        return float(angle_str) * 0.9
    else:
        raise ValueError(f"Unknown direction units: {direction_units}")


def azimuth_to_bearing(
    azimuth_deg: float, direction_type: DirectionType, direction_units: DirectionUnits
) -> str:
    """
    Convert azimuth in decimal degrees to bearing string.

    Args:
        azimuth_deg: Azimuth in decimal degrees (0-360)
        direction_type: Type of direction to output
        direction_units: Units for the direction string

    Returns:
        Bearing string
    """
    azimuth_deg = azimuth_deg % 360

    if direction_type == DirectionType.QB:
        return _azimuth_to_quadrant_bearing(azimuth_deg, direction_units)
    elif direction_type == DirectionType.NA:
        return _format_angle(azimuth_deg, direction_units)
    elif direction_type == DirectionType.SA:
        sa = (azimuth_deg - 180) % 360
        return _format_angle(sa, direction_units)
    elif direction_type == DirectionType.P:
        return _format_angle(azimuth_deg, direction_units)
    else:
        raise ValueError(f"Unknown direction type: {direction_type}")


def _azimuth_to_quadrant_bearing(
    azimuth_deg: float, direction_units: DirectionUnits
) -> str:
    """Convert azimuth to quadrant bearing string."""
    azimuth_deg = azimuth_deg % 360

    if 0 <= azimuth_deg <= 90:
        initial = "N"
        closing = "E"
        angle = azimuth_deg
    elif 90 < azimuth_deg <= 180:
        initial = "S"
        closing = "E"
        angle = 180 - azimuth_deg
    elif 180 < azimuth_deg <= 270:
        initial = "S"
        closing = "W"
        angle = azimuth_deg - 180
    else:  # 270 < azimuth_deg < 360
        initial = "N"
        closing = "W"
        angle = 360 - azimuth_deg

    angle_str = _format_angle(angle, direction_units)
    return f"{initial}{angle_str}{closing}"


def _format_angle(angle_deg: float, direction_units: DirectionUnits) -> str:
    """Format an angle in decimal degrees to a string."""
    if direction_units == DirectionUnits.DD:
        return f"{angle_deg:.2f}"
    elif direction_units == DirectionUnits.DMS:
        deg = int(angle_deg)
        min_float = (angle_deg - deg) * 60
        minutes = int(min_float)
        seconds = (min_float - minutes) * 60
        return f"{deg}-{minutes}-{seconds:.2f}"
    elif direction_units == DirectionUnits.R:
        radians = math.radians(angle_deg)
        return f"{radians:.6f}"
    elif direction_units == DirectionUnits.G:
        gradians = angle_deg / 0.9
        return f"{gradians:.2f}"
    else:
        raise ValueError(f"Unknown direction units: {direction_units}")
