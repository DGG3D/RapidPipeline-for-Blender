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

import json
import os
import queue
import subprocess
import textwrap
import webbrowser
from sys import platform
from typing import List

import bpy  # type: ignore
import bpy.utils.previews  # type: ignore

# defines user appdata folder for the plugin
base_dcc_data_folder = os.path.join(
    os.path.expanduser("~"), 'Documents') if 'darwin' in platform else os.getenv("LOCALAPPDATA")
os.environ["RPDP_PROCESSOR_DCC_DATA"] = os.path.join(base_dcc_data_folder, "RapidPipeline 3D Processor Plugins")

from .about_dialog import AboutDialog, AboutDialogPanel
from .basic_elements import (
    BooleanPropertyGroup,
    ColorPropertyGroup,
    FloatPropertyGroup,
    GroupWidgetPropertyGroup,
    IntegerPropertyGroup,
    StringPropertyGroup,
)
from .magic_actions_operator import ActivateMagicActionOperator, DeactivateMagicActionOperator

dirname = os.path.dirname(__file__)
cad_import = os.path.isfile(os.path.join(dirname, "cad_import.py"))
if cad_import:
    from .cad_import import CADImportFileOperator
from .compound_elements import GroupPanel, SimpleContainer, TabElement, get_ui_elements_dict, init_ui_element
from .gui_commons import ProcessorPlugin, UIElement
from .license_manager import ProcessorLicense
from .magic_actions_operator import magic_actions_options
from .progress_dialog import ProgressDialog
from .run_operator import RunOperator
from .scene_utils import (
    blend_create_prop,
    blend_scene_getattr,
    blend_scene_init_setattr,
    blend_scene_setattr_enum,
    get_uuid,
    set_uuid,
)
from .settings_operator import DefaultsOperator, LoadOperator, SaveOperator

preview_collections = {}
uuid_paths = {} #key: uuid value: paths of schema

execution_queue = queue.Queue()
rpde_status = None

def enum(**enums:dict[str,str]) -> type:
    return type('Enum', (), enums)

class Tabs:
    tabs = enum(IMPORT = "Import",
                SCENEGRAPHFLATTENING = "Scene Graph Flatting",
                EDIT = "3D Edit",
                MESHCULLING = "Mesh Culling",
                OPTIMIZE = "Optimize",
                MODIFIER = "Modifier",
                EXPORT = "Export"
                )

class LevelOperator(bpy.types.Operator):
    bl_idname = "processor.level"
    bl_description = "Choose the level of settings shown"
    bl_label = "level"
    bl_options = {'REGISTER', 'UNDO'}

    level: bpy.props.StringProperty(options={'HIDDEN'}) # type: ignore

    def execute(self, context:bpy.types.Context) -> set[str]:
        print(f"Scene level is now: {self.level}")
        context.scene.level = self.level
        return {'FINISHED'}

class HelpOperator(bpy.types.Operator):
    bl_idname = "processor.help"
    bl_description = "Open the RapidPipeline Documentation Website"
    bl_label = "help"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context:bpy.types.Context) -> set[str]:
        self.helpLink()
        return {'FINISHED'}

    def helpLink(self):
        webbrowser.open(r"https://docs.rapidpipeline.com/docs/3dProcessor-Tutorials/blender-plugin-tutorials")

class RPDEPanel (bpy.types.Panel):
    bl_idname = "VIEW3D_PT_processor"
    bl_description = "processor"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "RapidPipeline"
    bl_parent_id = "VIEW3D_PT_RapidPipeline"
    bl_label = "processor_output"
    bl_options = {'HIDE_HEADER'}

    @classmethod
    def poll(cls, context:bpy.types.Context) -> bool:
        return context.scene.rpde_running and not context.scene.rpde_error

    def draw(self, context:bpy.types.Context):
        self.layout.prop(context.scene, "rpde_percentage", text="Progress", slider=True)
        self.layout.label(text=context.scene.rpde_output)

