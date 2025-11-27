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
import pathlib
import textwrap
from typing import Any

import bpy
import bpy_extras

from .magic_actions_operator import MagicAction, MagicActionOperator, get_export_actions, get_magic_actions, get_version
from .scene_utils import blend_create_prop, blend_scene_getattr

global_export_ext = ""
global_export_path = ""



#https://blender.stackexchange.com/questions/74052/wrap-text-within-a-panel
def prettyPrint(main_layout:Any ,text:str, context:bpy.types.Context):
    panel_width = context.region.width

    # Calculate the maximum width of the label
    uifontscale = 9 * context.preferences.view.ui_scale
    max_label_width = int(panel_width // uifontscale)

    # Split the text into lines and format each line
    for line in text.splitlines():
        # Remove leading and trailing whitespace
        line = line.strip()

        # Split the line into chunks that fit within the maximum label width
        for chunk in textwrap.wrap(line, width=max_label_width):
            main_layout = main_layout.column()
            main_layout.label(text=chunk)

class ExportFileOperator(bpy.types.Operator, bpy_extras.io_utils.ExportHelper):
    bl_idname = "processor.file_export_operator"
    bl_description = "Export 3D Model"
    bl_label = "Export File"

    filename_ext = global_export_ext
    export_actions:list[MagicAction] = get_export_actions()

    def invoke(self, context, event):
        # select first export action
        for action in self.export_actions:
            if self.filename_ext.split(".")[-1] in action.action_name:
                bpy.ops.processor.magic_action_button(magic_action_str=action.action_name)
                return super().invoke(context, event)
        return super().invoke(context, event)


    def cancel(self, context):
        # select first magic action
        magic_actions_sorted:list[MagicAction] = get_magic_actions()
        first_magic_action = magic_actions_sorted[0].action_name
        bpy.ops.processor.magic_action_button(magic_action_str=first_magic_action)
        return None

    def draw(self, context):
        layout = self.layout
        selected_magic_action_str = context.scene.rpde_selected_action
        selection = "Choose a Magic Action"

        from .main_widget import preview_collections
        pcoll = preview_collections["main"]
        magic_action_placeholder = pcoll.get("Magic_action_placeholder", None)
        version = get_version()
        button_layout = layout
        main_magic_layout = layout
        selected_magic_action = None

        for magic_action in self.export_actions:
            if self.filename_ext.split(".")[-1] in magic_action.action_name:
                op:MagicActionOperator = button_layout.operator(
                    MagicActionOperator.bl_idname,
                    text=magic_action.action_name,
                    icon_value=getattr(
                        context.scene, f"magic_action_{version}_{os.path.basename(magic_action.path)}").icon_id,
                        depress=selected_magic_action_str == magic_action.action_name)
                action_name = magic_action.action_name
                op.magic_action_str = action_name

                selected_magic_action = magic_action

        if selected_magic_action_str:
            selection = selected_magic_action_str

        magic_layout = main_magic_layout.row()
        if selection != "Choose a Magic Action":
            magic_layout.label(text=f"{selection}")
            magic_layout = main_magic_layout.row()
            magic_layout = main_magic_layout.row()
            if context.scene.rpde_enable_preview:
                action_image_str = f"magic_action_image_{version}_{os.path.basename(magic_action.path)}"
                if action_image_str in pcoll:
                    magic_layout.template_icon(icon_value=pcoll[
                        action_image_str].icon_id, scale=5.0)
                    magic_layout.separator()
                else:
                    if magic_action_placeholder:
                        magic_layout.template_icon(icon_value=magic_action_placeholder.icon_id, scale=5.0)
                    else:
                        magic_layout.label(text="Image not loaded")
            if context.scene.rpde_enable_description:
                #description of magic action
                if selected_magic_action:
                    prettyPrint(magic_layout, selected_magic_action.action_description, context)
                else:
                    magic_layout.label(text="Warning: Could not find Magic Action description")
            magic_layout = main_magic_layout.row()
            box_layout = magic_layout.box()
            sub = box_layout.row()
            if selected_magic_action.action_options:
                for option in selected_magic_action.action_options:
                    sub = sub.split(factor=0.33)
                    left_col = sub.column(align=True)
                    left_col.alignment  = 'RIGHT'
                    right_col = sub.column(align=True)
                    attribute_env, attribute = blend_scene_getattr(
                        context.scene, path=option.option_path)

                    option_name = option.option_name if option.option_name else option.get_option_ui_element().title
                    left_col.label(text=option_name)
                    blend_create_prop(right_col, attribute_env, attribute, name="")
                    sub = box_layout.row()
            else:
                pass
                #print(f"Warning, could not find options for MagicAction: {selected_magic_action.action_name}")
        else:
            magic_layout = main_magic_layout.row()
            warning_msg = "Please choose an action above"
            magic_layout.label(text=warning_msg, icon='ERROR')

    def execute(self, context):
        if not self.filepath:
            self.report({'WARNING'}, "No file selected...")
            return {'FINISHED'}

        self.report({'INFO'}, "Exporting 3D file...")
        _ = export_file(self.filepath)
        return {'FINISHED'}

def export_file(filepath:str, ) -> str:
#    file_path = os.path.join(os.environ["RPDP_PROCESSOR_DCC_DATA"])

    # unselect everything
    for o in list(bpy.data.objects):
        o.select_set(False)

    global global_export_ext
    global_export_ext = pathlib.Path(filepath).suffix[1:]

    global global_export_path
    global_export_path = os.path.join(os.path.dirname(filepath), pathlib.Path(filepath).stem)

    bpy.types.Scene.rpde_export = True
    print("start rpde export")
    bpy.ops.processor.run()

    return None

class ExportMenu(bpy.types.Menu):
    bl_label = "Export Menu"
    bl_idname = "PROCESSOR_MT_export_menu"

    def draw(self, context):
        supported_classes = [ExportCTM, ExportFBX, ExportGLB, ExportGLTF, ExportOBJ, ExportPLY, ExportSTL, ExportUSD,
                            ExportUSDA, ExportUSDC, ExportUSDZ]
        layout = self.layout
#        layout.operator(ExportWrapper.bl_idname, text="wrapper test")
        for classes in supported_classes:
            layout.operator(classes.bl_idname, text=classes.filetype)


class ShowExportMenu(bpy.types.Operator):
    bl_label = "Show Export Menu"
    bl_idname = "processor.show_export_menu"
    bl_description = "Export 3D Model"

    def execute(self, context):
        bpy.ops.wm.call_menu(name=ExportMenu.bl_idname)
        return {'FINISHED'}

class ExportCTM(bpy.types.Operator):
    bl_idname = "processor.export_ctm"
    bl_label = "Start Export"
    filetype = ".ctm"

    def execute(self, context):
        return call_export_file_picker(self, context)

class ExportFBX(bpy.types.Operator):
    bl_idname = "processor.export_fbx"
    bl_label = "Start Export"
    filetype = ".fbx"
    export_ext = filetype

    def execute(self, context):
        return call_export_file_picker(self, context)

class ExportGLB(bpy.types.Operator):
    bl_idname = "processor.export_glb"
    bl_label = "Start Export"
    filetype = ".glb"
    export_ext = filetype

    def execute(self, context):
        return call_export_file_picker(self, context)

class ExportGLTF(bpy.types.Operator):
    bl_idname = "processor.export_gltf"
    bl_label = "Start Export"
    filetype = ".glTF"

    def execute(self, context):
        return call_export_file_picker(self, context)

class ExportOBJ(bpy.types.Operator):
    bl_idname = "processor.export_obj"
    bl_label = "Start Export"
    filetype = ".obj"

    def execute(self, context):
        return call_export_file_picker(self, context)

class ExportPLY(bpy.types.Operator):
    bl_idname = "processor.export_ply"
    bl_label = "Start Export"
    filetype = ".ply"

    def execute(self, context):
        return call_export_file_picker(self, context)

class ExportSTL(bpy.types.Operator):
    bl_idname = "processor.export_stl"
    bl_label = "Start Export"
    filetype = ".stl"

    def execute(self, context):
        return call_export_file_picker(self, context)

class ExportUSD(bpy.types.Operator):
    bl_idname = "processor.export_usd"
    bl_label = "Start Export"
    filetype = ".usd"

    def execute(self, context):
        return call_export_file_picker(self, context)

class ExportUSDA(bpy.types.Operator):
    bl_idname = "processor.export_usda"
    bl_label = "Start Export"
    filetype = ".usda"

    def execute(self, context):
        return call_export_file_picker(self, context)

class ExportUSDC(bpy.types.Operator):
    bl_idname = "processor.export_usdc"
    bl_label = "Start Export"
    filetype = ".usdc"

    def execute(self, context):
        return call_export_file_picker(self, context)

class ExportUSDZ(bpy.types.Operator):
    bl_idname = "processor.export_usdz"
    bl_label = "Start Export"
    filetype = ".usdz"

    def execute(self, context):
        return call_export_file_picker(self, context)

def call_export_file_picker(Exportclass, context):
    ExportFileOperator.filename_ext = Exportclass.filetype
    bpy.ops.processor.file_export_operator('INVOKE_DEFAULT')
    return {'FINISHED'}

clss = (
    ExportFileOperator, ShowExportMenu, ExportMenu,
    ExportCTM, ExportFBX, ExportGLB, ExportGLTF, ExportOBJ, ExportPLY, ExportSTL, ExportUSD,
    ExportUSDA, ExportUSDC, ExportUSDZ
)
def menu_func_export(self:Any, context:bpy.types.Context):
    self.layout.operator(ExportFileOperator.bl_idname, text="RapidPipeline 3D Export")

def register():
    reg()
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)

def unregister():
    unreg()
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)

reg, unreg = bpy.utils.register_classes_factory(clss)