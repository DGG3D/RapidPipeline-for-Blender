"""
The RapidPipeline 3D Processor Plugin for Blender
Copyright 2024, Darmstadt Graphics Group GmbH <info@dgg3d.com>
Licensed under GNU GPL-3.0-or-later.

This file is part of The RapidPipeline 3D Processor Plugin for Blender.
The RapidPipeline 3D Processor Plugin for Blender is free software:
you can redistribute it and/or modify it under the terms of the GNU
General Public License as published by the Free Software Foundation,
either version 3 of the License, or (at your option) any later version.

The RapidPipeline 3D Processor Plugin for Blender is distributed in
the hope that it will be useful, but WITHOUT ANY WARRANTY; without even
the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
See the GNU General Public License (under licenses/processorpluginblender.txt)
for more details.

You should have received a copy of the GNU General Public License
along with The RapidPipeline 3D Processor Plugin for Blender. If not,
see <https://www.gnu.org/licenses/>.

Note that the RapidPipeline 3D Processor Engine CLI ("rpde") is a copyrighted
software governed by its own EULA. The RapidPipeline 3D Processor Engine CLI
does NOT make use of the 3D Processor Plugin For Blender and does NOT follow
the GNU GPL-3.0 license. See the RapidPipeline 3D Processor EULA file (under
rpde/EULA_RapidPipelineEngine.rtf after installation, or during the install
process) for further information.
"""

import os
import textwrap

import bpy  # type: ignore

from .gui_commons import parseTextFile
from .license_manager import OpenLinkOperator


class OverrideTokenOperator(bpy.types.Operator):
    bl_idname = "processor.override_token"
    bl_description = "Override API Token"
    bl_label = "Override API Token"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context:bpy.types.Context) -> set[str]:
        bpy.types.Scene.has_license = False
        bpy.types.Scene.override_token = True
        return {'FINISHED'}


class AboutDialogPanel(bpy.types.Panel):
    bl_label = "About"
    bl_idname = "OBJECT_PT_About"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "RapidPipeline"
    bl_parent_id = "VIEW3D_PT_RapidPipeline"
    bl_options = {'HIDE_HEADER'}

    licenses: bpy.props.StringProperty() # type: ignore

    #https://blender.stackexchange.com/questions/74052/wrap-text-within-a-panel
    def prettyPrintLicense(self, text:str, context:bpy.types.Context):
        for area in bpy.context.screen.areas:
            if area.type == 'VIEW_3D':
                break
        for region in area.regions:
            if region.type == 'UI':
                panel_width = region.width
                break

        # Calculate the maximum width of the label
        uifontscale = 9 * context.preferences.view.ui_scale
        max_label_width = int(panel_width // uifontscale)

        # Split the text into lines and format each line
        for line in text.splitlines():
            # Remove leading and trailing whitespace
            line = line.strip()

            # Split the line into chunks that fit within the maximum label width
            for chunk in textwrap.wrap(line, width=max_label_width):
                self.layout.label(text=chunk)

    def draw(self, context:bpy.types.Context):
        layout = self.layout
        panel_layout = layout.row()

        panel_layout.operator(OverrideTokenOperator.bl_idname, text="Override CLI API Token")
        panel_layout = layout.row()
        op = panel_layout.operator(OpenLinkOperator.bl_idname, text="Terms and Conditions", icon='URL')
        op.url = "https://rapidpipeline.com/en/general-terms-and-conditions"
        self.prettyPrintLicense(bpy.context.scene.licenses, context)

    @classmethod
    def poll(cls, context:bpy.types.Context) -> bool:
        return bpy.context.scene.aboutdialog and not context.scene.rpde_running and context.scene.has_license

class AboutDialog(bpy.types.Operator):
    bl_idname = "processor.about_dialog"
    bl_description = "Override API Token and see copyright disclaimer"
    bl_label = "About"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context:bpy.types.Context) -> set[str]:
        if not bpy.context.scene.aboutdialog:
            bpy.context.scene.aboutdialog = True
        else:
            bpy.context.scene.aboutdialog = False

        license_disclaimer = """
        Copyright 2025, Darmstadt Graphics Group GmbH <info@dgg3d.com>
        Licensed under GNU GPL-3.0-or-later (see below for details).
        """
        bpy.context.scene.licenses = license_disclaimer

        # add license disclaimer

        oss_licenses_folder = os.path.join(os.path.dirname(__file__), "licenses")
        plugin_full_name = "The RapidPipeline 3D Processor Plugin For Blender"

        self.addOSSLicense(plugin_full_name, os.path.join(oss_licenses_folder, "processorpluginblender.txt"))
        self.addOSSLicense("Tabler Icons", os.path.join(oss_licenses_folder, "tabler.txt"))
        return {'FINISHED'}


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        return

    def addOSSLicense(self, license_name: str, license_file: str):
        """
        Appends an extra Open Source Software license to our list of licenses.
        """
        license_text = f"------------ {license_name} License ------------"
        license_text += "".join(parseTextFile(license_file)) + "\n"

        bpy.context.scene.licenses += license_text

clss = (
    AboutDialog, OverrideTokenOperator, OpenLinkOperator,
)

register, unregister = bpy.utils.register_classes_factory(clss)

