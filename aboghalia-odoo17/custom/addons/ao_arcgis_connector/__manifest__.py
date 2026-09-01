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

{
    'name': 'Arcgis Connector',
    'version': '17.0.1.0.10',
    'category': 'Customization',
    'summary': 'Connecting With Arcgis',
    'description': 'Connecting With Arcgis',
    'author': 'Ahmed Osama',
    'website': "https://www.mdarj.org",
    'company': 'Mdarj',
    'maintainer': 'Mdarj',
    'depends': ['base','project'],
    'data': [
        'views/ao_arcgis_views.xml',

    ],
    'assets': {
        'web.assets_backend': [
            'ao_arcgis_connector/static/src/js/arcgis_dashboard.js',
            'ao_arcgis_connector/static/src/xml/arcgis_dashboard.xml',
        ],
    },
    'license': 'LGPL-3',
    'installable': True,
}
