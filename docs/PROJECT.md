# Traverse QGIS Plugin - Project Documentation

## Overview

The Traverse plugin is a QGIS plugin designed for creating and managing traverse surveys. It provides tools for importing, creating, and exporting traverse data with support for drawing traverse lines on map layers.

## Project Structure

```
traverse/
├── traverse.py                 # Main plugin class and entry point
├── traverse_dockwidget.py      # Dock widget UI logic and functionality
├── traverse_dockwidget_base.ui # Qt Designer UI definition
├── resources.py                # Plugin resources (icons, assets)
├── __init__.py                 # Plugin initialization and metadata
├── docs/                       # Documentation folder
│   └── PROJECT.md              # This file
└── README.md                   # Project overview and installation
```

## Key Components

### Main Plugin (traverse.py)
- **TraversePlugin**: Main plugin class that initializes the QGIS plugin interface
- Handles plugin activation/deactivation
- Manages menu and toolbar actions
- Provides IFace (QGIS interface) reference

### Dock Widget (traverse_dockwidget.py)
- **TraverseDockWidget**: Main UI widget for the plugin
- Displays a table for traverse data (stations, bearings, distances)
- Provides buttons for:
  - Creating new traverse
  - Importing traverse data
  - Exporting traverse data
  - Drawing traverse on map
  - Clearing data

### UI Definition (traverse_dockwidget_base.ui)
- Qt Designer UI file
- Defines the layout and visual structure of the dock widget
- Contains table widget, buttons, and other controls

### Resources (resources.py)
- Plugin icons and assets
- Generated from .qrc file (Qt resource file)

## Features

1. **Traverse Data Management**
   - Table-based interface for entering traverse data
   - Support for stations, bearings, and distances
   - Data validation

2. **Import/Export**
   - Import traverse data from files
   - Export traverse data to various formats
   - Support for common survey formats

3. **Visualization**
   - Draw traverse lines on selected layer
   - Display traverse path on QGIS canvas
   - Visual feedback on layer editing

4. **QGIS Integration**
   - Works with QGIS vector layers
   - Integrates with QGIS dock widget system
   - Uses QGIS message bar for user feedback

## Development

### Prerequisites
- QGIS 3.x or higher
- Python 3.7+
- PyQt5 (via QGIS)
- QGIS development dependencies

### Installation

1. Copy the plugin folder to your QGIS plugins directory:
   ```
   ~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/  # Linux
   %APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\       # Windows
   ~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/  # macOS
   ```

2. Enable the plugin in QGIS Plugin Manager

### Code Quality

- **Linting**: Use flake8 with max line length of 120
  ```bash
  python -m flake8 . --max-line-length=120 --extend-ignore=E203,W503
  ```

- **Formatting**: Use Black for code formatting
  ```bash
  python -m black . --line-length=120
  ```

### Code Style Guidelines

- Follow PEP 8 standards
- Use snake_case for functions/variables
- Use PascalCase for classes
- Use UPPER_CASE for constants
- Maximum line length: 120 characters
- 4 spaces for indentation

### Testing

Currently, there are no automated tests. Manual testing involves:
1. Loading the plugin in QGIS
2. Testing traverse creation with vector layers
3. Verifying import/export functionality
4. Checking drawing and visualization

Future automated testing can use pytest:
```bash
python -m pytest tests/ -v
```

## Architecture Decisions

1. **Dock Widget Approach**: Uses QGIS dock widget for persistent UI access
2. **Table-Based Data Entry**: Provides intuitive interface for survey data
3. **Layer-Based Drawing**: Integrates with existing QGIS layers for seamless workflow
4. **Signal/Slot Pattern**: Uses Qt signals for loose coupling between components

## Dependencies

- **qgis.PyQt**: Qt bindings provided by QGIS
- **qgis.core**: QGIS core API for layer management
- **qgis.gui**: QGIS GUI components

## Future Enhancements

- Automated tests for core functionality
- Support for more survey formats
- Advanced coordinate transformations
- Traverse error checking and validation
- Export to popular survey software formats
- Undo/redo functionality

## Troubleshooting

### Plugin Not Showing
- Ensure plugin is enabled in QGIS Plugin Manager
- Check that the plugin folder is in the correct location
- Verify QGIS log for any error messages

### Import Errors
- Verify file format matches expected structure
- Check QGIS message bar for detailed error information
- Ensure vector layer is selected before operations

### Drawing Issues
- Confirm a vector layer is selected
- Check that the layer is in editing mode
- Verify traverse data is complete and valid

## License

See LICENSE file in the plugin directory.

## Contributing

See CONTRIBUTING file for contribution guidelines.

## Support

For issues and feature requests, please refer to the plugin documentation or contact the plugin maintainers.
