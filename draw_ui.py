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
import typing

import bpy
from bpy.types import Context, UILayout

from .compound_elements import SimpleContainer, TabElement, UIElement, init_ui_element
from .gui_commons import ProcessorPlugin
from .magic_actions_operator import ActivateMagicActionOperator, DeactivateMagicActionOperator, magic_actions_options
from .run_operator import RunOperator
from .scene_utils import (
    blend_create_prop,
    blend_scene_getattr,
)

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
    pcoll = preview_collections["main"]
    import_icon = pcoll["import"]

    ###############################
    # draw magic action selection buttons
    ###############################
    selection_layout = main_panel.layout.row()
    selection_layout.operator(DeactivateMagicActionOperator.bl_idname,
                    depress = False if context.scene.rpde_magicAction else True,
                    text="Manual Settings")
    selection_layout.operator(ActivateMagicActionOperator.bl_idname,
                    depress = True if context.scene.rpde_magicAction else False,
                    text="Magic Actions (Preview)")


    ###############################
    # draw magic actions
    ###############################
    magic_actions_layout = main_panel.layout.row()

    if context.scene.rpde_magicAction:
        #getMagicActions(main_panel, magic_actions_layout, context)
        magic_actions_panel(main_panel, magic_actions_layout, context, preview_collections)
        return

    ###############################
    # draw CAD import option
    ###############################
    #NOTE only activate when CAD import is enabled in rpde version
    if cad_import:
        cad_import_layout = main_panel.layout.row()
        cad_import_layout.scale_y = 1
        cad_import_layout.operator(
            CADImportFileOperator.bl_idname, icon_value=import_icon.icon_id, text="CAD Import")

    ###############################
    # draw execution buttons
    ###############################
    if not context.scene.rpde_magicAction:
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

    main_layout = main_panel.layout.row()

    ###############################
    # draw level selection
    ###############################
    if not context.scene.rpde_magicAction:
        main_layout.label(text="Level selection: ")
        main_panel.level_widget = getLevelSelection(main_layout, context)
        main_layout = main_panel.layout.row()

        _ = main_panel.layout.row()
        _ = main_panel.layout.row()

    ###############################
    # draw tab layout
    ###############################
    if not context.scene.rpde_magicAction:
        tab_layout = main_panel.layout.row()
        for _, child in enumerate(root_children):
            if isinstance(child, SimpleContainer):
                child.draw_on_panel(tab_layout, context, main_panel)

    _ = main_panel.layout.row()


def magic_actions_panel(main_panel:MainPanel, layout:UILayout, context:Context, preview_collections:dict):
    if os.path.isdir(os.path.join(dirname, 'magic-actions')):
        from .settings_operator import DefaultsOperator, LoadOperator, SaveOperator
        pcoll = preview_collections["main"]
        import_icon = pcoll["import"]
        load_icon = pcoll["load"]
        save_icon = pcoll["save"]
        run_icon = pcoll["run"]
        defaults_icon = pcoll["defaults"]

        layout = main_panel.layout

        layout.label(text="RapidPipeline Blender Plugin")
        layout = main_panel.layout.row(heading="test")
        layout.operator(
            CADImportFileOperator.bl_idname, icon_value=import_icon.icon_id, text="CAD Import")
        #percentage view (while running rpde)
        layout.prop(context.scene, "rpde_percentage", text="Progress", slider=True)
        layout.separator()
        layout.operator(
            LoadOperator.bl_idname, icon_value=load_icon.icon_id, text="Load Preset")
        #TODO doc buttons for doc / help page
        #TODO key button for tokens
        layout = main_panel.layout.row()
        layout = main_panel.layout.row()
        layout.label(text="What would you like to do?")
        layout = main_panel.layout.row()
        #TODO dropdown for magic actions
        layout = main_panel.layout.row()
        layout.label(text="TODO this is the selected magic action")
        layout = main_panel.layout.row()
        #TODO Image of magic action
        #TODO description of magic action
        layout = main_panel.layout.row()
        layout.label(text="Settings")
        layout = main_panel.layout.row()
        #TODO magic options
        layout = main_panel.layout.row()
        layout = main_panel.layout.row()
        layout = main_panel.layout.row()
        layout.label(text="Process Log")
        #TODO process log
        layout.operator(SaveOperator.bl_idname, icon_value=save_icon.icon_id, text="Save as Preset")
        layout.separator(factor=0.5)
        #TODO can we make this button in a different color?
        layout.operator(RunOperator.bl_idname, icon_value=run_icon.icon_id, text="Run") 




def getMagicActions(main_panel:MainPanel, layout:UILayout, context:Context):
    dirname = os.path.dirname(__file__)
    if os.path.isdir(os.path.join(dirname, 'magic-actions')):
        layout = main_panel.layout.box()
        layout.label(text="Preview of upcoming Magic Actions feature")
        layout.label(text="Use Magic Actions for a quick workflow:")
        layout.prop(context.scene.magic_action_property, "dropdown_selection")
        if context.scene.magic_action_property.dropdown_selection == "Choose a Magic Action":
            if context.scene.magic_action_property.warning_msg:
                layout.label(text=context.scene.magic_action_property.warning_msg, icon='ERROR')

        if magic_actions_options:
            layout.separator()

        for option in magic_actions_options:
            attribute_env, attribute = blend_scene_getattr(
                context.scene, "magic_action", path=option.option_path)

            layout.label(text=option.ui_element.parent_element.title)
            blend_create_prop(layout, attribute_env, attribute, name=option.ui_element.title)

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
