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
from __future__ import annotations

import os
import textwrap
import typing

import bpy
from bpy.types import Context, UILayout

from .compound_elements import SimpleContainer, TabElement, UIElement, init_ui_element
from .gui_commons import ProcessorPlugin
from .magic_actions_operator import (
    ActivateMagicActionOperator,
    DeactivateMagicActionOperator,
    DescriptionOperator,
    MagicActionOperator,
    get_magic_actions,
    get_version,
)
from .run_operator import RunOperator
from .scene_utils import (
    blend_create_prop,
    blend_scene_getattr,
)
from .settings_operator import CancelProcessorOperator, RetryProcessorOperator

if typing.TYPE_CHECKING:
    from main_widget import MainPanel

def get_children(parent:UIElement) -> list[UIElement]:
    child_nodes = [parent]
    if hasattr(parent, 'child_elements'):
        for child in parent.child_elements:
            child_nodes.extend(get_children(child))
    return child_nodes


# loads metadata file
processor_plugin = ProcessorPlugin()
processor_plugin.loadPluginMetadata()

# reset widgets, load schema and UI rules
processor_plugin.reset()
processor_plugin.loadSchema()
processor_plugin.loadUIRules()
schema = processor_plugin.getSolvedSchema()
root_element:TabElement = init_ui_element("", "", uuid_dict={}, schema=schema)

root_children = list(get_children(root_element))


dirname = os.path.dirname(__file__)
cad_import = os.path.isfile(os.path.join(dirname, "cad_import.py"))

if cad_import:
    from .cad_import import CADImportFileOperator

def draw_main_panel(main_panel:MainPanel, context:Context, preview_collections:dict):

    _ = main_panel.layout.row()

    if context.scene.rpde_detail_mode:
        manual_settings_panel(main_panel, context, preview_collections)

#https://blender.stackexchange.com/questions/74052/wrap-text-within-a-panel
def prettyPrint(main_layout:UILayout ,text:str, context:bpy.types.Context):
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            break
    for region in area.regions:
        if region.type == 'UI':
            panel_width = region.width * (3 / 4)
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
            main_layout = main_layout.column()
            main_layout.label(text=chunk)

def manual_settings_panel(main_panel:MainPanel, context:Context, preview_collections:dict):
    if context.scene.rpde_running and not context.scene.rpde_error:
        running_layout = main_panel.layout.row()
        running_layout.operator(CancelProcessorOperator.bl_idname, text="Cancel")
        return
    if context.scene.rpde_error:
        error_layout = main_panel.layout.row()
        error_layout.operator(CancelProcessorOperator.bl_idname, text="Cancel")
        error_layout.operator(RetryProcessorOperator.bl_idname, text="Retry")
        rpde_output = context.scene.rpde_output
        error_layout = main_panel.layout.row()
        prettyPrint(main_panel.layout, rpde_output, context)
        return

    pcoll = preview_collections["main"]
    import_icon = pcoll["import"]
    ###############################
    # draw CAD import option
    ###############################
    #NOTE only activate when CAD import is enabled in rpde version
    if cad_import:
        cad_import_layout = main_panel.layout.row()
        cad_import_layout.scale_y = 1
        cad_import_layout.operator(
            CADImportFileOperator.bl_idname, icon_value=import_icon.icon_id, text="Import CAD File")

    ###############################
    # draw execution buttons
    ###############################
    button_layout = main_panel.layout.grid_flow(
        row_major=True, columns=0, even_columns=True, even_rows=False, align=True)
    getExecutionButtons(button_layout, preview_collections)
    run_layout = main_panel.layout.row()
    pcoll = preview_collections["main"]
    run_icon = pcoll["run"]
    run_layout.scale_y = 1.6
    run_layout.operator(RunOperator.bl_idname, icon_value=run_icon.icon_id, text="Run")

    _ = main_panel.layout.row()
    _ = main_panel.layout.row()
    _ = main_panel.layout.row()

    ###############################
    # draw tab layout
    ###############################
    tab_layout = main_panel.layout.row()
    for _, child in enumerate(root_children):
        if isinstance(child, SimpleContainer):
            child.draw_on_panel(tab_layout, context, main_panel)

    _ = main_panel.layout.row()


