# -*- coding: utf-8 -*-
"""
/***************************************************************************
 ZonalExactDialog
                                 A QGIS plugin
 Zonal Statistics of rasters using Exact Extract library
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                             -------------------
        begin                : 2024-02-11
        git sha              : $Format:%H$
        copyright            : (C) 2024 by Jakub Charyton
        email                : jakub.charyton@gmail.com
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

import os
import time
from typing import List

from qgis.PyQt import uic
from qgis.PyQt import QtWidgets
from qgis.core import QgsMapLayerProxyModel, QgsTask, QgsApplication, QgsTaskManager, QgsMessageLog

import geopandas as gpd
from exactextract import exact_extract

from .dialog_input_dto import DialogInputDTO
from .user_communication import UserCommunication

# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'zonal_exact_dialog_base.ui'))


class ZonalExactDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, parent=None, uc: UserCommunication = None, iface = None, task_manager: QgsTaskManager = None):
        """Constructor."""
        super(ZonalExactDialog, self).__init__(parent)
        # Set up the user interface from Designer through FORM_CLASS.
        # After self.setupUi() you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.dialog_input: DialogInputDTO = None
        self.tasks = []
        self.uc = uc
        self.iface = iface
        self.task_manager: QgsTaskManager = task_manager
        
        self.calculated_stats_list = []
        
        self.setupUi(self)
        
        self.mRasterLayerComboBox.setFilters(QgsMapLayerProxyModel.RasterLayer)
        self.mVectorLayerComboBox.setFilters(QgsMapLayerProxyModel.VectorLayer)
        
        self.mCalculateButton.clicked.connect(self.calculate)

    def calculate(self):
        self.get_input_values()
        if self.dialog_input is None:
            return
        vector_gdf = gpd.read_file(self.dialog_input.vector_layer_path, layer=self.dialog_input.input_layername, engine='pyogrio').reset_index().rename(columns={"index":"id"}).astype({'id':'int32'})
        batch_size = round(len(vector_gdf) / self.dialog_input.parallel_jobs)
        
        self.tasks = []
        for i in range(self.dialog_input.parallel_jobs):
            temp_vector_gdf = vector_gdf[i:i + batch_size]
            # task_temp = QgsTask.fromFunction(f'task_{i}', self.calculate_stats, on_finished=self.calculated_stats, 
            #                                 polygon_layer_gdf=temp_vector_gdf, raster=self.dialog_input.raster_layer_path,
            #                                 stats=self.dialog_input.aggregates_stats_list+self.dialog_input.arrays_stats_list, 
            #                                 include_cols=['id'], index_column='id', prefix='test_prefix_')
            
            # task_temp = QgsTask.fromFunction(f'task_{i}', self.calculate, on_finished=self.calculation_finished)
            
            t1 = MyTask(f'waste cpu {i}', QgsTask.CanCancel)
            self.tasks.append(t1)

            self.task_manager.addTask(t1)
        
        self.task_manager.allTasksFinished.connect(self.postprocess)
        pass
    
    def postprocess(self):
        for i in range(self.dialog_input.parallel_jobs):
            self.uc.bar_info(self.tasks[i].result)
    
    def calculate_stats(self, polygon_layer_gdf: gpd.GeoDataFrame, raster: str, stats: List[str], include_cols=['id'],
                        index_column: str='id', prefix: str=''):
        print("started calculating")
        result_stats = exact_extract(vec=polygon_layer_gdf, rast=raster, ops=stats, include_cols=include_cols, output="pandas")
        
        return result_stats
    
    def calculated_stats(self, state: bool, description: str, failed_features: int, exception: object):
        if exception is None:
            if result is None:
                print('No data')
            else:
                print("calculated")
                self.calculated_stats_list.append(result)
        
    
    def get_input_values(self):
        raster_layer_path, vector_layer_path = self.get_files_paths()
        parallel_jobs = self.mSpinBox.value()
        output_file_path = self.mQgsOutputFileWidget.filePath()
        aggregates_stats_list = self.mAggregatesComboBox.checkedItems()
        arrays_stats_list = self.mArraysComboBox.checkedItems()
        
        # check if both stats lists are empty
        if not aggregates_stats_list and not arrays_stats_list:
            self.uc.bar_warn(f"You didn't select anything from either Aggregates and Arrays")
            return
        
        self.dialog_input = DialogInputDTO(raster_layer_path, vector_layer_path, parallel_jobs, output_file_path,
                                           aggregates_stats_list, arrays_stats_list)
    
    def get_files_paths(self):
        raster_layer_path = self.mRasterLayerComboBox.currentLayer().dataProvider().dataSourceUri()
        vector_layer_path = self.mVectorLayerComboBox.currentLayer().dataProvider().dataSourceUri()

        return raster_layer_path, vector_layer_path

class MyTask(QgsTask):
    
    def __init__(self, description, flags):
        super().__init__(description, flags)
        self.result = None
        self.description = description
    
    def run(self):
        QgsMessageLog.logMessage('Started task {}'.format(self.description))
        print('crashandburn')
        self.setProgress(20)
        time.sleep(3)
        self.setProgress(40)
        time.sleep(3)
        self.setProgress(100)
        self.result = self.description + ' is done!'
        
        return True
    


class CalculateStatsTask(QgsTask):
    def __init__(self, description, flags, polygon_layer_gdf, raster, stats, include_cols):
        super().__init__(description, flags)
        self.polygon_layer_gdf = polygon_layer_gdf
        self.raster = raster
        self.stats = stats
        self.include_cols = include_cols
        
        self.result_stats = None
    
    def run(self):
        QgsMessageLog.logMessage('Started task {}'.format(self.description()))
        
        print("started calculating")
        result_stats = exact_extract(vec=self.polygon_layer_gdf, rast=self.raster, ops=self.stats, include_cols=self.include_cols, output="pandas")
        
        
    def finished():
        pass
        