class CancelProcessorOperator(bpy.types.Operator):
    bl_idname = "processor.cancel_processor"
    bl_description = "Cancel the current process"
    bl_label = "Cancel"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context:bpy.types.Context) -> set[str]:
        bpy.types.Scene.rpde_running = False
        bpy.types.Scene.rpde_error = False
        bpy.types.Scene.rpde_cancel = True
        return {'FINISHED'}

class RetryProcessorOperator(bpy.types.Operator):
    bl_idname = "processor.retry_processor"
    bl_description = "Retry the current process"
    bl_label = "Retry"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context:bpy.types.Context) -> set[str]:
        print("Retry RapidPipeline...")
        bpy.types.Scene.rpde_running = False
        bpy.ops.processor.run()
        return {'FINISHED'}

class RestartUIOperator(bpy.types.Operator):
    bl_idname = "processor.restart_processor"
    bl_description = "restart_processor_token"
    bl_label = "Restart"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context:bpy.types.Context) -> set[str]:
        print("Reloading UI...")
        bpy.types.Scene.rpde_UI_error = False
        return {'FINISHED'}

def execute_queued_functions() -> float:
    while not execution_queue.empty():
        function = execution_queue.get()
        function()
    return 1.0

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

root_element:TabElement = init_ui_element("", "", uuid_dict=uuid_paths, schema=schema)

root_children = list(get_children(root_element))

class ButtonPanel(bpy.types.Panel):
    bl_idname = "VIEW3D_PT_Buttons"
    bl_label = "RapidPipeline Button"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "RapidPipeline"
    bl_parent_id = "VIEW3D_PT_RapidPipeline"
    bl_options = {'HIDE_HEADER'}

    @classmethod
    def poll(cls, context:bpy.types.Context) -> bool:
        return not context.scene.rpde_running and context.scene.has_license and not context.scene.rpde_UI_error

    def draw(self, context:bpy.types.Context):
        pcoll = preview_collections["main"]
        help_icon = pcoll["help"]
        about_icon = pcoll["about"]
        bottom_layout = self.layout.row()
        bottom_layout.scale_y = 1.4
        bottom_layout.operator(HelpOperator.bl_idname, icon_value=help_icon.icon_id, text="Help")
        bottom_layout.operator(AboutDialog.bl_idname, icon_value=about_icon.icon_id, text="About")