class ProcesslogToggle(bpy.types.PropertyGroup):
    show_box: bpy.props.BoolProperty(
        name="",
        description="",
        default=False
    ) # type: ignore

def magic_actions_panel(main_layout:UILayout, context:Context, preview_collections:dict):
    main_magic_layout = main_layout.column_flow()

    if context.scene.rpde_running:
        main_magic_layout.enabled = False
    else:
        main_magic_layout.enabled = True

    magic_layout = main_magic_layout.row()

    if os.path.isdir(os.path.join(dirname, 'magic-actions')):

        pcoll = preview_collections["main"]
        run_icon = pcoll["run"]
        magic_action_placeholder = pcoll["Magic_action_placeholder"]

        magic_layout = main_magic_layout.row(align=True)
        magic_layout.scale_x = 2.0
        magic_layout.alignment = 'LEFT'


        #Magic action buttons
        button_layout = magic_layout.grid_flow(
            row_major=True, columns=0, even_columns=True, even_rows=False, align=True)
        button_layout.scale_y = 1.4
        button_layout.scale_x = 1.0

        selected_magic_action_str = context.scene.magic_action_property.selected_magic_action
        selection = "Choose a Magic Action"

        version = get_version()

        magic_action_sorted = get_magic_actions()

        for magic_action in magic_action_sorted:
            op:MagicActionOperator = button_layout.operator(
                MagicActionOperator.bl_idname,
                text=magic_action.action_name,
                icon_value=getattr(context.scene, f"magic_action_{version}_{os.path.basename(magic_action.path)}").icon_id,
                depress=selected_magic_action_str == magic_action.action_name)
            action_name = magic_action.action_name
            op.magic_action_str = action_name

        if selected_magic_action_str:
            selection = selected_magic_action_str
        from .magic_actions_operator import MagicAction
        selected_magic_action:MagicAction = next((action for action in magic_action_sorted
                                                  if action.action_name == selection
                                                  and action.action_version == version), None)

        magic_layout = main_magic_layout.row()
        if selection != "Choose a Magic Action":
            magic_layout.label(text=f"{selection}")
            magic_layout = main_magic_layout.row()
            magic_layout = main_magic_layout.row()
            try:
                if context.scene.rpde_enable_preview:
                    image_value = None
                    magic_action_image_str = f"magic_action_image_{version}_{os.path.basename(selected_magic_action.path)}"
                    if magic_action_image_str in pcoll:
                        image_value = pcoll[magic_action_image_str]
                    if selected_magic_action and selected_magic_action.action_image and image_value:
                        magic_layout.template_icon(icon_value=image_value.icon_id, scale=7.5)
                        magic_layout.separator()
                    else:
                        if magic_action_placeholder:
                            magic_layout.template_icon(icon_value=magic_action_placeholder.icon_id, scale=7.5)
                        else:
                            magic_layout.label(text="Image not loaded")
            except Exception:
                    if magic_action_placeholder:
                        magic_layout.template_icon(icon_value=magic_action_placeholder.icon_id, scale=7.5)
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
            if selected_magic_action:
                if selected_magic_action.action_options:
                    for option in selected_magic_action.action_options:
                        sub = sub.split(factor=0.33)
                        left_col = sub.column(align=True)
                        left_col.alignment  = 'RIGHT'
                        right_col = sub.column(align=True)
                        attribute_env, attribute = blend_scene_getattr(
                            context.scene, "magic_action", path=option.option_path)

                        #NOTE if we want to display the parent titles for additional context:
                        option_name = option.option_name if option.option_name else option.get_option_ui_element().title
                        left_col.label(text=option_name)
                        blend_create_prop(right_col, attribute_env, attribute, name="")
                        sub = box_layout.row()
            else:
                pass
        else:
            magic_layout = main_magic_layout.row()
            warning_msg = "Please choose an action above"
            magic_layout.label(text=warning_msg, icon='ERROR')

        magic_layout = main_magic_layout.row()
        magic_layout = main_magic_layout.row()
        magic_layout = main_magic_layout.row()

        if selection != "Choose a Magic Action":
            magic_running_layout = main_layout.row()
            magic_layout = main_layout.row()
            magic_layout.enabled = False
            magic_layout.label(text="Process Log")
            magic_layout = main_layout.row()
            box_layout = magic_layout.box()

            # Process log:
            log_layout = box_layout.row()
            props = context.scene.rpde_processor_log
            row= log_layout.row()
            row.template_list(
                listtype_name="UI_UL_list",
                list_id="processor_list",
                dataptr=props,
                propname="items",
                active_dataptr=props,
                active_propname="RPDE_message",
                item_dyntip_propname="RPDE_message",
                rows=5
            )

            magic_layout = main_layout.row()

            if context.scene.rpde_running:
                magic_layout.prop(context.scene, "rpde_percentage", text="Progress", slider=True)
                magic_layout = main_layout.row()
                magic_running_layout = main_layout.column_flow()
                magic_running_layout.operator(CancelProcessorOperator.bl_idname, text="Cancel")
            else:
                magic_layout.scale_y = 1.4
                magic_layout.operator(RunOperator.bl_idname, icon_value=run_icon.icon_id, text="Run")


