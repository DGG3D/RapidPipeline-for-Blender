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
"""  # noqa: N999

import os

import bpy  # type: ignore

from .run_rpde import RunPipeline

cad_output_path = os.path.join(os.environ["RPDP_PROCESSOR_DCC_DATA"], "CAD_import")

class CADImportOperator(bpy.types.Operator):
    bl_idname = "processor.cad_import"
    bl_description = "Import CAD Model"
    bl_label = "Import CAD Model"
    bl_options = {'REGISTER', 'UNDO'}

    filepath: bpy.props.StringProperty(subtype='FILE_PATH') # type: ignore

    # Define a function to trigger the file browser
    def invoke(self, context:bpy.types.Context, event:bpy.types.Event) -> set[str]:
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context:bpy.types.Context) -> set[str]:
        print("execute CAD Import")
        print(self.filepath)
        _ = convertCADFile(self.filepath)
        return {'FINISHED'}


def convertCADFile(filepath:str) -> str:
    out_path = os.path.join(cad_output_path, "output", "cad_converted.glb")
    #TODO check if CAD file was selected
    dirname = os.path.dirname(__file__)
    rpde_settings = os.path.join(dirname, 'resources', "CAD_import", "rpdp_dcc_plugin_cad_settings.json")
    if not rpde_settings:
        raise Exception("Could not load RPDE CAD settings file.")

    output_folder = os.environ["RPDP_PROCESSOR_DCC_DATA"]
    execution_folder = os.path.join(output_folder)
    file_path = os.path.join(execution_folder)
    # unselect everything
    for o in list(bpy.data.objects):
        o.select_set(False)
    RunPipeline.runPipeline(filepath, rpde_settings, file_path, copied_nodes=None)
    return out_path

clss = (
    CADImportOperator,
)

register, unregister = bpy.utils.register_classes_factory(clss)
