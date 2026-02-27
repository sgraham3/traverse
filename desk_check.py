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


# Calculations from traverse_dockwidget.py
def calculate_curve(start_point, azimuth_deg, radius, arc_length):
    tangent_math_rad = math.radians(90 - azimuth_deg)
    center_angle_rad = tangent_math_rad - math.copysign(math.pi / 2, radius)
    center_x = start_point.x() + abs(radius) * math.cos(center_angle_rad)
    center_y = start_point.y() + abs(radius) * math.sin(center_angle_rad)

    start_arc_angle = math.atan2(start_point.y() - center_y, start_point.x() - center_x)
    delta_angle_rad = arc_length / abs(radius)

    # Use negative radius for Left turn (add delta angle), positive for Right (subtract delta)
    # The sign of the radius determines the turn direction
    end_arc_angle = start_arc_angle - math.copysign(delta_angle_rad, radius)

    end_x = center_x + abs(radius) * math.cos(end_arc_angle)
    end_y = center_y + abs(radius) * math.sin(end_arc_angle)

    # Calculate exit tangent
    radial_angle_at_end = math.atan2(end_y - center_y, end_x - center_x)
    # The exit tangent is perpendicular to the radial line at the end of the curve
    exit_tangent_math_rad = radial_angle_at_end + math.copysign(math.pi / 2, radius)
    exit_azimuth_deg = (90 - math.degrees(exit_tangent_math_rad)) % 360
    if exit_azimuth_deg < 0:
        exit_azimuth_deg += 360

    return QgsPointXY(end_x, end_y), exit_azimuth_deg


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

print("--- Traverse Calculation Desk Check ---")
print(f"Start Point: {current_point}\\n")

# 1. DD S87-58-48E 197.000000
print("1. DD S87-58-48E 197.0")
az = bearing_to_azimuth("S87-58-48E", DirectionType.QB, DirectionUnits.DMS)
print(f"   Azimuth: {az:.6f}")
current_point, last_azimuth = calculate_line(current_point, az, 197.0)
print(f"   End Point: {current_point}")
print(f"   Exit Azimuth: {last_azimuth:.6f}\\n")


# 2. NC A 222.95 D 17.27 C S7-32-15W L
print("2. NC A 222.95 D 17.27 C S7-32-15W L")
# For a non-tangent curve, the azimuth is the chord bearing
az_nc = bearing_to_azimuth("S7-32-15W", DirectionType.QB, DirectionUnits.DMS)
print(f"   Chord Azimuth: {az_nc:.6f}")
arc_length_nc = 222.95
central_angle_nc = 17.27  # From the file, treated as DD
# Radius = (Arc Length) / (Central Angle in Radians)
radius_nc = arc_length_nc / math.radians(central_angle_nc)
# 'L' means left turn, so radius is negative
radius_nc = -radius_nc
print(f"   Radius: {radius_nc:.6f}")
# The direction of an NC is its CHORD bearing. The *drawing* logic needs the tangent.
# The issue might be that the chord direction is used as the initial tangent.
# Let's assume for now it's drawn as a tangent curve from the chord direction for this test.
current_point, last_azimuth = calculate_curve(
    current_point, az_nc, radius_nc, arc_length_nc
)
print(f"   End Point: {current_point}")
print(f"   Exit Azimuth: {last_azimuth:.6f}\\n")


# 3. DD S1-5-48E 5.690000
print("3. DD S1-5-48E 5.69")
az2 = bearing_to_azimuth("S1-5-48E", DirectionType.QB, DirectionUnits.DMS)
print(f"   Azimuth: {az2:.6f}")
current_point, last_azimuth = calculate_line(current_point, az2, 5.69)
print(f"   End Point: {current_point}")
print(f"   Exit Azimuth: {last_azimuth:.6f}\\n")


# 4. DD S86-0-0W 173.700000
print("4. DD S86-0-0W 173.70")
az3 = bearing_to_azimuth("S86-0-0W", DirectionType.QB, DirectionUnits.DMS)
print(f"   Azimuth: {az3:.6f}")
current_point, last_azimuth = calculate_line(current_point, az3, 173.70)
print(f"   End Point: {current_point}")
print(f"   Exit Azimuth: {last_azimuth:.6f}\\n")


# 5. DD N1-16-12E 245.000000
print("5. DD N1-16-12E 245.00")
az4 = bearing_to_azimuth("N1-16-12E", DirectionType.QB, DirectionUnits.DMS)
print(f"   Azimuth: {az4:.6f}")
current_point, last_azimuth = calculate_line(current_point, az4, 245.00)
print(f"   End Point: {current_point}")
print(f"   Exit Azimuth: {last_azimuth:.6f}\\n")

print("--- End of Calculations ---")
print(f"Final Calculated Point: {current_point}")
print(f"Expected Start Point:   {start_point}")