class MainPanel(bpy.types.Panel):
    bl_idname = "VIEW3D_PT_RapidPipeline"
    bl_label = "RapidPipeline Processor"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "RapidPipeline"

    # height variables for scroll area
    height_diff = 0

    was_successful: bool = False
    was_cancelled: bool = False


    # variables for progress
    progress_dialog: ProgressDialog = None

    def draw_header(self, context: bpy.types.Context):
        pcoll = preview_collections["main"]
        rapidpipeline_icon: bpy.types.Icons = pcoll["rapidPipeline"]
        self.layout.template_icon(icon_value=rapidpipeline_icon.icon_id, scale=1.2)

    def draw(self, context: bpy.types.Context):
        ###############################
        # draw ui error
        ###############################
        if context.scene.rpde_UI_error:
            drawUIError(self, context)
            return
        ###############################
        # draw rpde window
        ###############################
        try:
            if context.scene.rpde_running or not context.scene.has_license:
                if context.scene.rpde_running and not context.scene.rpde_error:
                    running_layout = self.layout.row()
                    running_layout.operator(CancelProcessorOperator.bl_idname, text="Cancel")
                if context.scene.rpde_error:
                    error_layout = self.layout.row()
                    error_layout.operator(CancelProcessorOperator.bl_idname, text="Cancel")
                    error_layout.operator(RetryProcessorOperator.bl_idname, text="Retry")
                    rpde_output = context.scene.rpde_output
                    error_layout = self.layout.row()
                    prettyPrint(self, rpde_output, context)
                return

            pcoll = preview_collections["main"]
            import_icon = pcoll["import"]

            ###############################
            # draw magic action selection buttons
            ###############################
            selection_layout = self.layout.row()
            selection_layout.operator(DeactivateMagicActionOperator.bl_idname,
                            depress = False if context.scene.rpde_magicAction else True,
                            text="Manual Settings")
            selection_layout.operator(ActivateMagicActionOperator.bl_idname,
                            depress = True if context.scene.rpde_magicAction else False,
                            text="Magic Actions (Preview)")


            ###############################
            # draw CAD import option
            ###############################
            #NOTE only activate when CAD import is enabled in rpde version
            if cad_import:
                cad_import_layout = self.layout.row()
                cad_import_layout.scale_y = 1
                cad_import_layout.operator(
                    CADImportFileOperator.bl_idname, icon_value=import_icon.icon_id, text="CAD Import")

            ###############################
            # draw execution buttons
            ###############################
            if not context.scene.rpde_magicAction:
                button_layout = self.layout.grid_flow(
                    row_major=True, columns=0, even_columns=True, even_rows=False, align=True)
                self.getExecutionButtons(button_layout)
            run_layout = self.layout.row()
            pcoll = preview_collections["main"]
            run_icon = pcoll["run"]
            run_layout.scale_y = 1.6
            run_layout.operator(RunOperator.bl_idname, icon_value=run_icon.icon_id, text="Run")

            _ = self.layout.row()
            _ = self.layout.row()

            ###############################
            # draw magic actions
            ###############################
            magic_actions_layout = self.layout.row()

            if context.scene.rpde_magicAction:
                self.getMagicActions(magic_actions_layout, context)


            main_layout = self.layout.row()

            ###############################
            # draw level selection
            ###############################
            if not context.scene.rpde_magicAction:
                main_layout.label(text="Level selection: ")
                self.level_widget = self.getLevelSelection(main_layout, context)
                main_layout = self.layout.row()

                _ = self.layout.row()
                _ = self.layout.row()

            ###############################
            # draw tab layout
            ###############################
            if not context.scene.rpde_magicAction:
                tab_layout = self.layout.row()
                for _, child in enumerate(root_children):
                    if isinstance(child, SimpleContainer):
                        child.draw_on_panel(tab_layout, context, self)

            _ = self.layout.row()

        except Exception:
            print("ERROR: Could not draw UI Components of RapidPipeline Blender Plugin.")
            bpy.types.Scene.rpde_UI_error = True
            import traceback
            traceback.print_stack()
            traceback.print_exc()

    def getExecutionButtons(self, layout:bpy.types.UILayout) -> None:
        pcoll = preview_collections["main"]
        load_icon = pcoll["load"]
        save_icon = pcoll["save"]
        defaults_icon = pcoll["defaults"]
        layout.scale_y = 1
        layout.operator(LoadOperator.bl_idname, icon_value=load_icon.icon_id, text="Load Preset")
        layout.operator(SaveOperator.bl_idname, icon_value=save_icon.icon_id, text="Save Preset")
        layout.operator(DefaultsOperator.bl_idname, icon_value=defaults_icon.icon_id, text="Defaults")

    def getMagicActions(self, layout:bpy.types.UILayout, context:bpy.types.Context):
        dirname = os.path.dirname(__file__)
        if os.path.isdir(os.path.join(dirname, 'magic-actions')):

            layout = self.layout.box()
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
                    context.scene, "magic_action", uuid_dict={}, path=option.option_path)

                layout.label(text=option.ui_element.parent_element.title)
                blend_create_prop(layout, attribute_env, attribute, name=option.ui_element.title)

            _ = self.layout.row()
            _ = self.layout.row()


    def getLevelSelection(self, main_layout: bpy.types.UILayout, context:bpy.types.Context):
        """
        Radio button group, selecting the settings level to be displayed.
        """

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


clss = (MainPanel, BooleanPropertyGroup,
        IntegerPropertyGroup, FloatPropertyGroup, LevelOperator, ColorPropertyGroup,
        LoadOperator, SaveOperator, DefaultsOperator, HelpOperator, RunOperator,
        StringPropertyGroup, RPDEPanel,
        GroupWidgetPropertyGroup, CancelProcessorOperator, RetryProcessorOperator,
        RestartUIOperator,
        )

late_reg_clss = (ButtonPanel, AboutDialogPanel)

reg, unreg = bpy.utils.register_classes_factory(clss)
late_reg, late_unreg = bpy.utils.register_classes_factory(late_reg_clss)


