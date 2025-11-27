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
import queue
import subprocess
import textwrap
import webbrowser
from sys import platform
from typing import Any, List

import bpy
import bpy.utils.previews
from bpy.types import Context, Operator, Panel

# defines user appdata folder for the plugin
base_dcc_data_folder = os.path.join(
    os.path.expanduser("~"), 'Documents') if 'darwin' in platform else os.getenv("LOCALAPPDATA")
os.environ["RPDP_PROCESSOR_DCC_DATA"] = os.path.join(base_dcc_data_folder, "RapidPipeline 3D Processor Plugins")

from .about_dialog import AboutDialog, AboutDialogPanel, OverrideTokenOperator
from .basic_elements import (
    BooleanPropertyGroup,
    ColorPropertyGroup,
    FloatPropertyGroup,
    GroupWidgetPropertyGroup,
    IntegerPropertyGroup,
    StringPropertyGroup,
)
from .compound_elements import GroupPanel, SimpleContainer, get_ui_elements_dict
from .draw_ui import draw_main_panel, draw_processor_log, magic_actions_panel
from .export_operator import ShowExportMenu
from .gui_commons import ProcessorPlugin, UIElement
from .import_operator import ImportFileOperator
from .license_manager import ProcessorLicense
from .progress_dialog import ProgressDialog
from .scene_utils import (
    blend_scene_init_setattr,
    blend_scene_setattr_enum,
    get_uuid,
    set_uuid,
)
from .settings_operator import (
    CancelProcessorOperator,
    DefaultsOperator,
    LoadOperator,
    RestartUIOperator,
    RetryProcessorOperator,
    SaveOperator,
)

preview_collections = {}
uuid_paths = {} #key: uuid value: paths of schema

execution_queue = queue.Queue()
rpde_status = None

dirname = os.path.dirname(__file__)
cad_import = os.path.isfile(os.path.join(dirname, "cad_import.py"))

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

class LevelOperator(Operator):
    bl_idname = "processor.level"
    bl_description = "Choose the level of settings shown"
    bl_label = "level"
    bl_options = {'REGISTER', 'UNDO'}

    level: bpy.props.StringProperty(options={'HIDDEN'}) # type: ignore

    def execute(self, context:Context) -> set[str]:
        print(f"Scene level is now: {self.level}")
        context.scene.level = self.level
        return {'FINISHED'}

class SettingsOperator(Operator):
    bl_idname = "processor.settings"
    bl_description = "Open the RapidPipeline Settings"
    bl_label = "settings"
    bl_options = {'REGISTER'}

    def execute(self, context:Context) -> set[str]:
        bpy.types.Scene.rpde_settings = not context.scene.rpde_settings
        bpy.types.Scene.rpde_draw_ui = not context.scene.rpde_settings
        bpy.types.Scene.rpde_help = False
        if not context.scene.rpde_settings and not context.scene.rpde_detail_mode:
            # reset to first magic action to prevent issues:
            reset_magic_actions()
        return {'FINISHED'}

class HelpOperator(Operator):
    bl_idname = "processor.help"
    bl_description = "Open the RapidPipeline Documentation Website"
    bl_label = "help"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context:Context) -> set[str]:
        bpy.types.Scene.rpde_help = not context.scene.rpde_help
        bpy.types.Scene.rpde_draw_ui = not context.scene.rpde_help
        bpy.types.Scene.rpde_settings = False
        bpy.context.scene.aboutdialog = False
#        self.helpLink()
        return {'FINISHED'}

class DocLinkOperator(Operator):
    bl_idname = "processor.doclink"
    bl_description = ""
    bl_label = "help"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context:Context) -> set[str]:
        webbrowser.open(r"https://docs.rapidpipeline.com/docs/componentDocs/integrations/blender-plugin-setup")
        return {'FINISHED'}

