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
 This script initializes the plugin, making it known to QGIS.
"""

__author__ = 'PXL Smart ICT'
__date__ = '2023-02-21'
__copyright__ = '(C) 2023 by PXL Smart ICT'


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load DeepForestPlugin class from file DeepForestPlugin.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .DeepForestPlugin import DeepForestPluginPlugin
    return DeepForestPluginPlugin()