def drawUIError(panel:bpy.types.Panel, context:bpy.types.Context):
        error_layout = panel.layout.row()
        error_msg = """ERROR: Could not draw UI Components of RapidPipeline Blender Plugin. \n
        Please try to restart the RapidPipeline Plugin or contact Customer Support."""

        prettyPrint(panel, error_msg, context)
        error_layout.operator(RestartUIOperator.bl_idname, text="Restart")

#https://blender.stackexchange.com/questions/74052/wrap-text-within-a-panel
def prettyPrint(panel:bpy.types.Panel, text:str, context:bpy.types.Context):
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
            panel.layout.label(text=chunk)

def create_subpanel(path:List[str], parent_panel:str, schema:dict, display_header:bool) -> GroupPanel:
    set_uuid(set(path))
    id = f"VIEW3D_PT_Subpanel{get_uuid(path).replace('-', '')}"
    header = {'HIDE_HEADER'} if not display_header else set()
    if id:
        if not hasattr(bpy.types, id):
            new_panel = type(id,
                (GroupPanel, bpy.types.Panel, ),
                {"bl_idname" : id, "bl_label" : schema.get("title", ""),
                    "bl_parent_id": parent_panel, "UI_elements": [],
                    "bl_options": header})
            if not hasattr(bpy.types, new_panel.bl_idname):
                bpy.utils.register_class(new_panel)
            return new_panel
        else:
            return getattr(bpy.types, id)
    return None

def add_ui_element_to_panel(path:List[str], panel:GroupPanel):
    if panel.bl_idname != "VIEW3D_PT_RapidPipeline":
        try:
            ui_element:UIElement = get_ui_elements_dict()[get_uuid(path)]
        except Exception:
            ui_element:UIElement = None
        if ui_element:
            if not isinstance(ui_element, SimpleContainer):
                panel.UI_elements.append(ui_element)
                ui_element.panel = panel

def add_parent_to_panel(in_path:List[str], panel:GroupPanel, schema_key:str):
    if schema_key:
        path = in_path.copy()
        try:
            ui_element:UIElement = get_ui_elements_dict()[get_uuid(path)]
        except Exception:
            import traceback
            traceback.print_stack()
            traceback.print_exc()

            print("Error could not find ui element to add to panel")
            ui_element:UIElement = None
        if ui_element:
            panel.parent_element = ui_element
    else:
        print("Error: could not find schema key for adding parent to panel")
        print(f"For Path: {in_path} and panel: {panel.bl_label}")

