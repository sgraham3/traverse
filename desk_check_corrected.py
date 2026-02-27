import math
from esri_traverse import (
    bearing_to_azimuth,
    DirectionType,
    DirectionUnits,
    _parse_angle_string,
    _parse_quadrant_bearing,
)


# Re-implement the necessary geometry classes and functions from QGIS for this test
class QgsPointXY:
    def __init__(self, x, y):
        self._x = x
        self._y = y

    def x(self):
        return self._x

    def y(self):
        return self._y

    def __repr__(self):
        return f"QgsPointXY({self._x:.6f}, {self._y:.6f})"


def calculate_nc_chord_curve(start_point, chord_azimuth_deg, chord_length, radius):
    """A correct geometric implementation for finding an arc from its chord."""

    # 1. Find Chord End Point (P2)
    chord_az_rad = math.radians(chord_azimuth_deg)
    p2_x = start_point.x() + chord_length * math.sin(chord_az_rad)
    p2_y = start_point.y() + chord_length * math.cos(chord_az_rad)
    p2 = QgsPointXY(p2_x, p2_y)

    # 2. Find the Circle's Center (C)
    half_chord = chord_length / 2.0
    if abs(radius) < half_chord:
        raise ValueError("Radius cannot be smaller than half chord length.")

    # Distance from chord midpoint to center
    h = math.sqrt(radius**2 - half_chord**2)

    # Midpoint of chord
    mid_x = (start_point.x() + p2.x()) / 2.0
    mid_y = (start_point.y() + p2.y()) / 2.0

    # Direction from midpoint to center (perpendicular to chord)
    # Right turn (+R) is +90deg from chord azimuth, Left turn (-R) is -90deg
    perp_az_rad = chord_az_rad + math.copysign(math.pi / 2, radius)

    # Center point
    center_x = mid_x + h * math.sin(perp_az_rad)
    center_y = mid_y + h * math.cos(perp_az_rad)

    # 3. Generate the Arc
    start_angle_rad = math.atan2(start_point.y() - center_y, start_point.x() - center_x)
    end_angle_rad = math.atan2(p2.y() - center_y, p2.x() - center_x)

    # Correct the sweep direction
    if radius > 0:  # Right turn, sweep is CW (angle decreases)
        while end_angle_rad > start_angle_rad:
            end_angle_rad -= 2 * math.pi
    else:  # Left turn, sweep is CCW (angle increases)
        while end_angle_rad < start_angle_rad:
            end_angle_rad += 2 * math.pi

    # The end point calculated from this sweep is the true end of the segment
    final_end_x = center_x + abs(radius) * math.cos(end_angle_rad)
    final_end_y = center_y + abs(radius) * math.sin(end_angle_rad)
    end_point = QgsPointXY(final_end_x, final_end_y)

    # 4. Calculate Exit Tangent
    # The exit tangent is perpendicular to the radial line at the arc's end point.
    radial_at_end_rad = end_angle_rad
    # For right turn (+R), tangent is CW from radial (-pi/2). For left turn (-R), tangent is CCW (+pi/2).
    exit_tangent_rad = radial_at_end_rad - math.copysign(math.pi / 2, radius)

    exit_azimuth_deg = (90 - math.degrees(exit_tangent_rad) + 360) % 360

    return end_point, exit_azimuth_deg


def calculate_line(start_point, azimuth_deg, distance):
    azimuth_rad = math.radians(azimuth_deg)
    dx = distance * math.sin(azimuth_rad)
    dy = distance * math.cos(azimuth_rad)
    end_point = QgsPointXY(start_point.x() + dx, start_point.y() + dy)
    return end_point, azimuth_deg


# --- Main Desk Check ---
start_point = QgsPointXY(348.710271, -296.428509)
last_azimuth = None
current_point = start_point

print("--- Traverse Calculation Desk Check (Corrected) ---")
print(f"Start Point: {current_point}\\n")

# 1. DD S87-58-48E 197.000000
print("1. DD S87-58-48E 197.0")
az = bearing_to_azimuth("S87-58-48E", DirectionType.QB, DirectionUnits.DMS)
current_point, last_azimuth = calculate_line(current_point, az, 197.0)
print(f"   End Point: {current_point}")
print(f"   Exit Azimuth: {last_azimuth:.6f}\\n")

# 2. NC A 222.95 D 17.27 C S7-32-15W L
print("2. NC A 222.95 D 17.27 C S7-32-15W L")
chord_az = bearing_to_azimuth("S7-32-15W", DirectionType.QB, DirectionUnits.DMS)
arc_len = 222.95
central_angle = 17.27
radius = -(arc_len / math.radians(central_angle))  # Negative for L
chord_len = 2 * abs(radius) * math.sin(math.radians(central_angle) / 2)
current_point, last_azimuth = calculate_nc_chord_curve(
    current_point, chord_az, chord_len, radius
)
print(f"   Radius: {radius:.6f}, Chord Length: {chord_len:.6f}")
print(f"   End Point: {current_point}")
print(f"   Exit Azimuth: {last_azimuth:.6f}\\n")

# 3. DD S1-5-48E 5.69
print("3. DD S1-5-48E 5.69")
az2 = bearing_to_azimuth("S1-5-48E", DirectionType.QB, DirectionUnits.DMS)
current_point, last_azimuth = calculate_line(current_point, az2, 5.69)
print(f"   End Point: {current_point}")
print(f"   Exit Azimuth: {last_azimuth:.6f}\\n")

# 4. DD S86-0-0W 173.70
print("4. DD S86-0-0W 173.70")
az3 = bearing_to_azimuth("S86-0-0W", DirectionType.QB, DirectionUnits.DMS)
current_point, last_azimuth = calculate_line(current_point, az3, 173.70)
print(f"   End Point: {current_point}")
print(f"   Exit Azimuth: {last_azimuth:.6f}\\n")

# 5. DD N1-16-12E 245.00
print("5. DD N1-16-12E 245.00")
az4 = bearing_to_azimuth("N1-16-12E", DirectionType.QB, DirectionUnits.DMS)
current_point, last_azimuth = calculate_line(current_point, az4, 245.00)
print(f"   End Point: {current_point}")
print(f"   Exit Azimuth: {last_azimuth:.6f}\\n")

print("--- End of Calculations ---")
print(f"Final Calculated Point: {current_point}")
print(f"Original Start Point:   {start_point}")
misclose_dist = math.sqrt(
    (current_point.x() - start_point.x()) ** 2
    + (current_point.y() - start_point.y()) ** 2
)
print(f"Misclosure Distance: {misclose_dist:.6f}")
