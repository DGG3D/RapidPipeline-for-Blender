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

import functools
import os
import subprocess
import hashlib
import base64

import bpy  # type: ignore

from .gui_commons import ProcessorPlugin

nodes = []

class RunPipeline:
    @staticmethod
    def runPipeline(processor_input_file:str, rpde_config:str, output_folder:str, copied_nodes:list) -> None:
        """
        Disables elements, and starts RapidPipeline process with the current UI settings.
        A file with the current settings is exported and validated.
        """

        # exports model to predefined file location
        input_file = processor_input_file

        # process model with RapidPipeline
        os.chdir(os.path.dirname(ProcessorPlugin.getRPDEPath()))
        rpde_exec = "./rpde"
        rpde_exec = ProcessorPlugin.getRPDEPath()
        pipeline_cmd = [
            rpde_exec,
            "--read_config", rpde_config,
            "-i", input_file,
            "-o", output_folder,
            "--run"]

        hash_object = hashlib.sha1(str.encode(''.join(pipeline_cmd)))
        h = base64.b64encode(hash_object.digest()).decode()

        pipeline_cmd += ['--signature', h]

        bpy.types.Scene.rpde_cmd = "**".join(pipeline_cmd)
        global nodes
        nodes = copied_nodes
        bpy.ops.wm.modal_timer_operator()


class ModalTimerOperator(bpy.types.Operator):
    """
    Operator which runs itself from a timer
    Runns rpde on a modal timer to get the output of the rpde subprocess 
    reflected in the UI
    """
    bl_idname = "wm.modal_timer_operator"
    bl_label = "Modal Timer Operator"

    _timer = None
    value = ""
    result = None
    subprocess_poll = None
    full_log = ""
    def close_rpde_session(self, context:bpy.types.Context):
        print("RPDE Process finished")
        bpy.types.Scene.rpde_output = ""
        bpy.ops.processor.run()

    def modal(self, context:bpy.types.Context, event:bpy.types.Event) -> set[str]:
        if event.type == 'TIMER':
            if context.scene.rpde_cancel:
                self.result.kill()
                bpy.types.Scene.rpde_cancel = False
                print("cancle rpde")
                bpy.ops.object.select_all(action='DESELECT')
                for node in nodes:
                    bpy.data.objects[node.name].select_set(True)
                    original_node = node.name.split("_processed")[0]
                    bpy.data.objects[original_node].hide_set(False)
                bpy.ops.object.delete()
                return{'FINISHED'}
            if self.result:
                self.subprocess_poll = self.result.poll()
                rpde_output = ""
                rpde_error = ""
                rpde_output = str(self.result.stdout.readline())

                if "" != rpde_output:
                    print(rpde_output)
                    if "batch processing" not in rpde_output:
                        self.full_log += (rpde_output)

                if rpde_output and len(rpde_output) > 1:
                    # displays the percentage status of rpde
                    if '% [' in rpde_output:
                        bpy.types.Scene.rpde_output = self.value
                        context.scene.rpde_percentage = int(rpde_output.split('%')[0])
                    else:
                        bpy.types.Scene.rpde_output = rpde_output
                        self.value = rpde_output
                    context.area.tag_redraw()

                if self.subprocess_poll is not None:
                    if self.subprocess_poll != 0:
                        rpde_error = str(self.result.stderr.readline())
                        if "" != rpde_error:
                            print(rpde_error)
                            self.full_log += (rpde_error)
                        bpy.types.Scene.rpde_error = True
                        bpy.types.Scene.rpde_output = self.full_log
                        context.area.tag_redraw()
                        return {'FINISHED'}
                    else:
                        print("close session")
                        bpy.app.timers.register(functools.partial(self.close_rpde_session, context), first_interval=1)
                        return {'FINISHED'}
            else:
                print("found error in execution")
                return {'FINISHED'}
        return {'PASS_THROUGH'}

    def execute(self, context:bpy.types.Context) -> set[str]:
        """
        Executes a pipeline command, displaying a progress dialog with a Cancel button.
        """
        # reset flags
        self.was_successful = False
        self.was_cancelled = False
        bpy.types.Scene.rpde_cancel = False

        command_arguments:list = context.scene.rpde_cmd.split("**")

        bpy.types.Scene.rpde_running = True
        self.result = subprocess.Popen(
            command_arguments, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        wm = context.window_manager
        self._timer = wm.event_timer_add(0.01, window=context.window)
        wm.modal_handler_add(self)

        return {'RUNNING_MODAL'}

    def cancel(self, context:bpy.types.Context):
        wm = context.window_manager
        wm.event_timer_remove(self._timer)


clss = (
    ModalTimerOperator,
)

register, unregister = bpy.utils.register_classes_factory(clss)
