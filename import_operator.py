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
import textwrap
from typing import Any

import bpy
import bpy_extras
from bpy.types import Context, Event, Operator

from .magic_actions_operator import MagicAction, MagicActionOperator, get_import_actions, get_version
from .ProcessorPluginsCommon.magic_actions.utils import saveJSON
from .run_operator import RunPipeline, get_export_settings
from .scene_utils import blend_create_prop, blend_scene_getattr

output_path = os.path.join(os.environ["RPDP_PROCESSOR_DCC_DATA"], "import")

#https://blender.stackexchange.com/questions/74052/wrap-text-within-a-panel
def prettyPrint(main_layout:Any ,text:str, context:Context):
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

class ImportFileOperator(Operator, bpy_extras.io_utils.ImportHelper):
    bl_idname = "processor.file_import_operator"
    bl_description = "Import 3D Model"
    bl_label = "Import File"

    dirname = os.path.dirname(__file__)
    cad_import = os.path.isfile(os.path.join(dirname, "cad_import.py"))

    import_actions:list[MagicAction] = get_import_actions()
    for action in import_actions:
        if not cad_import and "Import CAD" in action.name:
            import_actions.remove(action)

    def invoke(self, context:Context, event:Event) -> set:
        # select first import action
        bpy.ops.processor.magic_action_button(magic_action_str=self.import_actions[0].name)
        return super().invoke(context, event)

    def cancel(self, context:Context):
        # select first magic action
        from .magic_actions_operator import MagicAction, get_magic_actions
        magic_actions_sorted:list[MagicAction] = get_magic_actions()
        first_magic_action = magic_actions_sorted[0].name
        bpy.ops.processor.magic_action_button(magic_action_str=first_magic_action)
        return None

    def draw(self, context:Context):
        layout = self.layout
        selected_magic_action_str = context.scene.rpde_selected_action
        selection = "Choose a Magic Action"

        from .main_widget import preview_collections
        pcoll = preview_collections["main"]
        magic_action_placeholder = pcoll.get("Magic_action_placeholder", None)
        version = get_version()
        button_layout = layout
        main_magic_layout = layout

        for magic_action in self.import_actions:
            op:MagicActionOperator = button_layout.operator(
                MagicActionOperator.bl_idname,
                text=magic_action.name,
                icon_value=getattr(context.scene,
                                   f"magic_action_{version}_{magic_action.name}").icon_id,
                depress=selected_magic_action_str == magic_action.name)
            action_name = magic_action.name
            op.magic_action_str = action_name

        if selected_magic_action_str:
            selection = selected_magic_action_str
        from .magic_actions_operator import MagicAction
        selected_magic_action:MagicAction = next((action for action in get_import_actions()
                                                  if action.name == selection
                                                  and action.version == get_version()), None)

        magic_layout = main_magic_layout.row()
        if selection != "Choose a Magic Action":
            magic_layout.label(text=f"{selection}")
            magic_layout = main_magic_layout.row()
            magic_layout = main_magic_layout.row()
            if context.scene.rpde_enable_preview:
                action_image_str = f"magic_action_image_{version}_{selected_magic_action.name}"
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
                    prettyPrint(magic_layout, selected_magic_action.description, context)
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

                    option_name = option.option_name if (
                        option.option_name) else option.option.get_option_ui_element().title
                    left_col.label(text=option_name)
                    blend_create_prop(right_col, attribute_env, attribute, name="")
                    sub = box_layout.row()
            else:
                print(f"Warning, could not find options for MagicAction: {selected_magic_action.name}")
        else:
            magic_layout = main_magic_layout.row()
            warning_msg = "Please choose an action above"
            magic_layout.label(text=warning_msg, icon='ERROR')

    def execute(self, context:Context) -> set:

        if not os.path.isfile(self.filepath):
            self.report({'WARNING'}, "No file selected...")
            return {'FINISHED'}

        self.report({'INFO'}, "Importing 3D file...")
        import_path = os.path.join(os.path.dirname(__file__), 'resources', "import")

        from .draw_ui import root_element
        current_settings = root_element.getSettings()

        current_settings["export"] = get_export_settings("rpde_file")

        # make sure to get the correct filename
        current_name = current_settings["export"][0].get("fileName", "")
        if not current_name:
            self.output_filename = "rpde_file"
        else:
            self.output_filename = current_name

        import_settings_dict = current_settings
        rpde_settings_tmp = os.path.join(import_path, "rpdp_dcc_plugin_import_settings_tmp.json")

        if saveJSON(import_settings_dict, rpde_settings_tmp):
            _ = import_file(self.filepath, rpde_settings_tmp)
        else:
            print("Warning, could not save import settings.")

        return {'FINISHED'}

def import_file(filepath:str, rpde_settings_path:str) -> str:
    out_path = os.path.join(output_path, "output", "input_converted.glb")

    if not rpde_settings_path:
        raise Exception("Could not load RPDE CAD settings file.")

    file_path = os.path.join(os.environ["RPDP_PROCESSOR_DCC_DATA"])

    # unselect everything
    for o in list(bpy.data.objects):
        o.select_set(False)


    RunPipeline.runPipeline(filepath, rpde_settings_path, file_path, copied_nodes=None)
    return out_path

def menu_func_import(self:Any, context:bpy.types.Context):
    self.layout.operator(ImportFileOperator.bl_idname, text="RapidPipeline 3D Import")

clss = (
    ImportFileOperator,
)

def register():
    reg()
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

def unregister():
    unreg()
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)

reg, unreg = bpy.utils.register_classes_factory(clss)
