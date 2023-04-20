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
from PIL import Image
from osgeo import gdal
from qgis.PyQt.QtCore import QCoreApplication
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

    def initAlgorithm(self, config):
        """
        Here we define the inputs and output of the algorithm, along
        with some other properties.
        """

        # We add the input vector features source. It can have any kind of
        # geometry.
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.INPUT,
                self.tr('Input layer'),
                None,
                False
            )
        )

        # Add window parameter for algorithm
        self.addParameter(
            QgsProcessingParameterNumber(
                self.INPUT_LIMIT,
                self.tr('Window size in pixels (should be about 40m)'),
                type=QgsProcessingParameterNumber.Integer,
                defaultValue=600,
                optional=False,
                minValue=0,
                maxValue=10000,
            )
        )

        # We add a feature sink in which to store our processed features (this
        # usually takes the form of a newly created vector layer when the
        # algorithm is run in QGIS).
        self.addParameter(
            QgsProcessingParameterFolderDestination(
                self.OUTPUT,
                self.tr('Output folder'),
                optional=False,
                # fileFilter='Image files (*.png)'
                # fileFilter='GeoJSON files (*.json)'
            )
        )

    # https://github.com/geoscan/geoscan_forest
    # https://bitbucket.org/kul-reseco/localmaxfilter/src/master/localmaxfilter/interfaces/localmaxfilter_processing.py
    # https://gis.stackexchange.com/questions/282773/writing-a-python-processing-script-with-qgis-3-0
    # https://gis.stackexchange.com/questions/358230/programmatically-enable-disable-input-parameters-in-a-qgis-processing-plugin
    def processAlgorithm(self, parameters, context, feedback):
        """
        Here is where the processing itself takes place.
        """

        print('processAlgorithm')
        feedback.setProgress(0)
        # Retrieve the feature source and sink. The 'dest_id' variable is used
        # to uniquely identify the feature sink, and must be included in the
        # dictionary returned by the processAlgorithm function.

        source_layer = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        window_size = self.parameterAsInt(parameters, self.INPUT_LIMIT, context)
        dest_file = self.parameterAsFileOutput(parameters, self.OUTPUT, context)
        sl_rect = source_layer.extent()  # use to transform coordinates
        raster_layer = QgsRasterLayer(source_layer.source())
        crs = raster_layer.crs().authid()

        print('Window size: ', window_size)

        print('Layer: ' + str(source_layer))
        print('Extent: ', sl_rect.xMinimum(), sl_rect.yMinimum(), sl_rect.width(), sl_rect.height())
        print('CRS: ', crs)
        print('Dimensions: ', source_layer.width(), ' x ', source_layer.height())

        source_provider = source_layer.dataProvider()
        ds_uri = str(source_provider.dataSourceUri())
        ds = gdal.Open(ds_uri)
        print('RasterCount  ', ds.RasterCount, ' bands')

        arr_1 = ds.GetRasterBand(1).ReadAsArray()
        arr_2 = ds.GetRasterBand(2).ReadAsArray()
        arr_3 = ds.GetRasterBand(3).ReadAsArray()
        three_band = np.array([arr_1, arr_2, arr_3])
        three_band = np.transpose(three_band, (1, 2, 0))
        print('Image (W,H,D): ' + str(three_band.shape))
        print('Destination file: ', dest_file)

        slicing = 3500

        # if three_band.shape[0] > slicing * 1.1 and three_band.shape[1] > slicing * 1.1:
        sl_height = three_band.shape[0]
        sl_width = three_band.shape[1]
        part_count_v = math.ceil(sl_height / slicing)
        part_count_h = math.ceil(sl_width / slicing)
        slice_v = math.ceil(sl_height / part_count_v)
        slice_h = math.ceil(sl_width / part_count_h)

        print('Slice size: ', slice_v, ' by ', slice_h)

        total = part_count_v * part_count_h
        count = 0
        feature_list = []

        for y0 in range(0, sl_height, slice_v):
            for x0 in range(0, sl_width, slice_h):
                if feedback.isCanceled():
                    break
                y_max = y0 + slice_v
                x_max = x0 + slice_h
                part = three_band[y0:y_max, x0:x_max, 0:3]
                img = Image.fromarray(part, 'RGB')
                img_file_name = dest_file + '/part_' + str(y_max) + '_' + str(x_max) + '.jpg'
                img.save(img_file_name, quality=90, optimize=True, subsampling=0)

                with open(img_file_name, 'rb') as img_file:
                    files = {'file': img_file}
                    resp = requests.post('http://10.125.93.137:5000/tree_rects', files=files)
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
                                "properties": json_boxes[b]
                            }
                            feature_list.append(feature)
                        # break  # TODO: remove
                    else:
                        print('Error: ', resp.status_code)

                count = count + 1
                print('Processed part: ', count, ' / ', total)

                feedback.setProgress(int(count / total * 100))
            break  # TODO: remove

        # write to file
        current_datetime = datetime.datetime.now()
        output_file_name = dest_file + '/trees_' + current_datetime.strftime("%Y_%m_%d_%H_%M") + '.geojson'
        with open(output_file_name, 'wt') as out_file:
            geo_json = {
                'type': 'FeatureCollection',
                'features': feature_list,
                'crs': {
                    "type": "name",
                    "properties": {
                        "name": crs
                    }
                }
            }
            out_file.write(json.dumps(geo_json, indent=1))
        print('Written ', output_file_name)

        # TODO: return as output
        # (sink, dest_id) = self.parameterAsRasterLayer(parameters, self.OUTPUT, context, None, None, None)
        #     # Add a feature in the sink
        #     sink.addFeature(feature, QgsFeatureSink.FastInsert)

        return {self.OUTPUT: None}

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
