# AGENTS.md

This file provides guidelines for agentic coding agents working in the Traverse QGIS plugin repository. It outlines build, lint, and test commands, as well as code style guidelines to maintain consistency.

## Repository Overview

This is a QGIS Python plugin for creating and managing traverse surveys. It consists of:
- `traverse.py`: Main plugin class
- `traverse_dockwidget.py`: Dock widget logic with PyQt UI
- `traverse_dockwidget_base.ui`: Qt Designer UI definition
- `resources.py`: Plugin resources
- `__init__.py`: Plugin initialization

The plugin uses PyQt5/Qt6 (via QGIS PyQt bindings) and QGIS API for GIS functionality.

## Build/Lint/Test Commands

### Linting
Run linting to check code quality and style:
```bash
python -m flake8 . --max-line-length=120 --extend-ignore=E203,W503
```
- Use `flake8` for Python linting
- Line length: 120 characters
- Ignore E203 (whitespace before ':') and W503 (line break before binary operator) for Black compatibility

Alternative with Ruff (faster):
```bash
python -m ruff check . --line-length=120
```

### Code Formatting
Format code automatically:
```bash
python -m black . --line-length=120
```
- Use Black for consistent formatting
- Line length: 120 characters

### Testing
Since this is a QGIS plugin, tests require QGIS environment. There are currently no automated tests, but manual testing involves:

1. Install the plugin in QGIS
2. Load test data (vector layers)
3. Test traverse creation, import/export, and drawing functionality

To run if tests were added in the future:
```bash
python -m pytest tests/ -v
```

For a single test:
```bash
python -m pytest tests/test_specific.py::TestClass::test_method -v
```

### Plugin Packaging
To package the plugin for distribution:
```bash
# Using pb_tool (if installed)
pb_tool compile
pb_tool package

# Or manually zip the plugin directory
zip -r traverse.zip traverse/
```

### Running the Plugin
To test the plugin in QGIS:
1. Copy the plugin folder to QGIS plugins directory
2. Enable the plugin in QGIS Plugin Manager
3. Open the Traverse dock widget from the Plugins menu

## Code Style Guidelines

### General Python Conventions
- Follow PEP 8 style guide
- Use snake_case for variables, functions, and methods
- Use PascalCase for classes
- Use UPPER_CASE for constants
- Maximum line length: 120 characters
- Use 4 spaces for indentation (no tabs)

### Imports
- Group imports: standard library, third-party (PyQt, QGIS), local modules
- Use absolute imports within the plugin
- Import specific items, not modules when possible

```python
# Good
import os
import math

from qgis.PyQt import QtWidgets, QtCore
from qgis.PyQt.QtCore import pyqtSignal
from qgis.core import QgsProject, QgsVectorLayer

# Avoid
from qgis.PyQt import *
import qgis.core
```

### Naming Conventions
- **Classes**: PascalCase (e.g., `TraverseDockWidget`)
- **Methods/Functions**: snake_case (e.g., `set_start_point`, `draw_traverse_from_table`)
- **Variables**: snake_case (e.g., `start_point`, `selected_layer`)
- **Constants**: UPPER_CASE (e.g., `NUM_CURVE_SEGMENTS`)
- **Qt Objects**: Follow Qt naming (e.g., `actionImport`, `finishButton`)
- **Private methods**: Prefix with underscore (e.g., `_create_hamburger_menu`)

### Error Handling
- Use try/except blocks for operations that may fail
- Show user-friendly error messages via `iface.messageBar()`
- Log critical errors appropriately
- Handle QGIS-specific exceptions (e.g., layer operations)

```python
try:
    # risky operation
    selected_layer.startEditing()
except Exception as e:
    self.iface.messageBar().pushCritical("Plugin Name", f"Error: {e}")
```

### Type Hints (Optional but Recommended)
Add type hints for new code:
```python
from typing import Optional, List
from qgis.core import QgsVectorLayer

def process_layer(self, layer: Optional[QgsVectorLayer]) -> bool:
    # implementation
```

### Qt/PyQt Specific
- Use Qt signal/slot connections properly
- Set object names for UI elements for testing
- Use QGIS icon standards for toolbar actions
- Follow QGIS message bar conventions for user feedback

### Documentation
- Add docstrings for classes and methods using triple quotes
- Document parameters, return types, and exceptions
- Use clear, descriptive variable names
- Add comments for complex logic

```python
def draw_traverse_from_table(self):
    """
    Draws traverse lines on the selected layer based on table data.
    
    Raises:
        ValueError: If required data is missing
    """
```

### File Organization
- Keep UI logic in dockwidget file
- Separate resources in resources.py
- Main plugin logic in traverse.py
- UI definition in .ui file

### Security
- Validate user inputs (file paths, numeric values)
- Use safe file operations
- Avoid executing untrusted code
- Handle sensitive data appropriately (though not applicable here)

### Performance
- Avoid unnecessary computations in UI event handlers
- Use appropriate data structures
- Consider memory usage for large datasets
- Use QGIS progress indicators for long operations

### Testing Guidelines
- Write unit tests for utility functions
- Use QGIS testing framework for integration tests
- Mock QGIS interfaces when possible
- Test edge cases (empty tables, invalid inputs)

### Git Workflow
- Use descriptive commit messages
- Follow conventional commits if applicable
- Test changes before committing
- Use branches for features/bugs

### QGIS Specific
- Check iface and canvas availability before operations
- Handle layer editing states properly
- Use QGIS coordinate reference systems appropriately
- Follow QGIS plugin development best practices

This document should be updated as the codebase evolves and new tools/patterns are adopted.