class FeedbackOperator(Operator):
    bl_idname = "processor.feedback"
    bl_description = ""
    bl_label = "feedback"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context:Context) -> set[str]:
        webbrowser.open(r"https://webforms.pipedrive.com/f/6q9NnMBNx3wtPNn2wJ49483fTonnF3e7jPK61JL64YqVui7VCxNV15tW9aznGyL3UL")
        return {'FINISHED'}

class ContactSupportOperator(Operator):
    bl_idname = "processor.support"
    bl_description = ""
    bl_label = "support"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context:Context) -> set[str]:
        """
        Callback to open Crisp support chat window, using user's e-mail if available.
        """

        support_url = "https://go.crisp.chat/chat/embed/?website_id=922e6bf3-2bf5-48d4-ba89-5bd58ef411e1"

        # get user's email address from token if available
        user_email = ProcessorLicense.getUserEmail()
        if user_email:
            user_email.replace("@", "%40")
            support_url += f"&user_email={user_email}"

        webbrowser.open(support_url)
        return {'FINISHED'}

class RPDEPanel (Panel):
    bl_idname = "VIEW3D_PT_processor"
    bl_description = "processor"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "RapidPipeline"
    bl_parent_id = "VIEW3D_PT_RapidPipeline"
    bl_label = "processor_output"
    bl_options = {'HIDE_HEADER'}

    @classmethod
    def poll(cls, context:Context) -> bool:
        return context.scene.rpde_detail_mode and (context.scene.rpde_running or context.scene.rpde_error)

    def draw(self, context:Context):
        draw_processor_log(context, self.layout)

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

class MainPanel(Panel):
    bl_idname = "VIEW3D_PT_RapidPipeline"
    bl_label = "RapidPipeline"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "RapidPipeline"

    # height variables for scroll area
    height_diff = 0

    was_successful: bool = False
    was_cancelled: bool = False


    # variables for progress
    progress_dialog: ProgressDialog = None

    def draw_header(self, context:Context):
        pcoll = preview_collections["main"]
        rapidpipeline_icon: bpy.types.Icons = pcoll["rapidPipeline"]
        self.layout.template_icon(icon_value=rapidpipeline_icon.icon_id, scale=1.2)

    def draw_header_preset(self, context: Context):
        pcoll = preview_collections["main"]
        help_icon = pcoll["help"]
        key_icon = pcoll["token_key"]
        settings_icon = pcoll["settings"]
        header_layout = self.layout.row(align=True)
        header_layout.operator(OverrideTokenOperator.bl_idname, icon_value=key_icon.icon_id, text="")
        header_layout.operator(SettingsOperator.bl_idname, icon_value=settings_icon.icon_id, text="")
        header_layout.operator(HelpOperator.bl_idname, icon_value=help_icon.icon_id, text="")
        self.layout.prop(context.scene, "magic_action_versions")

    def draw(self, context:Context):
        pcoll = preview_collections["main"]
        if context.scene.rpde_UI_error:
            drawUIError(self, context)
            return

        if not context.scene.has_license:
            return

        if context.scene.rpde_settings:
            self.layout.prop(context.scene, "rpde_enable_preview", text="Show Preview Image")
            self.layout.prop(context.scene, "rpde_enable_description", text="Show Description")
            self.layout.prop(context.scene, "rpde_detail_mode", text="Expert Mode")
            self.layout.operator(SettingsOperator.bl_idname, text="Back", icon_value=pcoll["cancel"].icon_id)
            return

        if context.scene.rpde_help:
            self.layout.operator(
                DocLinkOperator.bl_idname, text="Plugin Documentation", icon_value=pcoll["documentation"].icon_id)
            self.layout.operator(
                FeedbackOperator.bl_idname, text="Feedback", icon_value=pcoll["feedback"].icon_id)
            self.layout.operator(
                ContactSupportOperator.bl_idname, text="Contact Support", icon_value=pcoll["support"].icon_id)
            self.layout.operator(
                AboutDialog.bl_idname, text="About the Plugin", icon_value=pcoll["about"].icon_id)
            self.layout.operator(
                HelpOperator.bl_idname, text="Back", icon_value=pcoll["cancel"].icon_id)
            return

        try:
            draw_main_panel(self, context, preview_collections)

        except Exception:
            print("ERROR: Could not draw UI Components of RapidPipeline Blender Plugin.")
            bpy.types.Scene.rpde_UI_error = True
            import traceback
            traceback.print_stack()
            traceback.print_exc()

