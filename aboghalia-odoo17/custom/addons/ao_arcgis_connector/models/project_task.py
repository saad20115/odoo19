# -*- coding: utf-8 -*-
#############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2022-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Cybrosys Techno Solutions(<https://www.cybrosys.com>)
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
from odoo import models, fields, api
import logging
import requests
_logger = logging.getLogger('ArcGIS Projects')

class ProjectTask(models.Model):
    _inherit = 'project.task'

    objectId = fields.Integer('Object Id')
    uniqueId = fields.Integer('Unique Id')
    globalId = fields.Char('Global Id')
    x_axis = fields.Float('الإحداثي X')
    y_axis = fields.Float('الإحداثي Y')
    
    def create(self, vals):
        res = super(ProjectTask, self).create(vals)
        response = requests.get("https://www.arcgis.com/sharing/generateToken?f=json&username=HajjConsultant2&password=HajjConsultant2@&referer=https://www.arcgis.com")
        token = response.json()['token']
        url = "https://services9.arcgis.com/extZYdQc4t6K94Yj/arcgis/rest/services/survey123_87d445fe6dbe4c669e236f5f183d4f15_form/FeatureServer/0/addFeatures?f=json&token=" + str(token)
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = '''features=[
                    {
                        "attributes" : {
                        "field_1" : 508389''' + ''',
                        },
                        "geometry" : {
                                        "x" : ''' + res.x_axis + ''',
                                        "y" : ''' + res.y_axis + '''
                                     }
                    }
                    ]'''
        response = requests.post(url, headers=headers, data=data)
        vals = response.json()
        res.objectId = vals['addResults'][0]['objectId']
        res.uniqueId = vals['addResults'][0]['uniqueId']
        res.globalId = vals['addResults'][0]['globalId']

        _logger.info(response.json())






        [

]