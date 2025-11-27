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
from typing import Any

import bpy  # type: ignore
import bpy_extras  # type: ignore

from .json_utils import JSonUtils
from .run_rpde import RunPipeline

cad_output_path = os.path.join(os.environ["RPDP_PROCESSOR_DCC_DATA"], "CAD_import")

class CADImportFileOperator(bpy.types.Operator, bpy_extras.io_utils.ImportHelper):
    bl_idname = "processor.cad_file_import"
    bl_description = "Import CAD Model"
    bl_label = "Import CAD File"

    #filter for supported cad files
    #NOTE needs to use some wildcards due to problems with filter_glob fuction
    # only char length of 255 are supported? (as shown in blender source code)
    # described here: https://app.clickup.com/t/86c3f3zpk
    supported_cad_ext_short = [".*3d*", ".3mf", ".arc", ".asm",
                         ".cat*", ".cgr", ".dae", ".dgn", ".dlv", ".d*f*", ".dwg",
                         ".exp", ".iam", ".ifc*", ".ig*", ".ipt", ".jt", ".mf1", ".mod*", ".nwd",
                         ".neu", ".par", ".pkg", ".prc", ".prt", ".psm", ".pwd", ".rfa", ".rvt", ".sa*",
                         ".ses*", ".sld*", ".st*p*", ".unv", ".vda", ".vmrl", ".wrl", ".x_*", ".xas", ".xmt*", ".xpr"]
    default_string = "*" + ";*".join(supported_cad_ext_short)

    filter_glob: bpy.props.StringProperty(
        default= default_string,
        options={'HIDDEN'}
    ) # type: ignore

    enum_options = []
    enum_options.append(("coarse",)*3)
    enum_options.append(("medium",)*3)
    enum_options.append(("fine",)*3)


    tessellation_resolution: bpy.props.EnumProperty(
        name="Tessellation Resolution",
        items=enum_options,
        description="Tessellation resolution for imported CAD surfaces",
        default=enum_options[0][0]
    ) #type: ignore

    remove_t_junctions: bpy.props.BoolProperty(
        name="Remove T-Junctions",
        description= "Attempts to remove T-Junctions after CAD tessellation (experimental)",
        default=False
    ) # type: ignore

    sew_tolerance: bpy.props.FloatProperty(
        name="CAD Sewing Tolerance",
        description= "Tolerance for the sewing operation on the b-reps before tessellation",
        default=0.0,
        min= 0.0,
        max= 1.7976931348623157e+308
    ) # type: ignore

    def execute(self, context:bpy.types.Context) -> set:
        if not os.path.isfile(self.filepath):
            self.report({'WARNING'}, "No file selected...")
            return {'FINISHED'}

        self.report({'INFO'}, "Importing CAD file...")

        # writing cad import settings based on selected tessellation resolution:
        cad_import_path = os.path.join(os.path.dirname(__file__), 'resources', "CAD_import")
        rpde_settings = os.path.join(cad_import_path, "rpdp_dcc_plugin_cad_settings.json")
        cad_settings_json = JSonUtils.loadJSON(rpde_settings)

        if cad_settings_json.get("import", {}).get("CAD", {}).get("tessellationResolution", ""):
            cad_settings_json["import"]["CAD"]["tessellationResolution"] = self.tessellation_resolution
            cad_settings_json["import"]["CAD"]["removeTJunctions"] = self.remove_t_junctions
            cad_settings_json["import"]["CAD"]["sewTolerance"] = self.sew_tolerance

        rpde_settings_tmp = os.path.join(cad_import_path, "rpdp_dcc_plugin_cad_settings_tmp.json")

        if JSonUtils.saveJSON(cad_settings_json, rpde_settings_tmp):
            _ = convertCADFile(self.filepath, rpde_settings_tmp)
        else:
            print("Warning: could not set CAD import settings. Using default...")
            _ = convertCADFile(self.filepath, rpde_settings)

        return {'FINISHED'}


def convertCADFile(filepath:str, rpde_settings_path:str) -> str:
    out_path = os.path.join(cad_output_path, "output", "cad_converted.glb")
    #TODO check if CAD file was selected
    if not rpde_settings_path:
        raise Exception("Could not load RPDE CAD settings file.")

    output_folder = os.environ["RPDP_PROCESSOR_DCC_DATA"]
    execution_folder = os.path.join(output_folder)
    file_path = os.path.join(execution_folder)
    # unselect everything
    for o in list(bpy.data.objects):
        o.select_set(False)
    RunPipeline.runPipeline(filepath, rpde_settings_path, file_path, copied_nodes=None)
    return out_path

def menu_func_import(self:Any, context:bpy.types.Context):
    self.layout.operator(CADImportFileOperator.bl_idname, text="RapidPipeline CAD Import")

clss = (
    CADImportFileOperator,
)

def register():
    reg()
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

def unregister():
    unreg()
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)

reg, unreg = bpy.utils.register_classes_factory(clss)
