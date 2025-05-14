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
import webbrowser
from typing import Any

import bpy  # type: ignore

from .json_utils import JSonUtils


class CancelTokenOperator(bpy.types.Operator):
    bl_idname = "processor.cancel_token"
    bl_description = "cancel_token"
    bl_label = "Cancel"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context:bpy.types.Context) -> set[str]:
        bpy.types.Scene.has_license = True
        bpy.types.Scene.override_token = False
        return {'FINISHED'}

class EnterLicenseOperator(bpy.types.Operator):
    bl_idname = "processor.enter_license"
    bl_description = "enter_license"
    bl_label = "Enter License"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context:bpy.types.Context) -> set[str]:
        if context.scene.t_and_c_agreed:
            bpy.types.Scene.has_license = ProcessorLicense.overrideSessionLicense(context)
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, "Please accept the Terms and Conditions to continue!")
            return {'FINISHED'}

class CreateTokenOperator(bpy.types.Operator):
    bl_idname = "processor.create_token"
    bl_description = "Create API Token"
    bl_label = "Create API Token"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context:bpy.types.Context) -> set[str]:
        self.createToken()
        return {'FINISHED'}

    def createToken(self):
        webbrowser.open(r"https://app.rapidpipeline.com/api_tokens")

class OpenLinkOperator(bpy.types.Operator):
    bl_idname = "wm.open_link"
    bl_label = "Open Link"

    url: bpy.props.StringProperty()

    def execute(self, context):
        webbrowser.open(self.url)
        return {'FINISHED'}

class LicensePanel(bpy.types.Panel):
    bl_idname = "VIEW3D_PT_license"
    bl_description = "license"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "RapidPipeline"
    bl_parent_id = "VIEW3D_PT_RapidPipeline"
    bl_label = "Set RapidPipeline API Token"
    bl_options = {'HIDE_HEADER'}

    warning_label = "A RapidPipeline API License Token file was not found."

    label_str_1 = "Please insert your API token. "
    label_str_2 = "By default, it will be valid for the current session only."

    t_and_c_str_1 = "Please take time to read our General Terms and Conditions carefully and confirm below."

    @classmethod
    def poll(cls, context:bpy.types.Context) -> bool:
        return not context.scene.has_license

    def draw(self, context:bpy.types.Context):
        if not context.scene.has_license:
            self.layout.label(text=self.warning_label)
            self.layout.label(text=self.label_str_1)
            self.layout.label(text=self.label_str_2)
            _ = self.layout.row()

            # add checkbox to save to disk
            self.layout.prop(context.scene, "use_token_future_sessions", text="Use Token for future sessions")
            self.layout.prop(context.scene, "api_token", text="Insert API Token")

            _ = self.layout.row()
            t_c_layout = self.layout.row()
            t_c_layout.label(text=self.t_and_c_str_1)
            t_c_layout = self.layout.row()
            op = t_c_layout.operator(OpenLinkOperator.bl_idname, text="Terms and Conditions", icon='URL')
            op.url = "https://rapidpipeline.com/en/general-terms-and-conditions"
            _ = self.layout.row()
            self.layout.prop(context.scene, "t_and_c_agreed", text="I have read and agree the Terms and Conditions")
            _ = self.layout.row()
            _ = self.layout.row()
            panel_layout = self.layout.row()
            panel_layout.operator(EnterLicenseOperator.bl_idname, text="Save Token")
            panel_layout.operator(CreateTokenOperator.bl_idname, text="Create API Token")
            if context.scene.override_token:
                panel_layout = self.layout.row()
                panel_layout.operator(CancelTokenOperator.bl_idname, text="Cancel")


class ProcessorLicense:
    LICENSE_FILE = os.path.join(os.environ["RPDP_PROCESSOR_DCC_DATA"], "rpd_account.json")
    TEMP_LICENSE_FILE = os.path.join(os.environ["RPDP_PROCESSOR_DCC_DATA"], "temp_rpd_account.json")

    @staticmethod
    def hasLicense() -> bool:
        # if the plugin has its own license file, use it
        if os.path.isfile(ProcessorLicense.LICENSE_FILE):
            # sets envvar for the Plugin License File
            os.environ["RPD_ACCOUNTFILE"] = ProcessorLicense.LICENSE_FILE
            return True

        # if there's no license file for the plugin, see global envvar
        if "RPD_ACCOUNTFILE" not in os.environ:
            return False
        return os.path.isfile(os.environ["RPD_ACCOUNTFILE"])

    @staticmethod
    def getAPIToken() -> str:
        if not os.environ.get("RPD_ACCOUNTFILE", ""):
            return ""
        account_data = JSonUtils.loadJSON(os.environ["RPD_ACCOUNTFILE"])
        return account_data["token"]

    @staticmethod
    def createLicenseFile(token: str, is_temp: bool) -> str:
        if is_temp:
            file_path = ProcessorLicense.TEMP_LICENSE_FILE
        else:
            file_path = ProcessorLicense.LICENSE_FILE

        account_data = {"host": "api.rapidpipeline.com", "token": token}

        print(f"Creating account file {file_path}...")
        if not JSonUtils.saveJSON(account_data, file_path):
            print("could not create file")
            return None
        return file_path

    @staticmethod
    def overrideSessionLicense(context: Any) -> Any:
        def createLicenseFromInput() -> bool:
            token = context.scene.api_token
            if token:
                # create license file, permanent or not, and sets envvar accordingly
                is_temp = not context.scene.use_token_future_sessions
                account_file = ProcessorLicense.createLicenseFile(token, is_temp)
                if account_file is not None:
                    os.environ["RPD_ACCOUNTFILE"] = account_file
                    return True
            return False

        return createLicenseFromInput()

    @staticmethod
    def performLicenseCheck(parent: Any) -> bool:
        """
        Attempts to find a license file, requesting user to input a valid token if necessary.
        Returns True if any token is provided, or False if user canceled process.
        """
        if not ProcessorLicense.hasLicense():
            return False
        return True

clss = (
    LicensePanel, EnterLicenseOperator, CreateTokenOperator, CancelTokenOperator,
    )

reg, unreg = bpy.utils.register_classes_factory(clss)

def register():
    reg()

def unregister():
    unreg()
