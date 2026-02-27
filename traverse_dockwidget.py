import os
import math

from qgis.PyQt import QtGui, QtWidgets, uic
from qgis.PyQt.QtCore import pyqtSignal, Qt, QVariant
from qgis.PyQt.QtGui import QIcon
from qgis.gui import QgsMapLayerComboBox, QgsMapToolEmitPoint
from qgis.core import (
    QgsProject,
    QgsVectorLayer,
    QgsPointXY,
    QgsFeature,
    QgsGeometry,
    QgsFields,
    QgsField,
    QgsWkbTypes,
    QgsFeatureRequest,
)
from qgis.core import QgsMapLayerProxyModel
from qgis.core import Qgis

try:
    from .esri_traverse import (
        EsriTraverseParser,
        DirectionType,
        DirectionUnits,
        bearing_to_azimuth,
        azimuth_to_bearing,
    )
except ImportError:
    from esri_traverse import (
        EsriTraverseParser,
        DirectionType,
        DirectionUnits,
        bearing_to_azimuth,
        azimuth_to_bearing,
    )


FORM_CLASS, _ = uic.loadUiType(
    os.path.join(os.path.dirname(__file__), "traverse_dockwidget_base.ui")
)

NUM_CURVE_SEGMENTS = 20


class traverseDockWidget(QtWidgets.QDockWidget, FORM_CLASS):
    closingPlugin = pyqtSignal()

    def __init__(self, parent=None):
        super(traverseDockWidget, self).__init__(parent)
        self.setupUi(self)

        self.iface = None
        self.canvas = None
        self.start_point = None
        self.closing_point = None
        self.current_map_tool = None
        self._first_trace_point = None

        # Hamburger Button setup
        self.hamburgerButton.setMenu(self._create_hamburger_menu())
        self.hamburgerButton.clicked.connect(self.hamburgerButton.showMenu)

        # Map Layer ComboBox setup
        self.mapLayerComboBox.setFilters(QgsMapLayerProxyModel.VectorLayer)
        self.mapLayerComboBox.layerChanged.connect(self.on_layer_changed)

        # Toolbar Actions connections
        self.actionStart.triggered.connect(self.set_start_point)
        self.actionClose.triggered.connect(self.set_closing_point)
        self.actionTraceLines.triggered.connect(self.activate_trace_line_tool)
        self.actionImport.triggered.connect(self.import_data)
        self.actionExport.triggered.connect(self.export_data)

        self.finishButton.clicked.connect(self.draw_traverse_from_table)
        self.newButton.clicked.connect(self.clear_table_and_start_new)

        # Table Widget initialization
        self.tableWidget.setRowCount(0)
        self.tableWidget.setColumnWidth(0, 100)
        self.tableWidget.setColumnWidth(1, 100)
        self.tableWidget.setColumnWidth(2, 80)
        self.tableWidget.setColumnWidth(3, 80)

        self.tableWidget.cellClicked.connect(self.on_table_cell_clicked)
        self.tableWidget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tableWidget.customContextMenuRequested.connect(
            self._show_table_context_menu
        )

    def _create_hamburger_menu(self):
        menu = QtWidgets.QMenu(self)
        menu.addAction(self.actionImport)
        menu.addAction(self.actionExport)
        return menu

    def set_qgis_interface(self, iface):
        self.iface = iface
        self.canvas = iface.mapCanvas()

    def set_start_point(self):
        if self.iface is None or self.canvas is None:
            self.iface.messageBar().pushCritical(
                "Traverse Plugin",
                "QGIS interface or map canvas not initialized.",
            )
            return

        self.iface.messageBar().pushMessage(
            "Traverse Plugin",
            "Click on the map to set the START point.",
            level=Qgis.Info,
        )

        self._deactivate_current_tool()
        self._first_trace_point = None

        tool = QgsMapToolEmitPoint(self.canvas)
        tool.canvasClicked.connect(self._handle_start_point_click)
        self.canvas.setMapTool(tool)
        self.current_map_tool = tool

    def _handle_start_point_click(self, point):
        self.start_point = point
        self.iface.messageBar().pushMessage(
            "Traverse Plugin",
            f"Start point set at: {self.start_point.toString()}",
            level=Qgis.Info,
        )
        self._deactivate_current_tool()

    def set_closing_point(self):
        if self.iface is None or self.canvas is None:
            self.iface.messageBar().pushCritical(
                "Traverse Plugin",
                "QGIS interface or map canvas not initialized.",
            )
            return

        self.iface.messageBar().pushMessage(
            "Traverse Plugin",
            "Click on the map to set the CLOSING point.",
            level=Qgis.Info,
        )

        self._deactivate_current_tool()
        self._first_trace_point = None

        tool = QgsMapToolEmitPoint(self.canvas)
        tool.canvasClicked.connect(self._handle_closing_point_click)
        self.canvas.setMapTool(tool)
        self.current_map_tool = tool

    def _handle_closing_point_click(self, point):
        self.closing_point = point
        self.iface.messageBar().pushMessage(
            "Traverse Plugin",
            f"Closing point set at: {self.closing_point.toString()}",
            level=Qgis.Info,
        )
        self._deactivate_current_tool()

    def _deactivate_current_tool(self):
        """Helper method to properly clean up current map tool."""
        if self.current_map_tool:
            self.canvas.unsetMapTool(self.current_map_tool)
            self.current_map_tool = None

    def activate_trace_line_tool(self):
        if self.iface is None or self.canvas is None:
            self.iface.messageBar().pushCritical(
                "Traverse Plugin",
                "QGIS interface not initialized.",
            )
            return

        self._deactivate_current_tool()
        self._first_trace_point = None

        self.iface.messageBar().pushMessage(
            "Traverse Plugin",
            "Click to define START of traverse segment.",
            level=Qgis.Info,
        )

        tool = QgsMapToolEmitPoint(self.canvas)
        tool.canvasClicked.connect(self._handle_trace_point_click)
        self.canvas.setMapTool(tool)
        self.current_map_tool = tool

    def _handle_trace_point_click(self, clicked_point):
        if self.iface is None or self.canvas is None:
            return

        if self._first_trace_point is None:
            self._first_trace_point = clicked_point
            self.iface.messageBar().pushMessage(
                "Traverse Plugin",
                "First point set. Click to define END of segment.",
                level=Qgis.Info,
            )
        else:
            start_segment_point = self._first_trace_point
            end_segment_point = clicked_point
            distance = start_segment_point.distance(end_segment_point)

            if distance == 0:
                self.iface.messageBar().pushWarning(
                    "Traverse Plugin",
                    "Segment has zero distance.",
                )
                return

            dx = end_segment_point.x() - start_segment_point.x()
            dy = end_segment_point.y() - start_segment_point.y()
            azimuth_rad = math.atan2(dx, dy)
            azimuth_deg = math.degrees(azimuth_rad)
            if azimuth_deg < 0:
                azimuth_deg += 360

            self.add_traverse_segment(
                f"{azimuth_deg:.2f}°", distance, 0.0, 0.0
            )
            self.start_point = end_segment_point
            self._first_trace_point = end_segment_point

            self.iface.messageBar().pushMessage(
                "Traverse Plugin",
                f"Segment added. Bearing: {azimuth_deg:.2f}°, Distance: {distance:.3f}",
                level=Qgis.Info,
            )

    def _parse_bearing_to_azimuth(self, bearing_str):
        bearing_str = bearing_str.strip().upper()

        if len(bearing_str) < 2:
            raise ValueError("Bearing string too short.")

        quadrant1 = bearing_str[0]
        quadrant2 = bearing_str[-1]

        if len(bearing_str) == 1:
            if quadrant1 == "N":
                return 0.0
            if quadrant1 == "E":
                return 90.0
            if quadrant1 == "S":
                return 180.0
            if quadrant1 == "W":
                return 270.0

        if len(bearing_str) == 2 and quadrant2 in ["E", "W"]:
            if bearing_str == "NE":
                return 45.0
            if bearing_str == "SE":
                return 135.0
            if bearing_str == "SW":
                return 225.0
            if bearing_str == "NW":
                return 315.0

        degrees_part = bearing_str[1:-1]
        parts = []
        if "-" in degrees_part:
            parts = degrees_part.split("-")
        else:
            try:
                deg = float(degrees_part)
                parts = [str(deg)]
            except ValueError:
                pass

        if not parts:
            raise ValueError(
                f"Could not parse degree/minute/second part: {degrees_part}"
            )

        deg = float(parts[0])
        minutes = float(parts[1]) if len(parts) > 1 else 0.0
        seconds = float(parts[2]) if len(parts) > 2 else 0.0

        decimal_degrees = deg + (minutes / 60.0) + (seconds / 3600.0)

        if quadrant1 == "N" and quadrant2 == "E":
            azimuth = decimal_degrees
        elif quadrant1 == "S" and quadrant2 == "E":
            azimuth = 180.0 - decimal_degrees
        elif quadrant1 == "S" and quadrant2 == "W":
            azimuth = 180.0 + decimal_degrees
        elif quadrant1 == "N" and quadrant2 == "W":
            azimuth = 360.0 - decimal_degrees
        else:
            raise ValueError(f"Invalid quadrant specification: {quadrant1}{quadrant2}")

        return azimuth % 360.0

    def _convert_azimuth_to_bearing_string(self, azimuth_deg):
        azimuth_deg = azimuth_deg % 360

        if abs(azimuth_deg - 0) < 0.0001 or abs(azimuth_deg - 360) < 0.0001:
            return "N"
        if abs(azimuth_deg - 90) < 0.0001:
            return "E"
        if abs(azimuth_deg - 180) < 0.0001:
            return "S"
        if abs(azimuth_deg - 270) < 0.0001:
            return "W"

        if 0 < azimuth_deg < 90:
            prefix, suffix = "N", "E"
            bearing_value = azimuth_deg
        elif 90 < azimuth_deg < 180:
            prefix, suffix = "S", "E"
            bearing_value = 180 - azimuth_deg
        elif 180 < azimuth_deg < 270:
            prefix, suffix = "S", "W"
            bearing_value = azimuth_deg - 180
        else:
            prefix, suffix = "N", "W"
            bearing_value = 360 - azimuth_deg

        degrees = int(bearing_value)
        minutes_float = (bearing_value - degrees) * 60
        minutes = int(minutes_float)
        seconds = round((minutes_float - minutes) * 60, 0)

        if seconds >= 60:
            minutes += 1
            seconds = 0
        if minutes >= 60:
            degrees += 1
            minutes = 0
            if degrees == 90:
                return suffix if prefix == "N" else prefix

        return f"{prefix}{degrees}-{minutes}-{int(seconds)}{suffix}"

    def draw_traverse_from_table(self):
        if self.iface is None or self.canvas is None:
            self.iface.messageBar().pushCritical(
                "Traverse Plugin",
                "QGIS interface not initialized.",
            )
            return

        selected_layer = self.mapLayerComboBox.currentLayer()
        if selected_layer is None:
            self.iface.messageBar().pushWarning(
                "Traverse Plugin",
                "Please select a layer.",
            )
            return

        if not isinstance(selected_layer, QgsVectorLayer):
            self.iface.messageBar().pushWarning(
                "Traverse Plugin",
                "Selected layer is not a vector layer.",
            )
            return

        if not (
            selected_layer.wkbType() == QgsWkbTypes.LineString
            or selected_layer.wkbType() == QgsWkbTypes.MultiLineString
        ):
            self.iface.messageBar().pushWarning(
                "Traverse Plugin",
                f"Selected layer '{selected_layer.name()}' is not a line layer.",
            )
            return

        is_editable_originally = selected_layer.isEditable()
        if not is_editable_originally:
            reply = QtWidgets.QMessageBox.question(
                self,
                "Toggle Editing",
                f"Enable editing for '{selected_layer.name()}'?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            )
            if reply == QtWidgets.QMessageBox.Yes:
                selected_layer.startEditing()
                if not self.iface.actionToggleEditing().isChecked():
                    self.iface.actionToggleEditing().trigger()
            else:
                self.iface.messageBar().pushWarning(
                    "Traverse Plugin",
                    "Layer not editable. Cannot draw.",
                )
                return

        if self.start_point is None:
            self.iface.messageBar().pushWarning(
                "Traverse Plugin",
                "Please set a START point.",
            )
            if not is_editable_originally:
                selected_layer.rollBack()
                if self.iface.actionToggleEditing().isChecked():
                    self.iface.actionToggleEditing().trigger()
            return

        if self.tableWidget.rowCount() == 0:
            self.iface.messageBar().pushWarning(
                "Traverse Plugin", "Table is empty."
            )
            if not is_editable_originally:
                selected_layer.rollBack()
                if self.iface.actionToggleEditing().isChecked():
                    self.iface.actionToggleEditing().trigger()
            return

        current_point = self.start_point
        features_to_add = []
        last_segment_exit_azimuth = None

        required_fields_info = [
            ("segment_id", QVariant.Int),
            ("direction", QVariant.String),
            ("distance", QVariant.Double),
            ("radius", QVariant.Double),
            ("arc_length", QVariant.Double),
        ]

        prov = selected_layer.dataProvider()
        fields_to_add = QgsFields()
        for field_name, field_type in required_fields_info:
            if selected_layer.fields().indexOf(field_name) == -1:
                fields_to_add.append(QgsField(field_name, field_type))

        if fields_to_add.count() > 0:
            if not prov.addAttributes(fields_to_add):
                self.iface.messageBar().pushCritical(
                    "Traverse Plugin", "Failed to add fields."
                )
                if not is_editable_originally:
                    selected_layer.rollBack()
                    if self.iface.actionToggleEditing().isChecked():
                        self.iface.actionToggleEditing().trigger()
                return
            selected_layer.updateFields()

        try:
            for row_idx in range(self.tableWidget.rowCount()):
                direction_item = self.tableWidget.item(row_idx, 0)
                distance_item = self.tableWidget.item(row_idx, 1)
                radius_item = self.tableWidget.item(row_idx, 2)
                arc_length_item = self.tableWidget.item(row_idx, 3)

                if not (direction_item and distance_item and distance_item.text().strip()):
                    self.iface.messageBar().pushWarning(
                        "Traverse Plugin",
                        f"Skipping incomplete row {row_idx + 1}.",
                    )
                    continue

                direction_str = direction_item.text().strip() if direction_item else ""
                segment_azimuth = 0.0

                # Determine azimuth (same logic as before)
                if row_idx == 0:
                    if not direction_str or direction_str.startswith("AD:"):
                        self.iface.messageBar().pushWarning(
                            "Traverse Plugin",
                            f"Row {row_idx + 1}: First segment needs explicit direction.",
                        )
                        continue
                    segment_azimuth = self._get_azimuth_from_string(direction_str)
                elif direction_str == "*" or not direction_str:
                    if last_segment_exit_azimuth is None:
                        self.iface.messageBar().pushWarning(
                            "Traverse Plugin",
                            f"Row {row_idx + 1}: Cannot determine tangent.",
                        )
                        continue
                    segment_azimuth = last_segment_exit_azimuth
                else:
                    if direction_str.startswith("AD:"):
                        if last_segment_exit_azimuth is None:
                            continue
                        try:
                            offset = float(direction_str[3:].strip())
                            segment_azimuth = (last_segment_exit_azimuth + offset) % 360
                        except ValueError:
                            continue
                    else:
                        segment_azimuth = self._get_azimuth_from_string(direction_str)

                segment_azimuth = segment_azimuth % 360

                try:
                    distance = float(distance_item.text()) if distance_item else 0.0
                    radius = float(radius_item.text()) if radius_item and radius_item.text().strip() else 0.0
                    arc_length = float(arc_length_item.text()) if arc_length_item and arc_length_item.text().strip() else 0.0

                    polyline_points = [current_point]
                    is_curve = radius != 0.0 and arc_length != 0.0
                    is_nontangent_chord = is_curve and not direction_str.startswith(("*", "AD:"))

                    if is_nontangent_chord:
                        polyline_points, next_point, last_segment_exit_azimuth = \
                            self._calculate_nontangent_curve_from_chord(
                                current_point, segment_azimuth, distance, radius
                            )
                    elif is_curve:
                        polyline_points, next_point, last_segment_exit_azimuth = \
                            self._calculate_tangent_curve(
                                current_point, segment_azimuth, radius, arc_length
                            )
                    else:
                        azimuth_rad = math.radians(segment_azimuth)
                        dx = distance * math.sin(azimuth_rad)
                        dy = distance * math.cos(azimuth_rad)
                        next_point = QgsPointXY(
                            current_point.x() + dx, current_point.y() + dy
                        )
                        polyline_points.append(next_point)
                        last_segment_exit_azimuth = segment_azimuth

                    feat = QgsFeature(selected_layer.fields())
                    feat.setGeometry(QgsGeometry.fromPolylineXY(polyline_points))
                    feat.setAttribute("segment_id", row_idx)
                    feat.setAttribute(
                        "direction",
                        self._convert_azimuth_to_bearing_string(segment_azimuth),
                    )
                    feat.setAttribute("distance", distance)
                    feat.setAttribute("radius", radius)
                    feat.setAttribute("arc_length", arc_length)
                    features_to_add.append(feat)
                    current_point = next_point

                except (ValueError, IndexError) as e:
                    self.iface.messageBar().pushWarning(
                        "Traverse Plugin", f"Error in row {row_idx + 1}: {e}"
                    )
                    continue

            if features_to_add:
                selected_layer.addFeatures(features_to_add)
                selected_layer.commitChanges()
                selected_layer.updateExtents()
                self.iface.mapCanvas().setExtent(selected_layer.extent())
                self.iface.mapCanvas().refresh()
                self.iface.messageBar().pushMessage(
                    "Traverse Plugin",
                    f"Drawn {len(features_to_add)} segments.",
                    level=Qgis.Info,
                )
            else:
                self.iface.messageBar().pushWarning(
                    "Traverse Plugin", "No valid segments drawn."
                )

        except Exception as e:
            self.iface.messageBar().pushCritical(
                "Traverse Plugin",
                f"Error during drawing: {e}.",
            )
            if selected_layer.isEditable() and selected_layer.isModified():
                selected_layer.rollBack()
        finally:
            if not is_editable_originally and selected_layer.isEditable():
                selected_layer.commitChanges()
                if self.iface.actionToggleEditing().isChecked():
                    self.iface.actionToggleEditing().trigger()

    def _get_azimuth_from_string(self, direction_str):
        """Helper to parse azimuth from string (decimal or bearing)."""
        try:
            cleaned = direction_str.replace("°", "").strip()
            return float(cleaned)
        except ValueError:
            return self._parse_bearing_to_azimuth(direction_str)

    def _calculate_tangent_curve(self, start_point, tangent_azimuth, radius, arc_length):
        """Calculate geometry for a tangent curve."""
        tangent_math_rad = math.radians(90 - tangent_azimuth)
        center_angle_rad = tangent_math_rad - math.copysign(math.pi / 2, radius)
        
        center_x = start_point.x() + abs(radius) * math.cos(center_angle_rad)
        center_y = start_point.y() + abs(radius) * math.sin(center_angle_rad)
        
        start_arc_angle = math.atan2(
            start_point.y() - center_y, start_point.x() - center_x
        )
        delta_angle_rad = arc_length / abs(radius)
        end_arc_angle = start_arc_angle + math.copysign(delta_angle_rad, -radius)
        
        polyline = [start_point]
        for i in range(1, NUM_CURVE_SEGMENTS + 1):
            step = (end_arc_angle - start_arc_angle) / NUM_CURVE_SEGMENTS
            angle = start_arc_angle + i * step
            px = center_x + abs(radius) * math.cos(angle)
            py = center_y + abs(radius) * math.sin(angle)
            polyline.append(QgsPointXY(px, py))
        
        end_point = polyline[-1]
        radial_end = math.atan2(end_point.y() - center_y, end_point.x() - center_x)
        exit_tangent_rad = radial_end + math.copysign(math.pi / 2, -radius)
        exit_azimuth = (90 - math.degrees(exit_tangent_rad) + 360) % 360
        
        return polyline, end_point, exit_azimuth

    def _calculate_nontangent_curve_from_chord(
        self, start_point, chord_azimuth_deg, chord_length, radius
    ):
        """Calculate geometry for a nontangent curve defined by chord."""
        if chord_length == 0:
            raise ValueError("Chord length cannot be zero.")
        
        half_chord = chord_length / 2.0
        if abs(radius) < half_chord:
            raise ValueError("Radius cannot be smaller than half chord length.")
        
        chord_az_rad = math.radians(chord_azimuth_deg)
        
        # End point of chord
        end_chord_x = start_point.x() + chord_length * math.sin(chord_az_rad)
        end_chord_y = start_point.y() + chord_length * math.cos(chord_az_rad)
        
        # Midpoint
        mid_x = (start_point.x() + end_chord_x) / 2.0
        mid_y = (start_point.y() + end_chord_y) / 2.0
        
        # Distance to center
        sagitta_h = math.sqrt(radius**2 - half_chord**2)
        
        # Center location (perpendicular to chord)
        center_angle_rad = chord_az_rad + math.copysign(math.pi / 2, radius)
        center_x = mid_x + sagitta_h * math.sin(center_angle_rad)
        center_y = mid_y + sagitta_h * math.cos(center_angle_rad)
        
        # Arc angles
        start_angle = math.atan2(start_point.y() - center_y, start_point.x() - center_x)
        delta_angle = 2 * math.asin(half_chord / abs(radius))
        end_angle = start_angle + math.copysign(delta_angle, -radius)
        
        # Generate polyline
        polyline = [start_point]
        for i in range(1, NUM_CURVE_SEGMENTS + 1):
            step = (end_angle - start_angle) / NUM_CURVE_SEGMENTS
            angle = start_angle + i * step
            px = center_x + abs(radius) * math.cos(angle)
            py = center_y + abs(radius) * math.sin(angle)
            polyline.append(QgsPointXY(px, py))
        
        end_point = polyline[-1]
        radial_end = math.atan2(end_point.y() - center_y, end_point.x() - center_x)
        exit_tangent_rad = radial_end + math.copysign(math.pi / 2, -radius)
        exit_azimuth = (90 - math.degrees(exit_tangent_rad) + 360) % 360
        
        return polyline, end_point, exit_azimuth

    def on_table_cell_clicked(self, row, column):
        total_rows = self.tableWidget.rowCount()
        if total_rows == 0:
            self._add_single_empty_row()
            return

        if row == total_rows - 1:
            direction_item = self.tableWidget.item(row, 0)
            if direction_item and direction_item.text().strip() != "":
                self._add_single_empty_row()
                self.tableWidget.setCurrentCell(total_rows, 0)

    def _show_table_context_menu(self, pos):
        menu = QtWidgets.QMenu()
        delete_action = menu.addAction("Delete Row(s)")
        action = menu.exec_(self.tableWidget.mapToGlobal(pos))
        if action == delete_action:
            self._delete_selected_rows()

    def _delete_selected_rows(self):
        selected_rows = sorted(
            list(set(index.row() for index in self.tableWidget.selectedIndexes())),
            reverse=True,
        )
        if not selected_rows:
            return

        reply = QtWidgets.QMessageBox.question(
            self,
            "Delete Rows",
            f"Delete {len(selected_rows)} row(s)?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
        )
        if reply == QtWidgets.QMessageBox.Yes:
            for row_idx in selected_rows:
                self.tableWidget.removeRow(row_idx)

    def clear_table_and_start_new(self):
        self.tableWidget.setRowCount(0)
        self._add_single_empty_row()
        self.start_point = None
        self.closing_point = None
        self._first_trace_point = None
        self.iface.messageBar().pushMessage(
            "Traverse Plugin",
            "Ready for new traverse.",
            level=Qgis.Info,
        )

    def import_data(self):
        file_dialog = QtWidgets.QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(
            self,
            "Import Traverse Data",
            "",
            "Text Files (*.txt)",
        )

        if not file_path:
            return

        self.tableWidget.setRowCount(0)

        try:
            parser = EsriTraverseParser()
            if not parser.parse_file(file_path):
                for error in parser.errors:
                    self.iface.messageBar().pushCritical("Traverse Plugin", error)
                return

            for warning in parser.warnings:
                self.iface.messageBar().pushWarning("Traverse Plugin", warning)

            if parser.start_point:
                self.start_point = QgsPointXY(
                    parser.start_point[0], parser.start_point[1]
                )

            if parser.end_point:
                self.closing_point = QgsPointXY(
                    parser.end_point[0], parser.end_point[1]
                )

            for course in parser.courses:
                if course.course_type == "DD":
                    self.add_traverse_segment(
                        course.direction, course.distance, 0.0, 0.0
                    )
                elif course.course_type == "AD":
                    angle_str = self._format_angle_from_decimal(
                        course.angle_offset, DirectionUnits.DD
                    )
                    self.add_traverse_segment(
                        f"AD:{angle_str}", course.distance, 0.0, 0.0
                    )
                elif course.course_type == "TC":
                    radius = self._calculate_radius_from_curve(
                        course.curve_measure_type,
                        course.curve_measure_value,
                        course.curve_angle_type,
                        course.curve_angle_value,
                    )
                    arc_length = self._calculate_arc_length_from_curve(
                        course.curve_measure_type,
                        course.curve_measure_value,
                        course.curve_angle_type,
                        course.curve_angle_value,
                        radius,
                    )
                    if course.curve_turn == "L":
                        radius = -abs(radius)
                    else:
                        radius = abs(radius)
                    self.add_traverse_segment("*", 0.0, radius, arc_length)
                elif course.course_type == "NC":
                    direction = course.curve_direction_value or "N0-0-0E"
                    radius = self._calculate_radius_from_curve(
                        course.curve_measure_type,
                        course.curve_measure_value,
                        course.curve_angle_type,
                        course.curve_angle_value,
                    )
                    arc_length = self._calculate_arc_length_from_curve(
                        course.curve_measure_type,
                        course.curve_measure_value,
                        course.curve_angle_type,
                        course.curve_angle_value,
                        radius,
                    )
                    chord_length = self._calculate_chord_length_from_curve(
                        arc_length, radius
                    )
                    if course.curve_turn == "L":
                        radius = -abs(radius)
                    else:
                        radius = abs(radius)
                    self.add_traverse_segment(
                        direction, chord_length, radius, arc_length
                    )

        except Exception as e:
            self.iface.messageBar().pushCritical(
                "Traverse Plugin", f"Import error: {e}"
            )

    def _format_angle_from_decimal(self, angle_deg, direction_units):
        if direction_units == DirectionUnits.DMS:
            deg = int(angle_deg)
            min_float = (angle_deg - deg) * 60
            minutes = int(min_float)
            seconds = (min_float - minutes) * 60
            return f"{deg}-{minutes}-{seconds:.2f}"
        else:
            return f"{angle_deg:.2f}"

    def _calculate_radius_from_curve(
        self, measure_type, measure_value, angle_type, angle_value
    ):
        if measure_type == "R":
            return measure_value
        elif measure_type in ["D", "C"]:
            if angle_value == 0:
                raise ValueError("Angle value cannot be zero for radius calculation.")
            angle_rad = math.radians(angle_value)
            return measure_value / (2 * math.sin(angle_rad / 2))
        elif measure_type == "A":
            if angle_value == 0:
                raise ValueError("Angle value cannot be zero for radius calculation.")
            angle_rad = math.radians(angle_value)
            return measure_value / angle_rad
        return 0.0

    def _calculate_arc_length_from_curve(
        self, measure_type, measure_value, angle_type, angle_value, radius
    ):
        if measure_type == "A":
            return measure_value
        elif measure_type == "D":
            angle_rad = math.radians(angle_value)
            return abs(radius) * angle_rad
        elif measure_type == "C":
            if abs(radius) > 0:
                delta_angle = 2 * math.asin((measure_value / 2) / abs(radius))
                return abs(radius) * delta_angle
        elif measure_type == "R":
            return measure_value
        return 0.0

    def _calculate_chord_length_from_curve(self, arc_length, radius):
        if abs(radius) == 0:
            return arc_length
        delta_angle_rad = arc_length / abs(radius)
        return 2 * abs(radius) * math.sin(delta_angle_rad / 2)

    def export_data(self):
        if self.iface is None:
            return

        file_dialog = QtWidgets.QFileDialog()
        file_path, _ = file_dialog.getSaveFileName(
            self,
            "Export Traverse Data",
            os.path.join(os.path.expanduser("~"), "exported_traverse.txt"),
            "Text Files (*.txt); All Files (*.*)",
        )

        if not file_path:
            return

        try:
            with open(file_path, "w") as f:
                f.write("DT QB\n")
                f.write("DU DMS\n")

                if self.start_point:
                    f.write(
                        f"SP {self.start_point.x():.6f} {self.start_point.y():.6f}\n"
                    )
                else:
                    self.iface.messageBar().pushWarning(
                        "Traverse Plugin", "No start point set."
                    )
                    return

                # Calculate closing point if not set
                if self.closing_point is None:
                    calc_point = self._calculate_closing_point_from_table()
                    if calc_point:
                        f.write(f"EP {calc_point.x():.6f} {calc_point.y():.6f}\n")
                    else:
                        self.iface.messageBar().pushWarning(
                            "Traverse Plugin", "Could not calculate closing point."
                        )
                else:
                    f.write(
                        f"EP {self.closing_point.x():.6f} {self.closing_point.y():.6f}\n"
                    )

                # Export rows
                for row_idx in range(self.tableWidget.rowCount()):
                    self._export_row(f, row_idx)

            self.iface.messageBar().pushMessage(
                "Traverse Plugin",
                f"Exported to {os.path.basename(file_path)}.",
                level=Qgis.Info,
            )
        except Exception as e:
            self.iface.messageBar().pushCritical(
                "Traverse Plugin", f"Export error: {e}"
            )

    def _calculate_closing_point_from_table(self):
        """Calculate closing point from table data."""
        if not self.start_point:
            return None
            
        calc_point = self.start_point
        current_azimuth = None

        for row_idx in range(self.tableWidget.rowCount()):
            direction_item = self.tableWidget.item(row_idx, 0)
            distance_item = self.tableWidget.item(row_idx, 1)
            radius_item = self.tableWidget.item(row_idx, 2)
            arc_length_item = self.tableWidget.item(row_idx, 3)

            if not (direction_item and distance_item):
                continue

            direction_str = direction_item.text().strip()
            
            # Determine azimuth
            if row_idx == 0:
                if not direction_str or direction_str.startswith("AD:"):
                    continue
                azimuth = self._get_azimuth_from_string(direction_str)
            elif direction_str == "*" or not direction_str:
                if current_azimuth is None:
                    continue
                azimuth = current_azimuth
            else:
                if direction_str.startswith("AD:"):
                    if current_azimuth is None:
                        continue
                    try:
                        offset = float(direction_str[3:].strip())
                        azimuth = (current_azimuth + offset) % 360
                    except ValueError:
                        continue
                else:
                    azimuth = self._get_azimuth_from_string(direction_str)

            try:
                distance = float(distance_item.text())
                radius = float(radius_item.text()) if radius_item and radius_item.text().strip() else 0.0
                arc_length = float(arc_length_item.text()) if arc_length_item and arc_length_item.text().strip() else 0.0

                if radius != 0.0 and arc_length != 0.0:
                    # Curve
                    tangent_math_rad = math.radians(90 - azimuth)
                    center_angle_rad = tangent_math_rad - math.copysign(math.pi / 2, radius)
                    center_x = calc_point.x() + abs(radius) * math.cos(center_angle_rad)
                    center_y = calc_point.y() + abs(radius) * math.sin(center_angle_rad)
                    
                    start_arc = math.atan2(calc_point.y() - center_y, calc_point.x() - center_x)
                    delta = arc_length / abs(radius)
                    end_arc = start_arc + math.copysign(delta, -radius)
                    
                    # Normalize sweep direction
                    if radius > 0:  # Right/CW
                        while end_arc > start_arc:
                            end_arc -= 2 * math.pi
                    else:  # Left/CCW
                        while end_arc < start_arc:
                            end_arc += 2 * math.pi
                    
                    calc_point = QgsPointXY(
                        center_x + abs(radius) * math.cos(end_arc),
                        center_y + abs(radius) * math.sin(end_arc),
                    )
                    
                    # Update exit azimuth
                    radial_end = math.atan2(calc_point.y() - center_y, calc_point.x() - center_x)
                    exit_tangent = radial_end + (math.pi / 2 if radius > 0 else -math.pi / 2)
                    current_azimuth = (90 - math.degrees(exit_tangent)) % 360
                else:
                    # Straight line
                    azimuth_rad = math.radians(azimuth)
                    dx = distance * math.sin(azimuth_rad)
                    dy = distance * math.cos(azimuth_rad)
                    calc_point = QgsPointXY(calc_point.x() + dx, calc_point.y() + dy)
                    current_azimuth = azimuth

            except (ValueError, ZeroDivisionError):
                continue

        return calc_point

    def _export_row(self, file_handle, row_idx):
        """Export a single row to file."""
        direction_item = self.tableWidget.item(row_idx, 0)
        distance_item = self.tableWidget.item(row_idx, 1)
        radius_item = self.tableWidget.item(row_idx, 2)
        arc_length_item = self.tableWidget.item(row_idx, 3)

        if not all([direction_item, distance_item, radius_item, arc_length_item]):
            return

        direction_str = direction_item.text().strip()
        try:
            distance = float(distance_item.text())
            radius = float(radius_item.text())
            arc_length = float(arc_length_item.text())
        except ValueError:
            return

        if radius != 0.0 and arc_length != 0.0:
            # Curve
            central_angle_rad = arc_length / abs(radius)
            central_angle_deg = math.degrees(central_angle_rad)
            turn = "L" if radius < 0 else "R"
            
            if direction_str == "*" or not direction_str:
                # Tangent curve
                file_handle.write(
                    f"TC A {arc_length:.6f} D {central_angle_deg:.2f} {turn}\n"
                )
            else:
                # Nontangent curve
                try:
                    azimuth = self._get_azimuth_from_string(direction_str)
                    bearing = self._convert_azimuth_to_bearing_string(azimuth)
                    file_handle.write(
                        f"NC A {arc_length:.6f} D {central_angle_deg:.2f} C {bearing} {turn}\n"
                    )
                except ValueError:
                    pass
        else:
            # Straight line
            if direction_str.startswith("AD:"):
                try:
                    angle = float(direction_str[3:].strip())
                    file_handle.write(f"AD {angle:.2f} {distance:.6f}\n")
                except ValueError:
                    pass
            else:
                try:
                    azimuth = self._get_azimuth_from_string(direction_str)
                    bearing = self._convert_azimuth_to_bearing_string(azimuth)
                    file_handle.write(f"DD {bearing} {distance:.6f}\n")
                except ValueError:
                    pass

    def on_layer_changed(self, layer):
        if layer:
            self.iface.messageBar().pushMessage(
                "Traverse Plugin",
                f"Selected: {layer.name()}",
                level=Qgis.Info,
            )

    def add_traverse_segment(self, direction, distance, radius, arc_length):
        row_count = self.tableWidget.rowCount()
        self.tableWidget.insertRow(row_count)
        self.tableWidget.setItem(row_count, 0, QtWidgets.QTableWidgetItem(str(direction)))
        self.tableWidget.setItem(row_count, 1, QtWidgets.QTableWidgetItem(f"{distance:.3f}"))
        self.tableWidget.setItem(row_count, 2, QtWidgets.QTableWidgetItem(f"{radius:.3f}"))
        self.tableWidget.setItem(row_count, 3, QtWidgets.QTableWidgetItem(f"{arc_length:.3f}"))

    def _add_single_empty_row(self):
        row_count = self.tableWidget.rowCount()
        self.tableWidget.insertRow(row_count)
        self.tableWidget.setItem(row_count, 0, QtWidgets.QTableWidgetItem(""))
        self.tableWidget.setItem(row_count, 1, QtWidgets.QTableWidgetItem("0.000"))
        self.tableWidget.setItem(row_count, 2, QtWidgets.QTableWidgetItem("0.000"))
        self.tableWidget.setItem(row_count, 3, QtWidgets.QTableWidgetItem("0.000"))

    def closeEvent(self, event):
        self._deactivate_current_tool()
        self.closingPlugin.emit()
        event.accept()