def setup_properties(schema: dict,
                     parent: dict = None,
                     path: List[str] = [],
                     schema_key:str = "",
                     parent_panel:str = ""):

    if isinstance(parent, dict) and parent.get('settingid', None) is not None:
        if schema_key:
            path.append(schema_key)

    if not parent_panel:
        parent_panel = create_subpanel(path, MainPanel.bl_idname, schema, display_header=False)
    temp_path = path.copy()
    attribute_id = schema.get("settingid", "settingid_not_found")

    for key in schema.keys():
        if key == 'properties':
            for sub_schema in schema['properties'].keys():
                if isinstance(schema['properties'][sub_schema], dict):
                    if parent and path:
                        parent_panel = create_subpanel(path.copy(), parent_panel.bl_idname, schema, display_header=True)
                        add_parent_to_panel(path.copy(), parent_panel, sub_schema)
                    setup_properties(schema=schema['properties'][sub_schema],
                                        parent=schema.copy(), path=path.copy(),
                                        schema_key=sub_schema, parent_panel=parent_panel)

        if not schema_key:
            continue

        if key == 'type':
            if schema['type'] == 'boolean':
                blend_scene_init_setattr(
                    bpy.types.Scene, attribute_id, property_group=BooleanPropertyGroup, path=path,
                    value_function=bpy.props.BoolProperty(
                        default=schema['default'], description=schema.get("description", "")),
                    uuid_dict=uuid_paths, toggable=('toggleable' in schema))
                add_ui_element_to_panel(path, parent_panel)
            if schema['type'] == 'integer':
                blend_scene_init_setattr(
                    bpy.types.Scene, attribute_id, property_group=IntegerPropertyGroup, path=path,
                    value_function=bpy.props.IntProperty(
                        default=schema['default'], min=schema.get('minimum', 0.0),
                        max=schema.get('maximum', 100_000_000), description=schema.get("description", "")),
                    uuid_dict=uuid_paths, toggable=('toggleable' in schema))
                add_ui_element_to_panel(path, parent_panel)
            if schema['type'] == 'string':
                blend_scene_init_setattr(
                    bpy.types.Scene, attribute_id, property_group=StringPropertyGroup, path=path,
                    value_function=bpy.props.StringProperty(
                        default=schema['default'], description=schema.get("description", "")),
                    uuid_dict=uuid_paths, toggable=('toggleable' in schema))
                add_ui_element_to_panel(path, parent_panel)
            if schema['type'] == 'object':
                blend_scene_init_setattr(
                    bpy.types.Scene, attribute_id,
                    property_group=GroupWidgetPropertyGroup, path=path,
                    value_function=bpy.props.BoolProperty(default=False, description=schema.get("description", "")),
                    uuid_dict=uuid_paths, toggable=('toggleable' in schema))
                add_ui_element_to_panel(path, parent_panel)

            if schema['type'] == 'number':
                if 'percentage' in parent:
                        blend_scene_init_setattr(
                            bpy.types.Scene, attribute_id,
                            property_group=FloatPropertyGroup, path=path,
                            value_function=
                                bpy.props.FloatProperty(
                                    min=schema['minimum'],
                                    max=schema['maximum'],
                                    default=schema['default'],
                                    subtype='PERCENTAGE',
                                    description=schema.get("description", "")),
                                    uuid_dict=uuid_paths,
                                    value=schema['default'],
                                    toggable=('toggleable' in schema))
                        add_ui_element_to_panel(path, parent_panel)
                else:
                    if 'maximum' in schema:
                        value_function = bpy.props.FloatProperty(
                                min=schema.get('minimum', 0.0), max=schema['maximum'],
                                default=schema.get('default', 0.0), description=schema.get("description", ""))
                    else:
                        value_function = bpy.props.FloatProperty(
                                    min=schema.get('minimum', 0.0), default=schema.get('default', 0.0),
                                    description=schema.get("description", ""))
                    blend_scene_init_setattr(
                        bpy.types.Scene, attribute_id,
                        property_group=FloatPropertyGroup, path=path,
                        value_function=value_function, uuid_dict=uuid_paths,
                        toggable=('toggleable' in schema))
                    add_ui_element_to_panel(path, parent_panel)

            if schema['type'] == 'array' and 'default' in schema:
                blend_scene_init_setattr(
                    bpy.types.Scene, attribute_id, property_group=ColorPropertyGroup, path=path,
                    value_function=bpy.props.FloatVectorProperty(
                        default = (schema['default'][:3]), min=0.0, max=1.0, subtype='COLOR',
                        description=schema.get("description", "")),
                        uuid_dict=uuid_paths, toggable=('toggleable' in schema))
                add_ui_element_to_panel(path, parent_panel)

        if key == 'enum':
            enum_options = []
            for element in schema['enum']:
                enum_options.append((element,)*3)
            blend_scene_setattr_enum(bpy.types.Scene, attribute_id, uuid_dict=uuid_paths,
                    property=bpy.props.EnumProperty(items=enum_options, description=schema.get("description", "")),
                    path=path)
            add_ui_element_to_panel(path, parent_panel)

        if key == 'oneOf':
            #create panel for oneofs (needed for modifier tab)
            if list(schema.keys())[0] == "oneOf":
                sub_schema = list(schema.keys())[0]
                if parent and path:
                    parent_panel = create_subpanel(path.copy(), parent_panel.bl_idname, schema, display_header=True)
                    add_parent_to_panel(path.copy(), parent_panel, sub_schema)

            oneof_elements = []
            for oneof_sub_schema in schema['oneOf']:
                oneof_elements.append((oneof_sub_schema.get('settingid', ''),
                                        oneof_sub_schema.get('title', ''),
                                        oneof_sub_schema.get('description', '')))
            #TODO: we need to draw the child objects of oneof
            #however they dont have a different path and they dont appear in the settings
            #this would be the emptyCompoundUIElement
            #so we need to draw the children of the correct empty comound ui element
            path_oneof = path.copy()
            path_oneof.append("Oneof")
            blend_scene_setattr_enum(bpy.types.Scene, attribute_id, uuid_dict=uuid_paths,
                    property=bpy.props.EnumProperty(items=oneof_elements, description=schema.get("description", "")),
                    path=path_oneof)
            add_ui_element_to_panel(path_oneof, parent_panel)

            path_tmp = path.copy()
            for oneof_sub_schema in schema['oneOf']:
                if isinstance(oneof_sub_schema, dict):
                    setup_properties(schema=oneof_sub_schema,
                                        parent=schema.copy(),
                                        path=path_tmp, schema_key= None,
                                        parent_panel=parent_panel)
                path=path_tmp

        path= temp_path



