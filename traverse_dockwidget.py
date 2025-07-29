import os
import math

from qgis.PyQt import QtGui, QtWidgets, uic
from qgis.PyQt.QtCore import pyqtSignal, Qt, QVariant # Import QVariant directly
from qgis.PyQt.QtGui import QIcon
from qgis.gui import QgsMapLayerComboBox, QgsMapToolEmitPoint
from qgis.core import QgsProject, QgsVectorLayer, QgsPointXY, QgsFeature, QgsGeometry, QgsFields, QgsField, QgsWkbTypes, QgsFeatureRequest
from qgis.core import QgsMapLayerProxyModel
from qgis.core import Qgis # Import Qgis for message levels


FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'traverse_dockwidget_base.ui'))

# Define a constant for curve approximation resolution
NUM_CURVE_SEGMENTS = 20 # Number of straight line segments to approximate a curve


class traverseDockWidget(QtWidgets.QDockWidget, FORM_CLASS):

    closingPlugin = pyqtSignal()

    def __init__(self, parent=None):
        """Constructor."""
        super(traverseDockWidget, self).__init__(parent)
        self.setupUi(self)

        self.iface = None
        self.canvas = None

        self.start_point = None
        self.closing_point = None
        self.current_map_tool = None # To keep track of active map tools for point selection
        self._first_trace_point = None # Used for the two-click digitizing of a segment

        # --- Connect UI elements to methods ---

        # Hamburger Button setup
        self.hamburgerButton.setMenu(self._create_hamburger_menu())
        self.hamburgerButton.clicked.connect(self.hamburgerButton.showMenu)

        # Map Layer ComboBox setup
        self.mapLayerComboBox.setFilters(QgsMapLayerProxyModel.VectorLayer)
        self.mapLayerComboBox.layerChanged.connect(self.on_layer_changed)

        # Toolbar Actions connections
        self.actionStart.triggered.connect(self.set_start_point)
        self.actionClose.triggered.connect(self.set_closing_point)
        # Connect actionTraceLines to activate the tracing tool
        self.actionTraceLines.triggered.connect(self.activate_trace_line_tool) 
        self.actionImport.triggered.connect(self.import_data) # Changed actionimport to actionImport
        self.actionExport.triggered.connect(self.export_data)

        # Connect the "Finish" button to the function that DRAWS lines from table to layer
        self.finishButton.clicked.connect(self.draw_traverse_from_table) 

        # Connect the "New" button (newButton) to clear the table and start fresh
        self.newButton.clicked.connect(self.clear_table_and_start_new)

        # Table Widget initialization
        self.tableWidget.setRowCount(0)
        self.tableWidget.setColumnWidth(0, 100) # Direction
        self.tableWidget.setColumnWidth(1, 100) # Distance
        self.tableWidget.setColumnWidth(2, 80)  # Radius
        self.tableWidget.setColumnWidth(3, 80)  # Arc Length

        # Connect cell click signal to add new row (if on last populated row)
        self.tableWidget.cellClicked.connect(self.on_table_cell_clicked)

        # --- Context Menu for Table Widget ---
        self.tableWidget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tableWidget.customContextMenuRequested.connect(self._show_table_context_menu)


    def _create_hamburger_menu(self):
        """Creates the menu for the hamburger button and adds actions."""
        menu = QtWidgets.QMenu(self)
        menu.addAction(self.actionImport) # Changed actionimport to actionImport
        menu.addAction(self.actionExport)
        return menu

    def set_qgis_interface(self, iface):
        """Sets the QGIS interface and map canvas objects.
           This method is called by the main plugin class (traverse.py).
        """
        self.iface = iface
        self.canvas = iface.mapCanvas()

    def set_start_point(self):
        """Activates a map tool to allow the user to click on the map
           and set the traverse start point.
        """
        if self.iface is None or self.canvas is None:
            self.iface.messageBar().pushCritical("Traverse Plugin", "QGIS interface or map canvas not initialized. Please restart QGIS or the plugin.")
            return

        self.iface.messageBar().pushMessage("Traverse Plugin", "Click on the map to set the START point of the traverse.", level=Qgis.Info)

        # Ensure any active trace tool is deactivated
        if self.current_map_tool:
            self.canvas.unsetMapTool(self.current_map_tool)
        self._first_trace_point = None # Reset trace digitizing state

        tool = QgsMapToolEmitPoint(self.canvas)
        tool.canvasClicked.connect(self._handle_start_point_click)
        self.canvas.setMapTool(tool)
        self.current_map_tool = tool

    def _handle_start_point_click(self, point):
        """Callback method for when the user clicks on the map to set the start point."""
        self.start_point = point
        self.iface.messageBar().pushMessage("Traverse Plugin", f"Start point set at: {self.start_point.toString()}", level=Qgis.Info)
        self.canvas.unsetMapTool(self.current_map_tool)
        self.current_map_tool = None


    def set_closing_point(self):
        """Activates a map tool to allow the user to click on the map
           and set the traverse closing point.
        """
        if self.iface is None or self.canvas is None:
            self.iface.messageBar().pushCritical("Traverse Plugin", "QGIS interface or map canvas not initialized. Please restart QGIS or the plugin.")
            return

        self.iface.messageBar().pushMessage("Traverse Plugin", "Click on the map to set the CLOSING point of the traverse.", level=Qgis.Info)

        # Ensure any active trace tool is deactivated
        if self.current_map_tool:
            self.canvas.unsetMapTool(self.current_map_tool)
        self._first_trace_point = None # Reset trace digitizing state

        tool = QgsMapToolEmitPoint(self.canvas)
        tool.canvasClicked.connect(self._handle_closing_point_click)
        self.canvas.setMapTool(tool)
        self.current_map_tool = tool

    def _handle_closing_point_click(self, point):
        """Callback method for when the user clicks on the map to set the closing point."""
        self.closing_point = point
        self.iface.messageBar().pushMessage("Traverse Plugin", f"Closing point set at: {self.closing_point.toString()}", level=Qgis.Info)
        self.canvas.unsetMapTool(self.current_map_tool)
        self.current_map_tool = None

    def activate_trace_line_tool(self):
        """
        Activates a map tool to allow the user to click on the map to digitize a new line segment.
        The first click sets the start, the second click sets the end, and the segment
        is added to the table. Allows for continuous digitizing.
        """
        if self.iface is None or self.canvas is None:
            self.iface.messageBar().pushCritical("Traverse Plugin", "QGIS interface or map canvas not initialized. Please restart QGIS or the plugin.")
            return

        # Ensure any other map tool is deactivated before starting trace
        if self.current_map_tool:
            self.canvas.unsetMapTool(self.current_map_tool)

        # Reset the first trace point for a new segment definition
        self._first_trace_point = None
        self.iface.messageBar().pushMessage("Traverse Plugin", "Click on the map to define the START of your new traverse segment.", level=Qgis.Info)

        tool = QgsMapToolEmitPoint(self.canvas)
        tool.canvasClicked.connect(self._handle_trace_point_click)
        self.canvas.setMapTool(tool)
        self.current_map_tool = tool

    def _handle_trace_point_click(self, clicked_point):
        """
        Callback method for when the user clicks on the map with the trace tool active.
        Handles two-click digitization of a segment.
        """
        if self.iface is None or self.canvas is None:
            return

        if self._first_trace_point is None:
            # This is the first click for a new segment
            self._first_trace_point = clicked_point
            self.iface.messageBar().pushMessage("Traverse Plugin", "First point set. Now click to define the END of the segment.", level=Qgis.Info)
            # Keep the tool active for the second click
        else:
            # This is the second click, define the segment
            start_segment_point = self._first_trace_point
            end_segment_point = clicked_point

            # Calculate distance
            distance = start_segment_point.distance(end_segment_point)
            
            # Calculate bearing (azimuth)
            dx = end_segment_point.x() - start_segment_point.x()
            dy = end_segment_point.y() - start_segment_point.y()
            
            azimuth_rad = math.atan2(dx, dy)
            azimuth_deg = math.degrees(azimuth_rad)
            
            if azimuth_deg < 0:
                azimuth_deg += 360

            # Add the new segment to the table
            self.add_traverse_segment(f"{azimuth_deg:.2f}°", distance, 0.0, 0.0) # Radius and Arc Length are 0 for straight lines
            
            # Update the global start_point for the traverse (used by "Finish" button)
            self.start_point = end_segment_point 
            
            # Set the _first_trace_point to the end of the current segment for continuous digitizing
            self._first_trace_point = end_segment_point
            
            self.iface.messageBar().pushMessage("Traverse Plugin", 
                                               f"Segment added. Bearing: {azimuth_deg:.2f}°, Distance: {distance:.3f}. Click to define the next segment.", 
                                               level=Qgis.Info)
            # Keep the tool active for continuous digitizing

    def _parse_bearing_to_azimuth(self, bearing_str):
        """
        Converts a bearing string (e.g., "N45-30-15E", "S60E", "NW") to an azimuth in decimal degrees.
        Returns the azimuth in degrees (0-360, clockwise from North).
        Raises ValueError for invalid formats.
        """
        bearing_str = bearing_str.strip().upper()

        if len(bearing_str) < 2:
            raise ValueError("Bearing string too short.")

        quadrant1 = bearing_str[0]
        quadrant2 = bearing_str[-1]
        
        # Handle cases like "N", "S", "E", "W"
        if len(bearing_str) == 1:
            if quadrant1 == 'N': return 0.0
            if quadrant1 == 'E': return 90.0
            if quadrant1 == 'S': return 180.0
            if quadrant1 == 'W': return 270.0

        # Handle cardinal/intercardinal without degrees like NE, NW, SE, SW
        if len(bearing_str) == 2 and quadrant2 in ['E', 'W']:
            if bearing_str == 'NE': return 45.0
            if bearing_str == 'SE': return 135.0
            if bearing_str == 'SW': return 225.0
            if bearing_str == 'NW': return 315.0

        degrees_part = bearing_str[1:-1]
        
        # Split degrees, minutes, seconds
        parts = []
        if '-' in degrees_part:
            parts = degrees_part.split('-')
        else: # Try to parse as decimal degrees if no hyphens
            try:
                deg = float(degrees_part)
                parts = [str(deg)]
            except ValueError:
                pass # Will be handled by the next check

        if not parts:
            raise ValueError(f"Could not parse degree/minute/second part: {degrees_part}")

        deg = float(parts[0])
        minutes = float(parts[1]) if len(parts) > 1 else 0.0
        seconds = float(parts[2]) if len(parts) > 2 else 0.0

        decimal_degrees = deg + (minutes / 60.0) + (seconds / 3600.0)

        azimuth = 0.0
        if quadrant1 == 'N' and quadrant2 == 'E':
            azimuth = decimal_degrees
        elif quadrant1 == 'S' and quadrant2 == 'E':
            azimuth = 180.0 - decimal_degrees
        elif quadrant1 == 'S' and quadrant2 == 'W':
            azimuth = 180.0 + decimal_degrees
        elif quadrant1 == 'N' and quadrant2 == 'W':
            azimuth = 360.0 - decimal_degrees
        elif quadrant1 == 'N' and quadrant2 == 'S': # Cases like N0-0-0S, this is usually 0 or 180
            if decimal_degrees == 0:
                azimuth = 0.0 # North
            else:
                raise ValueError("N/S followed by S/N not standard bearing.")
        elif quadrant1 == 'E' or quadrant1 == 'W':
            raise ValueError("Bearing should start with N or S.")
        else:
            raise ValueError(f"Invalid quadrant specification: {quadrant1}{quadrant2}")


        return azimuth % 360.0 # Ensure it's between 0 and 360

    def _convert_azimuth_to_bearing_string(self, azimuth_deg):
        """
        Converts an azimuth in decimal degrees (0-360) to a bearing string (e.g., N45-30-15E).
        """
        azimuth_deg = azimuth_deg % 360  # Ensure 0-360

        # Handle cardinal directions first with a small tolerance for floating point
        if abs(azimuth_deg - 0) < 0.0001 or abs(azimuth_deg - 360) < 0.0001: return "N"
        if abs(azimuth_deg - 90) < 0.0001: return "E"
        if abs(azimuth_deg - 180) < 0.0001: return "S"
        if abs(azimuth_deg - 270) < 0.0001: return "W"

        quadrant_prefix = ''
        quadrant_suffix = ''
        bearing_value = 0.0

        if 0 < azimuth_deg < 90:
            quadrant_prefix = 'N'
            quadrant_suffix = 'E'
            bearing_value = azimuth_deg
        elif 90 < azimuth_deg < 180:
            quadrant_prefix = 'S'
            quadrant_suffix = 'E'
            bearing_value = 180 - azimuth_deg
        elif 180 < azimuth_deg < 270:
            quadrant_prefix = 'S'
            quadrant_suffix = 'W'
            bearing_value = azimuth_deg - 180
        elif 270 < azimuth_deg < 360:
            quadrant_prefix = 'N'
            quadrant_suffix = 'W'
            bearing_value = 360 - azimuth_deg
        else:
            # Should not happen if cardinal directions are handled, but as a fallback
            return f"{azimuth_deg:.2f}" # Fallback to plain decimal degrees if not within standard quadrants

        degrees = int(bearing_value)
        minutes_float = (bearing_value - degrees) * 60
        minutes = int(minutes_float)
        seconds = round((minutes_float - minutes) * 60, 0) # Round to nearest second

        # Adjust for rounding up, e.g., 59.99 seconds becomes 60
        if seconds >= 60:
            minutes += 1
            seconds = 0
        if minutes >= 60:
            degrees += 1
            minutes = 0
            # If degrees goes to 90 due to rounding, re-check for cardinal directions
            if degrees == 90:
                 if quadrant_prefix == 'N' and quadrant_suffix == 'E': return "E"
                 if quadrant_prefix == 'S' and quadrant_suffix == 'E': return "S"
                 if quadrant_prefix == 'S' and quadrant_suffix == 'W': return "W"
                 if quadrant_prefix == 'N' and quadrant_suffix == 'W': return "N"

        return f"{quadrant_prefix}{degrees}-{minutes}-{int(seconds)}{quadrant_suffix}"


    def draw_traverse_from_table(self):
        """
        Draws traverse lines on the selected layer based on the data in the table widget.
        """
        if self.iface is None or self.canvas is None:
            self.iface.messageBar().pushCritical("Traverse Plugin", "QGIS interface or map canvas not initialized. Please restart QGIS or the plugin.")
            return

        selected_layer = self.mapLayerComboBox.currentLayer()
        if selected_layer is None:
            self.iface.messageBar().pushWarning("Traverse Plugin", "Please select a layer from the combo box to draw on.")
            return

        if not isinstance(selected_layer, QgsVectorLayer):
            self.iface.messageBar().pushWarning("Traverse Plugin", "Selected layer is not a vector layer. Please select a vector layer.")
            return
        
        # Check if the layer is a line layer
        if not (selected_layer.wkbType() == QgsWkbTypes.LineString or selected_layer.wkbType() == QgsWkbTypes.MultiLineString):
            self.iface.messageBar().pushWarning("Traverse Plugin", f"Selected layer '{selected_layer.name()}' is not a line layer. Cannot draw traverse lines on it.")
            return

        # Check if layer is editable and offer to toggle
        is_editable_originally = selected_layer.isEditable()
        if not is_editable_originally:
            reply = QtWidgets.QMessageBox.question(self, 'Toggle Editing', 
                                                   f"Layer '{selected_layer.name()}' is not in editing mode. Do you want to enable editing?",
                                                   QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
            if reply == QtWidgets.QMessageBox.Yes:
                selected_layer.startEditing()
                # Update QGIS UI to show editing mode if it wasn't already
                if not self.iface.actionToggleEditing().isChecked():
                    self.iface.actionToggleEditing().trigger() 
            else:
                self.iface.messageBar().pushWarning("Traverse Plugin", "Layer is not in editing mode. Cannot draw traverse lines.")
                return
        
        if self.start_point is None:
            self.iface.messageBar().pushWarning("Traverse Plugin", "Please set a START point before drawing traverse lines.")
            # If we started editing for this operation, roll back
            if not is_editable_originally:
                selected_layer.rollBack()
                if self.iface.actionToggleEditing().isChecked():
                    self.iface.actionToggleEditing().trigger()
            return

        if self.tableWidget.rowCount() == 0:
            self.iface.messageBar().pushWarning("Traverse Plugin", "The traverse table is empty. Add segments to draw.")
            # If we started editing for this operation, roll back
            if not is_editable_originally:
                selected_layer.rollBack()
                if self.iface.actionToggleEditing().isChecked():
                    self.iface.actionToggleEditing().trigger()
            return

        current_point = self.start_point
        features_to_add = []
        
        # Ensure fields exist for attributes if we want to populate them
        required_fields_info = [
            ("segment_id", QVariant.Int),
            ("direction", QVariant.String),
            ("distance", QVariant.Double),
            ("radius", QVariant.Double),
            ("arc_length", QVariant.Double)
        ]
        
        prov = selected_layer.dataProvider()
        fields_to_add_to_layer = QgsFields()
        for field_name, field_type in required_fields_info:
            if selected_layer.fields().indexOf(field_name) == -1:
                fields_to_add_to_layer.append(QgsField(field_name, field_type))
        
        if fields_to_add_to_layer.count() > 0:
            if not prov.addAttributes(fields_to_add_to_layer):
                self.iface.messageBar().pushCritical("Traverse Plugin", "Failed to add required fields to the layer.")
                if not is_editable_originally: # Only rollback if we started editing
                    selected_layer.rollBack()
                    if self.iface.actionToggleEditing().isChecked():
                        self.iface.actionToggleEditing().trigger()
                return
            selected_layer.updateFields()
            self.iface.messageBar().pushMessage("Traverse Plugin", f"Added missing fields to layer '{selected_layer.name()}'.", level=Qgis.Info)

        # Initialize last_segment_exit_azimuth. This will store the exit tangent direction of the *previously drawn* segment.
        last_segment_exit_azimuth = None 

        try:
            for row_idx in range(self.tableWidget.rowCount()):
                direction_item = self.tableWidget.item(row_idx, 0)
                distance_item = self.tableWidget.item(row_idx, 1)
                radius_item = self.tableWidget.item(row_idx, 2)
                arc_length_item = self.tableWidget.item(row_idx, 3)

                # If any key item is missing or empty, skip this row
                if not (direction_item and distance_item and distance_item.text().strip()): # Direction can be empty for tangent
                    self.iface.messageBar().pushWarning("Traverse Plugin", f"Skipping incomplete row {row_idx + 1} in table for drawing. (Missing Distance or invalid Direction)")
                    continue

                segment_tangent_azimuth_deg = 0.0
                direction_str_from_table = direction_item.text().strip() if direction_item else "" # Handle case where item might be None

                # Determine the azimuth for the START of the current segment
                if row_idx == 0: # First segment always uses its own explicit direction
                    if not direction_str_from_table: # First segment needs an explicit direction
                         self.iface.messageBar().pushWarning("Traverse Plugin", f"Row {row_idx + 1}: First segment must have an explicit direction. Skipping segment.")
                         continue
                    try:
                        cleaned_direction_str = direction_str_from_table.replace('°', '').strip()
                        segment_tangent_azimuth_deg = float(cleaned_direction_str) 
                    except ValueError:
                        try:
                            segment_tangent_azimuth_deg = self._parse_bearing_to_azimuth(direction_str_from_table) 
                        except ValueError as ve:
                            self.iface.messageBar().pushWarning("Traverse Plugin", f"Row {row_idx + 1}: Invalid direction format '{direction_str_from_table}'. Expected decimal degrees (e.g., '45.00') or bearing (e.g., 'N45-30-15E'). Skipping segment. Error: {ve}")
                            continue
                elif direction_str_from_table == "*" or not direction_str_from_table: # Tangent to previous segment's exit
                    if last_segment_exit_azimuth is None:
                        self.iface.messageBar().pushWarning("Traverse Plugin", f"Row {row_idx + 1}: Cannot determine tangent direction. Previous segment had no valid exit direction. Please specify direction explicitly for this row or ensure previous row is valid.")
                        continue
                    segment_tangent_azimuth_deg = last_segment_exit_azimuth
                    self.iface.messageBar().pushMessage("Traverse Plugin", f"Row {row_idx + 1}: Using tangent direction from previous segment ({segment_tangent_azimuth_deg:.2f}°).", level=Qgis.Info)
                else: # Nontangent, explicit direction given
                    try:
                        cleaned_direction_str = direction_str_from_table.replace('°', '').strip()
                        segment_tangent_azimuth_deg = float(cleaned_direction_str) 
                    except ValueError:
                        try:
                            segment_tangent_azimuth_deg = self._parse_bearing_to_azimuth(direction_str_from_table) 
                        except ValueError as ve:
                            self.iface.messageBar().pushWarning("Traverse Plugin", f"Row {row_idx + 1}: Invalid direction format '{direction_str_from_table}'. Expected decimal degrees (e.g., '45.00') or bearing (e.g., 'N45-30-15E'). Skipping segment. Error: {ve}")
                            continue
                
                # Ensure azimuth is within 0-360 range
                segment_tangent_azimuth_deg = segment_tangent_azimuth_deg % 360
                if segment_tangent_azimuth_deg < 0:
                    segment_tangent_azimuth_deg += 360

                try:
                    distance = float(distance_item.text())
                    radius = float(radius_item.text()) if (radius_item and radius_item.text().strip()) else 0.0
                    arc_length = float(arc_length_item.text()) if (arc_length_item and arc_length_item.text().strip()) else 0.0
                    
                    polyline_points = []
                    polyline_points.append(current_point) # Start of current segment

                    next_point = current_point # Default to no movement, will be updated

                    if radius != 0.0 and arc_length != 0.0:
                        # --- Curve Calculation ---
                        # Azimuth is clockwise from North (Y-axis)
                        # Standard math angle is counter-clockwise from East (X-axis)
                        
                        # Convert segment's STARTING tangent azimuth to standard math radians 
                        # for the tangent direction at current_point
                        tangent_math_rad = math.radians(90 - segment_tangent_azimuth_deg) 

                        # Calculate center of the circle
                        # Center is perpendicular to tangent, 'radius' distance away.
                        # If radius > 0 (right turn), center is 90 deg CLOCKWISE from tangent (tangent_math_rad - PI/2)
                        # If radius < 0 (left turn), center is 90 deg COUNTER-CLOCKWISE from tangent (tangent_math_rad + PI/2)
                        # This can be achieved with: center_angle_rad = tangent_math_rad - math.copysign(math.pi / 2, radius)
                        # Example: if radius is +50 (right turn), copysign is +PI/2, so tangent_math_rad - PI/2 (clockwise)
                        # Example: if radius is -50 (left turn), copysign is -PI/2, so tangent_math_rad - (-PI/2) = tangent_math_rad + PI/2 (counter-clockwise)
                        
                        center_angle_rad = tangent_math_rad - math.copysign(math.pi / 2, radius)
                        
                        center_x = current_point.x() + abs(radius) * math.cos(center_angle_rad)
                        center_y = current_point.y() + abs(radius) * math.sin(center_angle_rad)
                        center_point = QgsPointXY(center_x, center_y)

                        # Calculate start angle of the arc relative to the center
                        start_arc_angle = math.atan2(current_point.y() - center_y, current_point.x() - center_x)

                        # Calculate delta angle (central angle)
                        delta_angle_rad = arc_length / abs(radius)
                        
                        # Determine end angle based on direction of curve (sign of radius)
                        # If radius > 0 (Right turn), sweep is clockwise (subtract delta_angle_rad)
                        # If radius < 0 (Left turn), sweep is counter-clockwise (add delta_angle_rad)
                        # This can be achieved with: end_arc_angle = start_arc_angle + math.copysign(delta_angle_rad, -radius) 
                        # Example: if radius is +50 (right turn), copysign(-val, -50) is -val, so start_arc_angle - delta_angle_rad (clockwise)
                        # Example: if radius is -50 (left turn), copysign(-val, 50) is +val, so start_arc_angle + delta_angle_rad (counter-clockwise)
                        end_arc_angle = start_arc_angle + math.copysign(delta_angle_rad, -radius) 

                        # Ensure sweep is in correct direction and handle wrapping around 2*pi
                        if radius > 0: # Right turn, clockwise sweep (angles should decrease)
                            # If end_arc_angle is numerically greater than start_arc_angle, it means we wrapped around 0/2pi
                            while end_arc_angle > start_arc_angle:
                                end_arc_angle -= 2 * math.pi
                            step_angle = (end_arc_angle - start_arc_angle) / NUM_CURVE_SEGMENTS
                        else: # Left turn, counter-clockwise sweep (angles should increase)
                            # If end_arc_angle is numerically less than start_arc_angle, it means we wrapped around 0/2pi
                            while end_arc_angle < start_arc_angle:
                                end_arc_angle += 2 * math.pi
                            step_angle = (end_arc_angle - start_arc_angle) / NUM_CURVE_SEGMENTS

                        # Generate intermediate points
                        for i in range(1, NUM_CURVE_SEGMENTS + 1):
                            interp_angle = start_arc_angle + i * step_angle
                            px = center_x + abs(radius) * math.cos(interp_angle)
                            py = center_y + abs(radius) * math.sin(interp_angle)
                            polyline_points.append(QgsPointXY(px, py))
                        
                        next_point = polyline_points[-1] # Last point of the arc is the end of the segment
                        self.iface.messageBar().pushMessage("Traverse Plugin", f"Row {row_idx + 1}: Drawn as curve (Radius: {radius:.3f}, Arc Length: {arc_length:.3f}).", level=Qgis.Info)

                        # Calculate exit tangent for the current curve for the next segment's 'tangent to previous'
                        radial_angle_at_end = math.atan2(next_point.y() - center_point.y(), next_point.x() - center_point.x())
                        exit_tangent_math_rad = 0.0
                        if radius > 0: # Right turn, tangent is 90 deg CLOCKWISE from radial at end point
                            exit_tangent_math_rad = radial_angle_at_end + math.pi / 2
                        else: # Left turn, tangent is 90 deg COUNTER-CLOCKWISE from radial at end point
                            exit_tangent_math_rad = radial_angle_at_end - math.pi / 2
                            
                        # Convert this math angle back to survey azimuth (0-360)
                        exit_tangent_azimuth_deg = (90 - math.degrees(exit_tangent_math_rad)) % 360
                        if exit_tangent_azimuth_deg < 0: # Ensure positive 0-360
                            exit_tangent_azimuth_deg += 360
                        last_segment_exit_azimuth = exit_tangent_azimuth_deg

                    else: # Straight line
                        # Use the determined segment_tangent_azimuth_deg for straight line
                        azimuth_rad = math.radians(segment_tangent_azimuth_deg)
                        dx = distance * math.sin(azimuth_rad)
                        dy = distance * math.cos(azimuth_rad)
                        next_point = QgsPointXY(current_point.x() + dx, current_point.y() + dy)
                        polyline_points.append(next_point) # Add end point for straight line
                        last_segment_exit_azimuth = segment_tangent_azimuth_deg # Exit tangent is the same as its direction


                    feat = QgsFeature(selected_layer.fields()) # Create feature with layer's current fields
                    feat.setGeometry(QgsGeometry.fromPolylineXY(polyline_points))
                    
                    # Set attributes using field names (reliable if fields were added/exist)
                    feat.setAttribute(selected_layer.fields().indexOf("segment_id"), row_idx)
                    # Store the *effective* direction used for drawing this segment
                    feat.setAttribute(selected_layer.fields().indexOf("direction"), self._convert_azimuth_to_bearing_string(segment_tangent_azimuth_deg)) 
                    feat.setAttribute(selected_layer.fields().indexOf("distance"), distance)
                    feat.setAttribute(selected_layer.fields().indexOf("radius"), radius)
                    feat.setAttribute(selected_layer.fields().indexOf("arc_length"), arc_length)
                    
                    features_to_add.append(feat)
                    current_point = next_point # Update current point for next segment

                except ValueError: # Catches errors from float() conversions for distance/radius/arc_length
                    self.iface.messageBar().pushWarning("Traverse Plugin", f"Invalid numeric input (Distance, Radius, or Arc Length) in row {row_idx + 1}. Please ensure they are numbers.")
                    continue
                except Exception as e: # Catch other unexpected errors during loop
                    self.iface.messageBar().pushCritical("Traverse Plugin", f"Error processing row {row_idx + 1}: {e}")
                    raise # Re-raise to trigger the outer exception handler

            if features_to_add:
                selected_layer.addFeatures(features_to_add)
                selected_layer.commitChanges() # Commit changes to the layer
                selected_layer.updateExtents() # Update layer extent to encompass new features
                self.iface.mapCanvas().setExtent(selected_layer.extent()) # Zoom to new extent
                self.iface.mapCanvas().refresh()
                self.iface.messageBar().pushMessage("Traverse Plugin", f"Successfully drawn {len(features_to_add)} line segments on layer '{selected_layer.name()}'.", level=Qgis.Info)
            else:
                self.iface.messageBar().pushWarning("Traverse Plugin", "No valid traverse segments were drawn.")

        except Exception as e:
            self.iface.messageBar().pushCritical("Traverse Plugin", f"An unexpected error occurred during drawing: {e}. Changes rolled back.")
            # Rollback any pending changes if an error occurred
            if selected_layer.isEditable() and selected_layer.isModified():
                selected_layer.rollBack()
        finally:
            # If we started editing this layer for this operation, stop editing
            if not is_editable_originally and selected_layer.isEditable():
                selected_layer.commitChanges() # Try to commit, if it fails, QGIS will prompt
                if self.iface.actionToggleEditing().isChecked(): # Ensure UI button reflects state
                    self.iface.actionToggleEditing().trigger() 

    def on_table_cell_clicked(self, row, column):
        """
        Slot connected to self.tableWidget.cellClicked.
        Adds a new empty row if the click occurs on the last populated row.
        """
        total_rows = self.tableWidget.rowCount()
        
        # If table is empty, add the first row on any click
        if total_rows == 0:
            self._add_single_empty_row()
            return
        
        # If the clicked row is the last row
        if row == total_rows - 1:
            # Check if the 'Direction' cell in the last row is not empty
            direction_item = self.tableWidget.item(row, 0)
            if direction_item and direction_item.text().strip() != "":
                self._add_single_empty_row()
                self.tableWidget.setCurrentCell(total_rows, 0) # Set focus to the new row

    def _show_table_context_menu(self, pos):
        """
        Displays a context menu when the table widget is right-clicked.
        """
        menu = QtWidgets.QMenu()
        delete_action = menu.addAction("Delete Row(s)")
        
        action = menu.exec_(self.tableWidget.mapToGlobal(pos))
        if action == delete_action:
            self._delete_selected_rows()

    def _delete_selected_rows(self):
        """
        Deletes the currently selected row(s) from the table widget.
        """
        selected_rows = sorted(list(set(index.row() for index in self.tableWidget.selectedIndexes())), reverse=True)
        if not selected_rows:
            self.iface.messageBar().pushMessage("Traverse Plugin", "No rows selected to delete.", level=Qgis.Info)
            return

        reply = QtWidgets.QMessageBox.question(self, 'Delete Rows', 
                                               f"Are you sure you want to delete {len(selected_rows)} selected row(s)?",
                                               QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.Yes:
            for row_idx in selected_rows:
                self.tableWidget.removeRow(row_idx)
            self.iface.messageBar().pushMessage("Traverse Plugin", f"Deleted {len(selected_rows)} row(s).", level=Qgis.Info)
        else:
            self.iface.messageBar().pushMessage("Traverse Plugin", "Row deletion cancelled.", level=Qgis.Info)


    def clear_table_and_start_new(self):
        """
        Clears all rows from the table and adds a single new empty row
        to begin a new traverse entry.
        """
        self.tableWidget.setRowCount(0)
        self._add_single_empty_row()
        self.start_point = None # Also clear start/closing points for a fresh traverse
        self.closing_point = None
        self._first_trace_point = None # Clear any pending first trace point
        self.iface.messageBar().pushMessage("Traverse Plugin", "Table cleared. Ready for new traverse entry.", level=Qgis.Info)


    def import_data(self):
        """
        Opens a file dialog to select a data file (e.g., CSV, TXT)
        and populates the table widget with the imported data.
        This version is updated to handle 'DD' lines from 'import.txt'.
        """
        file_dialog = QtWidgets.QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(
            self,
            "Import Traverse Data",
            "",
            "All Files (*.*); CSV Files (*.csv); Text Files (*.txt)"
        )

        if file_path:
            self.iface.messageBar().pushMessage("Traverse Plugin", f"Attempting to import data from: {file_path}", level=Qgis.Info)
            self.tableWidget.setRowCount(0)

            try:
                with open(file_path, 'r') as f:
                    for line_num, line in enumerate(f, 1):
                        parts = line.strip().split(' ')
                        
                        if not parts:
                            continue

                        line_type = parts[0].upper()

                        if line_type == 'DD' and len(parts) >= 3:
                            try:
                                direction = parts[1].strip()
                                distance = float(parts[2].strip())
                                radius = 0.0
                                arc_length = 0.0
                                self.add_traverse_segment(direction, distance, radius, arc_length)
                            except ValueError:
                                self.iface.messageBar().pushWarning("Traverse Plugin",
                                                                    f"Skipping line {line_num}: Malformed numeric data for DD. Line: '{line.strip()}'")
                            except Exception as e:
                                self.iface.messageBar().pushCritical("Traverse Plugin",
                                                                    f"Error processing DD line {line_num}: {e}. Line: '{line.strip()}'")
                        elif line_type == 'SP' and len(parts) >= 3:
                            try:
                                x = float(parts[1].strip())
                                y = float(parts[2].strip())
                                self.start_point = QgsPointXY(x, y)
                                self.iface.messageBar().pushMessage("Traverse Plugin", f"Start point set from file: {self.start_point.toString()}", level=Qgis.Info)
                            except ValueError:
                                self.iface.messageBar().pushWarning("Traverse Plugin",
                                                                    f"Skipping line {line_num}: Malformed numeric data for SP. Line: '{line.strip()}'")
                            except Exception as e:
                                self.iface.messageBar().pushCritical("Traverse Plugin",
                                                                    f"Error processing SP line {line_num}: {e}. Line: '{line.strip()}'")
                        elif line_type == 'EP' and len(parts) >= 3:
                            try:
                                x = float(parts[1].strip())
                                y = float(parts[2].strip())
                                self.closing_point = QgsPointXY(x, y)
                                self.iface.messageBar().pushMessage("Traverse Plugin", f"Closing point set from file: {self.closing_point.toString()}", level=Qgis.Info)
                            except ValueError:
                                self.iface.messageBar().pushWarning("Traverse Plugin",
                                                                    f"Skipping line {line_num}: Malformed numeric data for EP. Line: '{line.strip()}'")
                            except Exception as e:
                                self.iface.messageBar().pushCritical("Traverse Plugin",
                                                                    f"Error processing EP line {line_num}: {e}. Line: '{line.strip()}'")
                        elif line_type in ['DT', 'DU']:
                            self.iface.messageBar().pushMessage("Traverse Plugin", f"Skipping line {line_num}: Unit/Type definition not handled in this version. Line: '{line.strip()}'", level=Qgis.Info)
                        else:
                            self.iface.messageBar().pushWarning("Traverse Plugin",
                                                                f"Skipping line {line_num}: Unrecognized format or incomplete data. Line: '{line.strip()}'")

                self.iface.messageBar().pushMessage("Traverse Plugin", f"Successfully imported data from {os.path.basename(file_path)}.", level=Qgis.Info)
            except FileNotFoundError:
                self.iface.messageBar().pushCritical("Traverse Plugin", f"File not found: {file_path}")
            except Exception as e:
                self.iface.messageBar().pushCritical("Traverse Plugin", f"An error occurred during import: {e}")

    def export_data(self):
        """
        Exports the traverse data from the table widget and optionally
        the start/closing points to a text file in a format similar to import.txt.
        Calculates the closing point if not explicitly set.
        """
        if self.iface is None:
            self.iface.messageBar().pushCritical("Traverse Plugin", "QGIS interface not initialized. Cannot export data.")
            return

        file_dialog = QtWidgets.QFileDialog()
        file_path, _ = file_dialog.getSaveFileName(
            self,
            "Export Traverse Data",
            os.path.join(os.path.expanduser("~"), "exported_traverse.txt"),
            "Text Files (*.txt); All Files (*.*)"
        )

        if file_path:
            try:
                with open(file_path, 'w') as f:
                    f.write("DT QB\n")
                    f.write("DU DMS\n")

                    if self.start_point:
                        f.write(f"SP {self.start_point.x():.6f} {self.start_point.y():.6f}\n")
                    else:
                        self.iface.messageBar().pushWarning("Traverse Plugin", "No start point set. Cannot export full traverse definition without it.")
                        # If no start point, cannot calculate closing point based on segments
                        return 

                    # Calculate closing point if it's not explicitly set
                    # This calculation also needs to respect the tangency logic
                    if self.closing_point is None:
                        calculated_closing_point = self.start_point
                        current_calc_azimuth = None # Will store exit azimuth of previous segment

                        for row_idx in range(self.tableWidget.rowCount()):
                            direction_item = self.tableWidget.item(row_idx, 0)
                            distance_item = self.tableWidget.item(row_idx, 1)
                            radius_item = self.tableWidget.item(row_idx, 2)
                            arc_length_item = self.tableWidget.item(row_idx, 3)

                            if not (direction_item and distance_item and distance_item.text().strip()): # Direction can be empty for tangent
                                self.iface.messageBar().pushWarning("Traverse Plugin", f"Skipping incomplete row {row_idx + 1} during closing point calculation.")
                                continue
                            
                            segment_tangent_azimuth_deg_calc = 0.0
                            direction_str_from_table_calc = direction_item.text().strip() if direction_item else ""

                            if row_idx == 0:
                                if not direction_str_from_table_calc:
                                    self.iface.messageBar().pushWarning("Traverse Plugin", f"Row {row_idx + 1}: First segment must have an explicit direction for closing point calculation. Skipping segment.")
                                    continue
                                try:
                                    cleaned_dir_str_calc = direction_str_from_table_calc.replace('°', '').strip()
                                    segment_tangent_azimuth_deg_calc = float(cleaned_dir_str_calc)
                                except ValueError:
                                    segment_tangent_azimuth_deg_calc = self._parse_bearing_to_azimuth(direction_str_from_table_calc)
                            elif direction_str_from_table_calc == "*" or not direction_str_from_table_calc:
                                if current_calc_azimuth is None:
                                    self.iface.messageBar().pushWarning("Traverse Plugin", f"Row {row_idx + 1}: Cannot determine tangent direction for closing point calculation. Skipping segment.")
                                    continue
                                segment_tangent_azimuth_deg_calc = current_calc_azimuth
                            else:
                                try:
                                    cleaned_dir_str_calc = direction_str_from_table_calc.replace('°', '').strip()
                                    segment_tangent_azimuth_deg_calc = float(cleaned_dir_str_calc)
                                except ValueError:
                                    segment_tangent_azimuth_deg_calc = self._parse_bearing_to_azimuth(direction_str_from_table_calc)
                            
                            segment_tangent_azimuth_deg_calc = segment_tangent_azimuth_deg_calc % 360
                            if segment_tangent_azimuth_deg_calc < 0:
                                segment_tangent_azimuth_deg_calc += 360

                            try:
                                distance = float(distance_item.text())
                                radius = float(radius_item.text()) if (radius_item and radius_item.text().strip()) else 0.0
                                arc_length = float(arc_length_item.text()) if (arc_length_item and arc_length_item.text().strip()) else 0.0

                                if radius != 0.0 and arc_length != 0.0:
                                    # Curve calculation for closing point
                                    tangent_math_rad_calc = math.radians(90 - segment_tangent_azimuth_deg_calc)
                                    center_angle_rad_calc = tangent_math_rad_calc - math.copysign(math.pi / 2, radius)
                                    
                                    center_x_calc = calculated_closing_point.x() + abs(radius) * math.cos(center_angle_rad_calc)
                                    center_y_calc = calculated_closing_point.y() + abs(radius) * math.sin(center_angle_rad_calc)
                                    center_point_calc = QgsPointXY(center_x_calc, center_y_calc)
                                    
                                    start_arc_angle_calc = math.atan2(calculated_closing_point.y() - center_y_calc, calculated_closing_point.x() - center_x_calc)
                                    delta_angle_rad_calc = arc_length / abs(radius)
                                    end_arc_angle_calc = start_arc_angle_calc + math.copysign(delta_angle_rad_calc, -radius)

                                    if radius > 0: # Right turn, clockwise sweep
                                        while end_arc_angle_calc > start_arc_angle_calc:
                                            end_arc_angle_calc -= 2 * math.pi
                                    else: # Left turn, counter-clockwise sweep
                                        while end_arc_angle_calc < start_arc_angle_calc:
                                            end_arc_angle_calc += 2 * math.pi

                                    # The new calculated closing point is the end point of this arc
                                    calculated_closing_point = QgsPointXY(center_x_calc + abs(radius) * math.cos(end_arc_angle_calc),
                                                                          center_y_calc + abs(radius) * math.sin(end_arc_angle_calc))
                                    
                                    # Calculate exit tangent for the curve
                                    radial_angle_at_end_calc = math.atan2(calculated_closing_point.y() - center_point_calc.y(), calculated_closing_point.x() - center_point_calc.x())
                                    exit_tangent_math_rad_calc = 0.0
                                    if radius > 0: # Right turn
                                        exit_tangent_math_rad_calc = radial_angle_at_end_calc + math.pi / 2
                                    else: # Left turn
                                        exit_tangent_math_rad_calc = radial_angle_at_end_calc - math.pi / 2
                                    
                                    current_calc_azimuth = (90 - math.degrees(exit_tangent_math_rad_calc)) % 360
                                    if current_calc_azimuth < 0:
                                        current_calc_azimuth += 360

                                else:
                                    # Straight line calculation for closing point
                                    azimuth_rad_calc = math.radians(segment_tangent_azimuth_deg_calc)
                                    dx = distance * math.sin(azimuth_rad_calc)
                                    dy = distance * math.cos(azimuth_rad_calc)
                                    calculated_closing_point = QgsPointXY(calculated_closing_point.x() + dx, calculated_closing_point.y() + dy)
                                    current_calc_azimuth = segment_tangent_azimuth_deg_calc

                            except ValueError as ve:
                                self.iface.messageBar().pushWarning("Traverse Plugin", 
                                    f"Error in row {row_idx + 1} during closing point calculation: {ve}. Skipping segment.")
                                continue
                            except Exception as e:
                                self.iface.messageBar().pushCritical("Traverse Plugin", 
                                    f"Unexpected error calculating closing point in row {row_idx + 1}: {e}. Aborting calculation.")
                                calculated_closing_point = None # Indicate failure
                                break
                        
                        if calculated_closing_point:
                            f.write(f"EP {calculated_closing_point.x():.6f} {calculated_closing_point.y():.6f}\n")
                            self.iface.messageBar().pushMessage("Traverse Plugin", "Closing point calculated from traverse segments and exported.", level=Qgis.Info)
                        else:
                            self.iface.messageBar().pushWarning("Traverse Plugin", "Could not calculate closing point from traverse segments. Check table data.")
                    else:
                        # If closing_point was explicitly set, use it
                        f.write(f"EP {self.closing_point.x():.6f} {self.closing_point.y():.6f}\n")


                    for row_idx in range(self.tableWidget.rowCount()):
                        direction_item = self.tableWidget.item(row_idx, 0)
                        distance_item = self.tableWidget.item(row_idx, 1)
                        radius_item = self.tableWidget.item(row_idx, 2)
                        arc_length_item = self.tableWidget.item(row_idx, 3)

                        if direction_item and distance_item and radius_item and arc_length_item:
                            direction_str_from_table = direction_item.text().strip()
                            radius = float(radius_item.text())
                            arc_length = float(arc_length_item.text())

                            # Convert table direction to an azimuth first
                            azimuth_deg_for_export = 0.0
                            try:
                                # Try parsing as direct decimal degrees (removing degree symbol first)
                                cleaned_direction_str = direction_str_from_table.replace('°', '').strip()
                                azimuth_deg_for_export = float(cleaned_direction_str)
                            except ValueError:
                                try:
                                    # Fallback to parsing as bearing
                                    azimuth_deg_for_export = self._parse_bearing_to_azimuth(direction_str_from_table)
                                except ValueError as ve:
                                    self.iface.messageBar().pushWarning("Traverse Plugin", 
                                        f"Skipping row {row_idx + 1} during export: Could not parse direction '{direction_str_from_table}'. Error: {ve}")
                                    continue # Skip this row

                            # Convert azimuth back to desired bearing string format for export
                            exported_direction_string = self._convert_azimuth_to_bearing_string(azimuth_deg_for_export)

                            if radius != 0.0 and arc_length != 0.0:
                                # Export as CV (Curve) type
                                f.write(f"CV {exported_direction_string} {radius:.6f} {arc_length:.6f}\n")
                            else:
                                # Export as DD (Direction-Distance) type
                                distance = float(distance_item.text())
                                f.write(f"DD {exported_direction_string} {distance:.6f}\n")
                        else:
                            self.iface.messageBar().pushWarning("Traverse Plugin", f"Skipping incomplete row {row_idx + 1} during export.")

                self.iface.messageBar().pushMessage("Traverse Plugin", f"Traverse data successfully exported to {os.path.basename(file_path)}.", level=Qgis.Info)
            except Exception as e:
                self.iface.messageBar().pushCritical("Traverse Plugin", f"An error occurred during export: {e}")

    def on_layer_changed(self, layer):
        """
        Slot connected to QgsMapLayerComboBox's layerChanged signal.
        Handles actions when the selected map layer changes.
        """
        if layer:
            self.iface.messageBar().pushMessage("Traverse Plugin", f"Selected layer: {layer.name()} (ID: {layer.id()})", level=Qgis.Info)
        else:
            self.iface.messageBar().pushMessage("Traverse Plugin", "No layer selected in the combo box.", level=Qgis.Info)

    def add_traverse_segment(self, direction, distance, radius, arc_length):
        """Adds a new row to the table with traverse segment data.
           Used when reading from file or layer, not for adding empty rows manually.
        """
        row_count = self.tableWidget.rowCount()
        self.tableWidget.insertRow(row_count)
        self.tableWidget.setItem(row_count, 0, QtWidgets.QTableWidgetItem(str(direction)))
        self.tableWidget.setItem(row_count, 1, QtWidgets.QTableWidgetItem(f"{distance:.3f}"))
        self.tableWidget.setItem(row_count, 2, QtWidgets.QTableWidgetItem(f"{radius:.3f}"))
        self.tableWidget.setItem(row_count, 3, QtWidgets.QTableWidgetItem(f"{arc_length:.3f}"))

    def _add_single_empty_row(self):
        """Adds a single empty row to the table widget with default zero values."""
        row_count = self.tableWidget.rowCount()
        self.tableWidget.insertRow(row_count)
        self.tableWidget.setItem(row_count, 0, QtWidgets.QTableWidgetItem("")) # Empty direction
        self.tableWidget.setItem(row_count, 1, QtWidgets.QTableWidgetItem("0.000")) # Default distance
        self.tableWidget.setItem(row_count, 2, QtWidgets.QTableWidgetItem("0.000")) # Default radius
        self.tableWidget.setItem(row_count, 3, QtWidgets.QTableWidgetItem("0.000")) # Default arc_length
        self.iface.messageBar().pushMessage("Traverse Plugin", "Added new empty row to the table.", level=Qgis.Info)


    def closeEvent(self, event):
        """Handle when the dock widget is closed."""
        if self.current_map_tool:
            self.canvas.unsetMapTool(self.current_map_tool)
            self.current_map_tool = None
        self.closingPlugin.emit()
        event.accept()