class MagicActionPanel(Panel):
    bl_label = "Magic Action Panel"
    bl_idname = "VIEW3D_PT_processor_magic_action_panel"
    bl_parent_id = "VIEW3D_PT_RapidPipeline"
    bl_space_type = 'VIEW_3D'
    bl_region_type = "UI"
    bl_category = "RapidPipeline"
    bl_options = {'HIDE_HEADER'}


    def draw(self, context:Context):
        if (not context.scene.rpde_detail_mode and
            context.scene.rpde_draw_ui and context.scene.has_license):

            magic_layout = self.layout.row()

            if os.path.isdir(os.path.join(dirname, 'magic-actions')):
                pcoll = preview_collections["main"]
                import_icon = pcoll["import"]
                save_icon = pcoll["save"]

                magic_layout = self.layout.row(align=True)
                magic_layout.scale_x = 1
                magic_layout.alignment = 'LEFT'
                sub = magic_layout.split(factor=0.66)
                left_col = sub.row(align=True)

                if cad_import:
                    left_col.operator(
                        ImportFileOperator.bl_idname, icon_value=import_icon.icon_id, text="Import 3D or CAD File")
                else:
                    left_col.operator(
                        ImportFileOperator.bl_idname, icon_value=import_icon.icon_id, text="Import 3D")

                left_col.operator(ShowExportMenu.bl_idname, icon_value=save_icon.icon_id, text="Export")
                magic_layout = self.layout.row()
                magic_layout = self.layout.row()

            layout = self.layout.box()
            magic_actions_panel(layout, context, preview_collections)

clss = (MainPanel, BooleanPropertyGroup,
        IntegerPropertyGroup, FloatPropertyGroup, LevelOperator, ColorPropertyGroup,
        LoadOperator, SaveOperator, DefaultsOperator, HelpOperator, DocLinkOperator,
        StringPropertyGroup, RPDEPanel,
        GroupWidgetPropertyGroup, CancelProcessorOperator, RetryProcessorOperator,
        RestartUIOperator, SettingsOperator, MagicActionPanel, ContactSupportOperator, FeedbackOperator,
        )

late_reg_clss = (AboutDialogPanel, )

reg, unreg = bpy.utils.register_classes_factory(clss)
late_reg, late_unreg = bpy.utils.register_classes_factory(late_reg_clss)


def drawUIError(panel:Panel, context:Context):
        error_layout = panel.layout.row()
        error_msg = """ERROR: Could not draw UI Components of RapidPipeline Blender Plugin. \n
        Please try to save and restart the Blender scene or contact Customer Support."""

        prettyPrint(panel, error_msg, context)
        error_layout.operator(RestartUIOperator.bl_idname, text="Restart")

#https://blender.stackexchange.com/questions/74052/wrap-text-within-a-panel
def prettyPrint(panel:Panel, text:str, context:Context):
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
                (GroupPanel, Panel, ),
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

# gets a dict of all descriptions of magic action options to be used in setup_proerties
def get_magic_descriptions() -> dict:
    from .magic_actions_operator import get_all_actions
    options_descriptions_dict = {}
    magic_actions = get_all_actions()

    for action in magic_actions:
        for option in action.action_options:
            options_descriptions_dict[get_uuid(option.option_path)] = option.option_description

    return options_descriptions_dict

