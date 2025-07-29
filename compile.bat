@echo off
call "C:\Program Files\QGIS 3.40.5\bin\o4w_env.bat"
call "C:\Program Files\QGIS 3.40.5\bin\qt5_env.bat"
call "C:\Program Files\QGIS 3.40.5\bin\py3_env.bat"

@echo on
pyrcc5 -o resources.py resources.qrc
REM pyuic5 -o traverse_dock_widget_base.py traverse_dock_widget_base.ui