class ProcessorLineProperty(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty() # type: ignore

class ProcessorLogProperty(bpy.types.PropertyGroup):
    items: bpy.props.CollectionProperty(type=ProcessorLineProperty) # type: ignore
    RPDE_message: bpy.props.IntProperty() # type: ignore

#NOTE currently not in use
def draw_magic_actions_dropdown(main_panel:MainPanel, layout:UILayout, context:Context):
    dirname = os.path.dirname(__file__)
    if os.path.isdir(os.path.join(dirname, 'magic-actions')):
        layout = main_panel.layout.box()
        layout.label(text="Preview of upcoming Magic Actions feature")
        layout.label(text="Use Magic Actions for a quick workflow:")
        layout.prop(context.scene.magic_action_property, "dropdown_selection")
        if context.scene.magic_action_property.dropdown_selection == "Choose a Magic Action":
            if context.scene.magic_action_property.warning_msg:
                layout.label(text=context.scene.magic_action_property.warning_msg, icon='ERROR')

        if context.scene.magic_action_property.action_options:
            layout.separator()

        for option in context.scene.magic_action_property.action_options:
            attribute_env, attribute = blend_scene_getattr(
                context.scene, "magic_action", path=option.option_path)

            layout.label(text=option.get_option_ui_element().parent_element.title)
            blend_create_prop(layout, attribute_env, attribute, name=option.get_option_ui_element().title)

        _ = main_panel.layout.row()
        _ = main_panel.layout.row()


def getExecutionButtons(layout:UILayout, preview_collections:dict) -> None:
    from .settings_operator import DefaultsOperator, LoadOperator, SaveOperator
    pcoll = preview_collections["main"]
    load_icon = pcoll["load"]
    save_icon = pcoll["save"]
    defaults_icon = pcoll["defaults"]
    layout.scale_y = 1
    layout.operator(LoadOperator.bl_idname, icon_value=load_icon.icon_id, text="Load Preset")
    layout.operator(SaveOperator.bl_idname, icon_value=save_icon.icon_id, text="Save Preset")
    layout.operator(DefaultsOperator.bl_idname, icon_value=defaults_icon.icon_id, text="Defaults")


def getLevelSelection(main_layout: UILayout, context:Context):
    """
    Radio button group, selecting the settings level to be displayed.
    """
    from .main_widget import LevelOperator
    main_layout.scale_y = 1.3

    basic_level = main_layout.operator(
        LevelOperator.bl_idname,
        text="Basic",
        depress=bpy.context.scene.level == 'basic')
    basic_level.level = 'basic'
    advanced_level = main_layout.operator(
        LevelOperator.bl_idname,
        text="Advanced",
        depress=bpy.context.scene.level == 'advanced')
    advanced_level.level = 'advanced'
    expert_level = main_layout.operator(
        LevelOperator.bl_idname,
        text="Expert",
        depress=bpy.context.scene.level == 'expert')
    expert_level.level = 'expert'


def register():
    bpy.utils.register_class(ProcessorLineProperty)
    bpy.utils.register_class(ProcessorLogProperty)
    bpy.types.Scene.rpde_processor_log = bpy.props.PointerProperty(type=ProcessorLogProperty)


def unregister():
    bpy.utils.unregister_class(ProcessorLineProperty)
    bpy.utils.unregister_class(ProcessorLogProperty)