def setup_properties(schema: dict,
                     parent: dict = None,
                     path: List[str] = [],
                     schema_key:str = "",
                     parent_panel:str = "",
                     magic_descriptions_dict:dict = {}):

    def get_description() -> str:
        if get_uuid(path) in magic_descriptions_dict:
            return magic_descriptions_dict[get_uuid(path)]
        else:
            return schema.get("description", "")

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
                                        schema_key=sub_schema, parent_panel=parent_panel,
                                        magic_descriptions_dict=magic_descriptions_dict)

        if not schema_key:
            continue

        #case only for export
        if key == "items" and attribute_id == "exportArray":
            setup_properties(schema["items"], parent, path, schema_key,
                             parent_panel, magic_descriptions_dict=magic_descriptions_dict)

        if key == 'type':
            if schema['type'] == 'boolean':
                blend_scene_init_setattr(
                    bpy.types.Scene, attribute_id, path=path,
                    value_function=bpy.props.BoolProperty(
                        name="", default=schema['default'], description=get_description()),
                    toggable=('toggleable' in schema))
                add_ui_element_to_panel(path, parent_panel)
            if schema['type'] == 'integer':
                blend_scene_init_setattr(
                    bpy.types.Scene, attribute_id, path=path,
                    value_function=bpy.props.IntProperty(
                        name="", default=schema['default'], min=schema.get('minimum', 0.0),
                        max=schema.get('maximum', 100_000_000), description=get_description()),
                    toggable=('toggleable' in schema))
                add_ui_element_to_panel(path, parent_panel)
            if schema['type'] == 'string':
                blend_scene_init_setattr(
                    bpy.types.Scene, attribute_id, path=path,
                    value_function=bpy.props.StringProperty(
                        name="", default=schema.get('default', ""), description=get_description()),
                    toggable=('toggleable' in schema))
                add_ui_element_to_panel(path, parent_panel)
            if schema['type'] == 'object':
                blend_scene_init_setattr(
                    bpy.types.Scene, attribute_id, path=path,
                    value_function=bpy.props.BoolProperty(name="", default=False, description=get_description()),
                    toggable=('toggleable' in schema))
                add_ui_element_to_panel(path, parent_panel)

            if schema['type'] == 'number':
                if 'percentage' in parent:
                        blend_scene_init_setattr(
                            bpy.types.Scene, attribute_id, path=path,
                            value_function=
                                bpy.props.FloatProperty(
                                    name="",
                                    min=schema['minimum'],
                                    max=schema['maximum'],
                                    default=schema['default'],
                                    subtype='PERCENTAGE',
                                    description=get_description()),
                                    value=schema['default'],
                                    toggable=('toggleable' in schema),
                                    precision=3
                                    )
                        add_ui_element_to_panel(path, parent_panel)
                else:
                    if 'maximum' in schema:
                        value_function = bpy.props.FloatProperty(
                                name="",
                                min=schema.get('minimum', 0.0), max=schema['maximum'],
                                default=schema.get('default', 0.0), description=get_description(),
                                precision=3)
                    else:
                        value_function = bpy.props.FloatProperty(
                                    name="",
                                    min=schema.get('minimum', 0.0), default=schema.get('default', 0.0),
                                    description=get_description(),
                                    precision=3)
                    blend_scene_init_setattr(
                        bpy.types.Scene, attribute_id, path=path,
                        value_function=value_function,
                        toggable=('toggleable' in schema))
                    add_ui_element_to_panel(path, parent_panel)

            if schema['type'] == 'array' and 'default' in schema:
                blend_scene_init_setattr(
                    bpy.types.Scene, attribute_id, path=path,
                    value_function=bpy.props.FloatVectorProperty(
                        name="",
                        default = (schema['default'][:3]), min=0.0, max=1.0, subtype='COLOR',
                        description=get_description()), toggable=('toggleable' in schema))
                add_ui_element_to_panel(path, parent_panel)

        if key == 'enum':
            enum_options = []
            for element in schema['enum']:
                enum_options.append((element,)*3)
            blend_scene_setattr_enum(bpy.types.Scene,
                    property=bpy.props.EnumProperty(name="", items=enum_options, description=get_description()),
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
            blend_scene_setattr_enum(bpy.types.Scene,
                    property=bpy.props.EnumProperty(name="", items=oneof_elements, description=get_description()),
                    path=path_oneof)
            add_ui_element_to_panel(path_oneof, parent_panel)

            path_tmp = path.copy()
            for oneof_sub_schema in schema['oneOf']:
                if isinstance(oneof_sub_schema, dict):
                    setup_properties(schema=oneof_sub_schema,
                                        parent=schema.copy(),
                                        path=path_tmp, schema_key= None,
                                        parent_panel=parent_panel,
                                        magic_descriptions_dict=magic_descriptions_dict)
                path=path_tmp

        path= temp_path



def setup_icons():
    pcoll = bpy.utils.previews.new()
    dirname = os.path.dirname(__file__)
    icons_dict = {
        "rapidPipeline" : ('Icon_solid_green.png', 'rpd_icon.svg'),
        "edit" : ('3dEdit.svg',),
        "import" : ('save.svg','import.svg',),
        "sceneGraphFlattening" : ('sceneGraphFlattening.svg',),
        "meshCulling" : ('meshCulling.svg',),
        "optimize" : ('optimize.svg',),
        "modifier" : ('outcomeModifier.svg',),
        "export" : ('exportArray.svg',),
        "load" : ('load.svg', 'import.svg',),
        "save" : ('blend_import.svg', 'open.svg', 'save.svg',),
        "defaults" : ('restore.svg',),
        "help" : ('blend_help.svg', 'help.svg',),
        "about" : ('info.svg',),
        "run" : ('blend_run.svg', 'run.svg', 'magic.svg'),
        "Magic_action_placeholder" : ('Blender Background.PNG',),
        "token_key": ('blend_key.svg','key.svg',),
        "settings": ('blend_settings.svg' ,'settings.svg',),
        "documentation": ('doc.svg',),
        "feedback": ('feedback.svg',),
        "cancel": ('cancel.svg',),
        "support": ('support.svg',)
    }

    for file, file_names in icons_dict.items():
        common_icon_found = False
        for file_name in file_names:
            commons_icon_dir = os.path.join(dirname, '3DProcessorPluginsCommon', 'assets', 'icons', file_name)
            if os.path.isfile(commons_icon_dir):
                pcoll.load(file, commons_icon_dir, 'IMAGE')
                common_icon_found = True
                break

        if not common_icon_found:
            for file_name in file_names:
                resources_dir = os.path.join(dirname, 'resources', 'images', file_name)
                if os.path.isfile(resources_dir):
                    pcoll.load(file, resources_dir, 'IMAGE')
                    break

    magic_action_path = os.path.join(dirname, 'magic-actions', 'actions')
    if os.path.isdir(os.path.join(magic_action_path)):
        for version in os.listdir(magic_action_path):
            if version != "Custom":
                for type in ('import', 'processing', 'export'):
                    magic_action_folder = os.path.join(magic_action_path, version, type)
                    if os.path.isdir(magic_action_folder):
                        for magic_action in os.listdir(magic_action_folder):
                            if os.path.isdir(os.path.join(magic_action_folder, magic_action)):
                                icon_dir = os.path.join(magic_action_folder, magic_action, 'icon-dark.svg')
                                image_dir = os.path.join(magic_action_folder, magic_action, "image.png")
                                pcoll.load(f"magic_action_{version}_{magic_action}", icon_dir, 'IMAGE')
                                if os.path.isfile(image_dir):
                                    pcoll.load(f"magic_action_image_{version}_{magic_action}", image_dir, 'IMAGE')
                                setattr(bpy.types.Scene, f"magic_action_{version}_{magic_action}",
                                        pcoll[f"magic_action_{version}_{magic_action}"])

    preview_collections["main"] = pcoll

    pcoll = preview_collections["main"]
    bpy.types.Scene.icon_import = pcoll["import"]
    bpy.types.Scene.icon_3dEdit = pcoll["edit"]
    bpy.types.Scene.icon_sceneGraphFlattening = pcoll["sceneGraphFlattening"]
    bpy.types.Scene.icon_meshCulling = pcoll["meshCulling"]
    bpy.types.Scene.icon_optimize = pcoll["optimize"]
    bpy.types.Scene.icon_outcomeModifier = pcoll["modifier"]
    bpy.types.Scene.icon_export = pcoll["export"]
    bpy.types.Scene.icon_cancel = pcoll["cancel"]


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
            magic_descriptions_dict = get_magic_descriptions()
            setup_properties(schema, path=[], magic_descriptions_dict=magic_descriptions_dict)

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
    bpy.types.Scene.level = bpy.props.EnumProperty(items=level, default=2)

    bpy.types.Scene.rpde_output = ""
    bpy.types.Scene.rpde_percentage = bpy.props.IntProperty(
        default=0, min=0, max=100, step=1, subtype='PERCENTAGE', options={'SKIP_SAVE'})
    bpy.types.Scene.has_license = ProcessorLicense.performLicenseCheck(None)
    bpy.types.Scene.use_token_future_sessions = bpy.props.BoolProperty(
        default=False,
        description="If checked, the current Authentication Token will be saved to disk for future usage.")
    bpy.types.Scene.t_and_c_agreed = bpy.props.BoolProperty(
        default=False,
        description="If checked, you agree to the Terms and Conditions of RapidPipeline usage.")
    bpy.types.Scene.api_token = bpy.props.StringProperty(default="")
    bpy.types.Scene.override_token = False
    bpy.types.Scene.rpde_settings = False
    bpy.types.Scene.rpde_help = False
    bpy.types.Scene.rpde_draw_ui = True
    bpy.types.Scene.rpde_enable_preview = bpy.props.BoolProperty(
        default=True,
        description="If checked, enables previews of Actions.")
    bpy.types.Scene.rpde_enable_description = bpy.props.BoolProperty(
        default=True,
        description="If checked, enables descriptions of Actions.")
    bpy.types.Scene.rpde_running = False
    bpy.types.Scene.rpde_error = False
    bpy.types.Scene.rpde_cancel = False
    bpy.types.Scene.rpde_UI_error = False
    bpy.types.Scene.rpde_export = False
    bpy.types.Scene.rpde_detail_mode = bpy.props.BoolProperty(
        default=False,
        description="Switches the views between Actions and Expert Mode.")

    dirname = os.path.dirname(__file__)
    magic_action_versions_path = os.path.join(dirname, "magic-actions", "actions")
    versions=[(version, version, version) for version in os.listdir(magic_action_versions_path) if version != "Custom"]
    bpy.types.Scene.magic_action_versions = bpy.props.EnumProperty(
            name="",
            description="Versions of Actions",
            items=versions,
            default=versions[-1][0],
            update=change_magic_action_version
        )

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
            reset_magic_actions()

    bpy.app.timers.register(wait_for_late_register, first_interval=0.2)
    bpy.app.handlers.load_post.append(wait_for_late_register)  #wait for context to be fully loaded

    if 'darwin' == platform:
        print("Mac detected")
        removeQuarantineFlagOnMac()
    elif 'linux' == platform:
        setupLinux()

def change_magic_action_version(self:Any, context:Context):
    from .draw_ui import change_drawn_version
    from .magic_actions_operator import set_version
    set_version(context.scene.magic_action_versions)
    change_drawn_version(context.scene.magic_action_versions)

def reset_magic_actions():
    # press first magic_action_button in ui
    from .magic_actions_operator import MagicAction, get_magic_actions
    magic_actions_sorted:list[MagicAction] = get_magic_actions()
    first_magic_action = magic_actions_sorted[0].action_name
    bpy.ops.processor.magic_action_button(magic_action_str=first_magic_action)

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