def setup_icons():
    pcoll = bpy.utils.previews.new()
    dirname = os.path.dirname(__file__)
    icons_dict = {
        "rapidPipeline" : 'Icon_solid_green.png',
        "edit" : '3dEdit.svg',
        "import" : 'import.svg',
        "sceneGraphFlattening" : 'sceneGraphFlattening.svg',
        "meshCulling" : 'meshCulling.svg',
        "optimize" : 'optimize.svg',
        "modifier" : 'outcomeModifier.svg',
        "export" : 'exportArray.svg',
        "load" : 'load.svg',
        "save" : 'save.svg',
        "defaults" : 'restore.svg',
        "help" : 'help.svg',
        "about" : 'info.svg',
        "run" : 'run.svg'
    }
    for file, file_name in icons_dict.items():
        icon_dir = os.path.join(dirname, 'resources', 'images', file_name)
        pcoll.load(file, icon_dir, 'IMAGE')

    if os.path.isdir(os.path.join(dirname, 'magic-actions')):
        magic_action_folder = os.path.join(dirname, 'magic-actions', 'actions')
        for magic_action in os.listdir(magic_action_folder):
            if os.path.isdir(os.path.join(magic_action_folder, magic_action)):
                icon_dir = os.path.join(magic_action_folder, magic_action, 'icon-dark.svg')
                pcoll.load(f"magic_action_{magic_action}", icon_dir, 'IMAGE')
                setattr(bpy.types.Scene, f"magic_action_{magic_action}", pcoll[f"magic_action_{magic_action}"])

    preview_collections["main"] = pcoll

    pcoll = preview_collections["main"]
    bpy.types.Scene.icon_import = pcoll["import"]
    bpy.types.Scene.icon_3dEdit = pcoll["edit"]
    bpy.types.Scene.icon_sceneGraphFlattening = pcoll["sceneGraphFlattening"]
    bpy.types.Scene.icon_meshCulling = pcoll["meshCulling"]
    bpy.types.Scene.icon_optimize = pcoll["optimize"]
    bpy.types.Scene.icon_outcomeModifier = pcoll["modifier"]
    bpy.types.Scene.icon_export = pcoll["export"]


