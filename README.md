# Spot Image Viewer and Verification Tool

Spot Image Viewer and Verification Tool is a comprehensive desktop application built for managing, indexing, and viewing spot imagery associated with electricity consumer IDs (specifically designed with WBSEDCL in mind). It goes beyond simply displaying images by offering a robust suite of assessment and calculation utilities.

## Table of Contents
- [Features](#features)
- [Project Architecture](#project-architecture)
- [Requirements](#requirements)
- [Running the Application](#running-the-application)
- [Packaging](#packaging)
- [License](#license)

## Features

- **Consumer Image Search:** Rapidly search and retrieve images linked to a 9-digit Consumer ID.
- **Local & Network Indexing:** Quickly scan, index, and cache image paths from local folders or network drives using SQLite to ensure instantaneous search results.
- **Image Inspection:** Preview images organized by date. Includes options for zooming, full-scale checking, saving, and printing directly from the canvas. 
- **Notes & Remarks Integration:** Easily log, manage, and export specific consumer observation notes (supports CSV export).
- **Theft Assessment Calculator:** A tailored utility to calculate preliminary and final electricity assessment bounds in potential theft situations based on usage patterns and tariffs.
- **Bill Calculator:** Estimate regular electricity bills according to current configurations.
- **Low Consumption Verifier:** Cross-check low consumption patterns.
- **Tariff Manager:** A built-in editor allowing users to securely edit electricity tariff slabs stored in `tariff_settings.json`.
- **Modern UI Options:** Styled using `ttkbootstrap` supporting both Light ("cosmo") and Dark ("darkly") modes.

## Project Architecture

- **`main_gui.py`**: The main entry point loading the viewer, toolbars, indexing configurations, and theme settings.
- **`database.py`**: Handles local SQLite schema generation and the WAL-enabled indexing routines.
- **`theft_calculator.py`**: User interface and computational engine for theft assessment computations.
- **`bill_calculator.py`**: Computation engine and UI for standard billing.
- **`low_consumption.py`**: Module for identifying or assessing instances of abnormally low unit consumption.
- **`tariff_manager.py` / `tariff_editor.py`**: Responsible for creating, validating, and updating JSON-based tariff configurations utilized by the calculators.
- **`utils.py`**: Helper utilities for maintaining recent logs, saved locations, notes, and backup threads.
- **`config.py`**: General configuration tokens.

## Requirements

Ensure you are using **Python 3.8+**. You will need several external libraries. Install them via your package manager:

```bash
pip install Pillow ttkbootstrap openpyxl sqlite3
# Note: sqlite3 is typically included with Python standard libraries
```

## Running the Application

To start the viewer and the main interface:

```bash
python main_gui.py
```
*(Optionally, use `python main.py` if configured as the primary bootstrap file).*

## Packaging

To package this application as a standalone executable (useful for distribution without requiring a Python environment):

The project uses PyInstaller. Ensure PyInstaller is installed (`pip install pyinstaller`). You can build the latest standalone using the provided spec configuration:

```bash
pyinstaller SpotImageViewerV18.4.spec
```

The resulting build files will be populated underneath the `dist/` directory.

## License

Copyright (c) 2026 Pramod Kumar Verma.
All Rights Reserved.
