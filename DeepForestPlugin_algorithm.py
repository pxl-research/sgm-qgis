# -*- coding: utf-8 -*-

"""
/***************************************************************************
 DeepForestPlugin
                                 A QGIS plugin
 Plugin using DeepForest to detect trees
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2023-02-21
        copyright            : (C) 2023 by PXL Smart ICT
        email                : servaas.tilkin@pxl.be
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

__author__ = 'PXL Smart ICT'
__date__ = '2023-02-21'
__copyright__ = '(C) 2023 by PXL Smart ICT'

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'

import datetime
import json
import math

import numpy as np
import requests
from . import resources
from PIL import Image
from osgeo import gdal
from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.core import (QgsProcessingAlgorithm,
                       QgsProcessingParameterRasterLayer,
                       QgsProcessingParameterFolderDestination,
                       QgsProcessingParameterNumber,
                       QgsRasterLayer)


# https://www.qgistutorials.com/en/docs/3/processing_python_plugin.html
# https://docs.qgis.org/3.22/en/docs/pyqgis_developer_cookbook/cheat_sheet.html#layers
class DeepForestPluginAlgorithm(QgsProcessingAlgorithm):
    """
    All Processing algorithms should extend the QgsProcessingAlgorithm
    class.
    """

    # Constants used to refer to parameters and outputs. They will be
    # used when calling the algorithm from another algorithm, or when
    # calling from the QGIS console.

    OUTPUT = 'OUTPUT'
    INPUT = 'INPUT'
    INPUT_LIMIT = 'INPUT_LIMIT'
    INPUT_TILE_SLICE = 'INPUT_TILE'
    INPUT_PATCH_SIZE = 'INPUT_WINDOW'
    INPUT_OVERLAP = 'INPUT_PATCH_OVERLAP'
    INPUT_THRESH = 'INPUT_THRESH'
    INPUT_IOU_THRESH = 'INPUT_IOU_THRESH'

    MSG_SRC = 'DeepForestPluginAlgorithm'
    MSG_INFO = 0
    BASE_URL = 'http://10.125.93.137:5000/'

    def initAlgorithm(self, config):
        """
        Here we define the inputs and output of the algorithm, along
        with some other properties.
        """

        # We add the input features source, it has to be a raster
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.INPUT,
                self.tr('Input layer'),
                optional=False
            )
        )

        # Add Tile slicing parameter for algorithm
        self.addParameter(
            QgsProcessingParameterNumber(
                self.INPUT_TILE_SLICE,
                self.tr('Tile slicing size'),
                type=QgsProcessingParameterNumber.Integer,
                defaultValue=3500,
                optional=True,
                minValue=2000,
                maxValue=15000,
            )
        )
        self.parameterDefinition(self.INPUT_TILE_SLICE).setHelp(
            'The map is cut into slices before being processed by the tree detector. ' +
            'Smaller tiles process more quickly but have more problems at the edges. ' +
            'Defaults to 3500')

        # Add Patch size parameter for algorithm
        self.addParameter(
            QgsProcessingParameterNumber(
                self.INPUT_PATCH_SIZE,
                self.tr('Patch size in pixels'),
                type=QgsProcessingParameterNumber.Integer,
                defaultValue=900,
                optional=True,
                minValue=100,
                maxValue=3000,
            )
        )
        self.parameterDefinition(self.INPUT_PATCH_SIZE).setHelp(
            'The algorithm scans for trees in a window of this size. ' +
            'It should be about equivalent to 40m in the real world. ' +
            'Defaults to 900')

        # Add Patch size parameter for algorithm
        self.addParameter(
            QgsProcessingParameterNumber(
                self.INPUT_OVERLAP,
                self.tr('Overlap between patches'),
                type=QgsProcessingParameterNumber.Double,
                defaultValue=0.4,
                optional=True,
                minValue=0.05,
                maxValue=0.95,
            )
        )
        self.parameterDefinition(self.INPUT_PATCH_SIZE).setHelp(
            'The amount of overlap between patches. ' +
            'Less overlap is quicker, but more prone to errors. ' +
            'Defaults to 0.4')

        # Add threshold parameter for algorithm
        self.addParameter(
            QgsProcessingParameterNumber(
                self.INPUT_THRESH,
                self.tr('Tree detection threshold'),
                type=QgsProcessingParameterNumber.Double,
                defaultValue=0.5,
                optional=True,
                minValue=0.05,
                maxValue=0.95,
            )
        )
        self.parameterDefinition(self.INPUT_THRESH).setHelp(
            'Below this value, a detected object will not be classified as a tree. ' +
            'Defaults to 0.5')

        # Add overlap threshold parameter for algorithm
        self.addParameter(
            QgsProcessingParameterNumber(
                self.INPUT_IOU_THRESH,
                self.tr('Overlap detection threshold'),
                type=QgsProcessingParameterNumber.Double,
                defaultValue=0.5,
                optional=True,
                minValue=0.05,
                maxValue=0.95,
            )
        )
        self.parameterDefinition(self.INPUT_IOU_THRESH).setHelp(
            'Minimum iou overlap among predictions between windows to be considered the same tree. ' +
            'Lower values suppress more boxes at edges.' +
            'Defaults to 0.5.')

        # Output parameter is a folder on the users computer
        self.addParameter(
            QgsProcessingParameterFolderDestination(
                self.OUTPUT,
                self.tr('Output folder'),
                optional=False,
            )
        )
        self.parameterDefinition(self.OUTPUT).setHelp(
            'The generated GeoJSON will be placed in this folder after processing' +
            'Make sure this folder is writable.')

    # https://github.com/geoscan/geoscan_forest
    # https://bitbucket.org/kul-reseco/localmaxfilter/src/master/localmaxfilter/interfaces/localmaxfilter_processing.py
    # https://gis.stackexchange.com/questions/282773/writing-a-python-processing-script-with-qgis-3-0
    # https://gis.stackexchange.com/questions/358230/programmatically-enable-disable-input-parameters-in-a-qgis-processing-plugin
    def processAlgorithm(self, parameters, context, feedback):
        feedback.pushInfo('Processing started')
        feedback.setProgress(0)

        session = requests.Session()
        session.headers.update({'Accept': 'application/json'})

        # get parameters
        source_layer = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        dest_folder = self.parameterAsFileOutput(parameters, self.OUTPUT, context)
        i_slice_size = self.parameterAsInt(parameters, self.INPUT_TILE_SLICE, context)
        i_patch_size = self.parameterAsInt(parameters, self.INPUT_PATCH_SIZE, context)
        i_patch_overlap = self.parameterAsDouble(parameters, self.INPUT_OVERLAP, context)
        i_thresh = self.parameterAsDouble(parameters, self.INPUT_THRESH, context)
        i_iou_thresh = self.parameterAsDouble(parameters, self.INPUT_IOU_THRESH, context)

        settings = {}
        if i_patch_size is not None:
            settings['patch_size'] = i_patch_size
        if i_patch_overlap is not None:
            settings['patch_overlap'] = i_patch_overlap
        if i_thresh is not None:
            settings['thresh'] = i_thresh
        if i_iou_thresh is not None:
            settings['iou_threshold'] = i_iou_thresh
        if bool(settings):
            headers = {'Content-Type': 'application/json'}
            resp = session.post(self.BASE_URL + 'settings',
                                headers=headers,
                                data=json.dumps(settings),
                                cookies={'session': 'deepforest_plugin'})
            if resp.status_code == 200:
                feedback.pushInfo('Applied custom settings: {}'.format(settings))
            else:
                feedback.pushInfo('Could not apply settings: {}'.format(settings))

        sl_rect = source_layer.extent()  # use to transform coordinates
        raster_layer = QgsRasterLayer(source_layer.source())
        crs = raster_layer.crs().authid()

        feedback.pushInfo('Tree detection window size: {}'.format(i_patch_size))

        feedback.pushInfo('Layer: ' + str(source_layer))
        feedback.pushInfo('CRS: {}'.format(crs))
        feedback.pushInfo('Extent: x:{:.2f} y:{:.2f} w:{:.2f} h:{:.2f}'
                          .format(sl_rect.xMinimum(), sl_rect.yMinimum(), sl_rect.width(), sl_rect.height()))
        feedback.pushInfo('Dimensions: {} x {}'.format(source_layer.width(), source_layer.height()))

        source_provider = source_layer.dataProvider()
        ds_uri = str(source_provider.dataSourceUri())
        ds = gdal.Open(ds_uri)
        feedback.pushInfo('RasterCount: {} bands'.format(ds.RasterCount))

        arr_1 = ds.GetRasterBand(1).ReadAsArray()
        arr_2 = ds.GetRasterBand(2).ReadAsArray()
        arr_3 = ds.GetRasterBand(3).ReadAsArray()
        three_band = np.array([arr_1, arr_2, arr_3])
        three_band = np.transpose(three_band, (1, 2, 0))
        feedback.pushInfo('Image (W,H,D): ' + str(three_band.shape))
        feedback.pushInfo('Destination folder: {}'.format(dest_folder))

        slicing = i_slice_size

        # if three_band.shape[0] > slicing * 1.1 and three_band.shape[1] > slicing * 1.1:
        sl_height = three_band.shape[0]
        sl_width = three_band.shape[1]
        part_count_v = math.ceil(sl_height / slicing)
        part_count_h = math.ceil(sl_width / slicing)
        slice_v = math.ceil(sl_height / part_count_v)
        slice_h = math.ceil(sl_width / part_count_h)

        feedback.pushInfo('Slice size: {} x {}'.format(slice_v, slice_h))

        total = part_count_v * part_count_h
        count = 0
        feature_list = []

        for y0 in range(0, sl_height, slice_v):
            if feedback.isCanceled():
                break
            for x0 in range(0, sl_width, slice_h):
                if feedback.isCanceled():
                    break
                y_max = y0 + slice_v
                x_max = x0 + slice_h
                part = three_band[y0:y_max, x0:x_max, 0:3]
                img = Image.fromarray(part, 'RGB')
                img_file_name = dest_folder + '/part_' + str(y_max) + '_' + str(x_max) + '.jpg'
                img.save(img_file_name, quality=90, optimize=True, subsampling=0)

                with open(img_file_name, 'rb') as img_file:
                    files = {'file': img_file}
                    resp = session.post(self.BASE_URL + 'tree_rects',
                                        files=files,
                                        cookies={'session': 'deepforest_plugin'})

                    if resp.status_code == 200:
                        str_content = resp.content.decode('utf-8')
                        json_boxes = json.loads(str_content)

                        for b in range(0, len(json_boxes)):
                            # transform these coordinates using extent
                            xmin = (x0 + json_boxes[b]['xmin']) / sl_width
                            xmin = sl_rect.xMinimum() + (xmin * sl_rect.width())
                            xmax = (x0 + json_boxes[b]['xmax']) / sl_width
                            xmax = sl_rect.xMinimum() + (xmax * sl_rect.width())

                            # QGIS uses 0.0 at BOTTOM left corner instead of top!
                            ymin = 1 - (y0 + json_boxes[b]['ymin']) / sl_height
                            ymin = sl_rect.yMinimum() + (ymin * sl_rect.height())
                            ymax = 1 - (y0 + json_boxes[b]['ymax']) / sl_height
                            ymax = sl_rect.yMinimum() + (ymax * sl_rect.height())

                            properties = {
                                'stroke': '#00ff00',
                                'stroke-width': 1,
                                'fill': '#00ff00',
                                'fill-opacity': 0.5
                            }

                            properties.update(json_boxes[b])

                            feature = {
                                "type": "Feature",
                                "geometry": {
                                    "type": "Polygon",
                                    "coordinates": [[
                                        [xmin, ymin],
                                        [xmin, ymax],
                                        [xmax, ymax],
                                        [xmax, ymin],
                                        [xmin, ymin]
                                    ]]
                                },
                                "properties": properties
                            }
                            feature_list.append(feature)
                    else:
                        feedback.pushInfo('Error: {}'.format(resp.status_code))

                count = count + 1
                feedback.pushInfo('Processed part: {}/{}'.format(count, total))

                feedback.setProgress(int(count / total * 100))

        # write to file
        current_datetime = datetime.datetime.now()
        output_file_name = dest_folder + '/trees_' + current_datetime.strftime("%Y_%m_%d_%H_%M") + '.geojson'
        with open(output_file_name, 'wt') as out_file:
            geo_json = {
                'type': 'FeatureCollection',
                'features': feature_list,
                'crs': {
                    'type': 'name',
                    'properties': {
                        'name': crs
                    }
                }
            }
            out_file.write(json.dumps(geo_json, indent=1))
        feedback.pushInfo('Written {}'.format(output_file_name))
        feedback.setProgress(1)

        # TODO: return as output
        # (sink, dest_id) = self.parameterAsRasterLayer(parameters, self.OUTPUT, context, None, None, None)
        #     # Add a feature in the sink
        #     sink.addFeature(feature, QgsFeatureSink.FastInsert)

        return {self.OUTPUT: None}

    def icon(self):
        return QIcon(':/plugins/deepforestplugin/icon.png')

    def name(self):
        """
        Returns the algorithm name, used for identifying the algorithm. This
        string should be fixed for the algorithm, and must not be localised.
        The name should be unique within each provider. Names should contain
        lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'Detect Trees'

    def displayName(self):
        """
        Returns the translated algorithm name, which should be used for any
        user-visible display of the algorithm name.
        """
        return self.tr(self.name())

    def group(self):
        """
        Returns the name of the group this algorithm belongs to. This string
        should be localised.
        """
        return self.tr(self.groupId())

    def groupId(self):
        """
        Returns the unique ID of the group this algorithm belongs to. This
        string should be fixed for the algorithm, and must not be localised.
        The group id should be unique within each provider. Group id should
        contain lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return ''

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return DeepForestPluginAlgorithm()
