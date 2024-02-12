# DeepForest QGIS Plug-in

### Info

This small package connects with a **DeepForest** web service.  
More info: https://github.com/pxl-research/sgm-qgis-flask

DeepForest is a python package for airborne object detection and classification.  
More info: https://deepforest.readthedocs.io/en/latest/landing.html

# Documentation

### Requirements

- QGIS version 3.28 (LTR) or later
- Python version 3.X
- Other dependencies are listed in `requirements.txt` (mainly `numpy`)

### Installation

1. Clone this repository or download the ZIP file.
2. Extract the contents to your QGIS plugin directory.
3. Install dependencies from `requirements.txt` using `pip install -r requirements.txt`.
4. Enable the plugin in QGIS.

### Usage

1. Open QGIS.
2. Navigate to the Plugins menu and ensure the DeepForest plugin is enabled.
3. Access the plugin through the QGIS interface.
4. Configure the connection settings to the DeepForest webservice.
5. Use the plugin tools to analyze satellite imagery for tree detection.