def register():
    reg()

    # if the temp license file is in the folder, remove it before continuing
    if os.path.isfile(ProcessorLicense.TEMP_LICENSE_FILE):
        os.remove(ProcessorLicense.TEMP_LICENSE_FILE)

    ProcessorPlugin.loadSchema()
    schema = ProcessorPlugin.getSolvedSchema()

    # load_post is only called on blender startup
    # timers.register is used in case the plugin is installed without a blender restart
    # we can not rely only on timers.register since it doesnt work on loading blender scenes
    global register_worked
    register_worked = False
    def wait_for_late_register(dummy = None):  # noqa: ANN001
        global register_worked
        if not register_worked:
            register_worked = True
            setup_properties(schema, path=[])

    bpy.app.timers.register(wait_for_late_register, first_interval=0.1)
    bpy.app.handlers.load_post.append(wait_for_late_register)  #wait for context to be fully loaded

    setup_icons()

    #setup tab elements
    tab_elements = []
    override_rules = ProcessorPlugin.ui_rules.get("overrideUIElement", {})
    for element in override_rules.get("SimpleContainer", []):
        tab_elements.append((element, element, "description"))

    bpy.types.Scene.tabelements = bpy.props.EnumProperty(items=tab_elements)

    bpy.types.Scene.aboutdialog = bpy.props.BoolProperty(default=False)
    bpy.types.Scene.licenses = bpy.props.StringProperty()

    #setup level
    level = [(("basic",)*3), (("advanced",)*3), (("expert",)*3)]
    bpy.types.Scene.level = bpy.props.EnumProperty(items=level)


    bpy.types.Scene.boolean_default = bpy.props.PointerProperty(type=BooleanPropertyGroup)
    bpy.types.Scene.integer_default = bpy.props.PointerProperty(type=IntegerPropertyGroup)
    bpy.types.Scene.float_default = bpy.props.PointerProperty(type=FloatPropertyGroup)
    bpy.types.Scene.enum_default = bpy.props.EnumProperty(
        items=[("default_enum", "default_name", "default_description")])
    bpy.types.Scene.color_default = bpy.props.FloatVectorProperty(
        default = (1.0, 1.0, 1.0), min=0.0, max=1.0, subtype='COLOR')

    bpy.types.Scene.rpde_output = ""
    bpy.types.Scene.rpde_percentage = bpy.props.IntProperty(default=0, min=0, max=100, step=1, subtype='PERCENTAGE')
    bpy.types.Scene.has_license = ProcessorLicense.performLicenseCheck(None)
    bpy.types.Scene.use_token_future_sessions = bpy.props.BoolProperty(
        default=False,
        description="If checked, the current Authentication Token will be saved to disk for future usage.")
    bpy.types.Scene.t_and_c_agreed = bpy.props.BoolProperty(
        default=False,
        description="If checked, you agree to the Terms and Conditions of RapidPipeline usage.")
    bpy.types.Scene.api_token = bpy.props.StringProperty(default="")
    bpy.types.Scene.override_token = False
    bpy.types.Scene.rpde_running = False
    bpy.types.Scene.rpde_error = False
    bpy.types.Scene.rpde_cancel = False
    bpy.types.Scene.rpde_UI_error = False
    bpy.types.Scene.rpde_magicAction = False

    # load_post is only called on blender startup
    # timers.register is used in case the plugin is installed without a blender restart
    # we can not rely only on timers.register since it doesnt work on loading blender scenes
    global late_registered
    late_registered = False
    def wait_for_late_register(dummy = None):  # noqa: ANN001
        global late_registered
        if not late_registered:
            late_registered = True
            late_reg()
            # save Addon to userpref to activate directly
            bpy.ops.wm.save_userpref()

    bpy.app.timers.register(wait_for_late_register, first_interval=0.2)
    bpy.app.handlers.load_post.append(wait_for_late_register)  #wait for context to be fully loaded

    if 'darwin' == platform:
        print("Mac detected")
        removeQuarantineFlagOnMac()
    elif 'linux' == platform:
        setupLinux()

def removeQuarantineFlagOnMac():
    os.chdir(os.path.dirname(ProcessorPlugin.getRPDEPath()))
    command_arguments = ['xattr', '-d', 'com.apple.quarantine', "./rpde"]
    command_arguments2 = ['chmod', '+x', "./rpde"]
    print("Removing quarantine flag on Mac...")
    print(command_arguments)

    _ = subprocess.run(
            command_arguments2)

    result = subprocess.run(
            command_arguments)

    print(f"Subprocess result: {result}")

def setupLinux():
    os.chdir(os.path.dirname(ProcessorPlugin.getRPDEPath()))
    command_arguments = ['chmod', '+x', "./rpde"]
    result = subprocess.run(
            command_arguments)

    print(f"Subprocess result: {result}")

def unregister():
    unreg()
    # if the temp license file is in the folder, remove it before continuing
    if os.path.isfile(ProcessorLicense.TEMP_LICENSE_FILE):
        os.remove(ProcessorLicense.TEMP_LICENSE_FILE)
    late_unreg()
