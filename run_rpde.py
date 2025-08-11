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

import base64
import functools
import hashlib
import os
import subprocess

try:
    import tomllib
except ModuleNotFoundError:
    pass

import traceback

import bpy  # type: ignore

from .gui_commons import ProcessorPlugin

nodes = []
suppressed_messages = ["batch processing", "cloud session"]

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
        dirname = os.path.dirname(__file__)
        try:
            blender_manifest = os.path.join(dirname, 'blender_manifest.toml')
            with open(blender_manifest, 'rb') as f:
                blender_manifest = tomllib.load(f)
            blender_plugin_info = f"bl_{blender_manifest['version']}"

            pipeline_cmd += ['--signature', h, blender_plugin_info]
        except:
            #TODO tomllib does not work for blender 4.0
            pipeline_cmd += ['--signature', h, "bl_1.0.0"]

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
        bpy.ops.processor.run()

    @staticmethod
    def _non_blocking_readlines(f, chunk=64):
        """
        Iterate over lines, yielding b'' when nothings left
        or when new data is not yet available.
        """

        fd = f.fileno()
        pipe_non_blocking_set(fd)

        blocks = []

        while True:
            try:
                data = os.read(fd, chunk)
                if not data:
                    # case were reading finishes with no trailing newline
                    yield b''.join(blocks)
                    blocks.clear()
            except PortableBlockingIOError as ex:
                if not pipe_non_blocking_is_error_blocking(ex):
                    raise ex

                yield b''
                continue

            while True:
                pos_n = data.find(b'\n')
                pos_r = data.find(b'\r')
                positions = [p for p in (pos_n, pos_r) if p != -1]

                if not positions:
                    break

                n = min(positions)

                yield b''.join(blocks) + data[:n + 1]
                data = data[n + 1:]
                blocks.clear()
            blocks.append(data)

    def _report_output(self) -> tuple[str, set[str]]:
        stdout_line_iter, stderr_line_iter = self._buffer_iter
        output_text = ""
        error_text = ""
        output_type = {""}
        for line_iter, report_type in (
                (stdout_line_iter, {'INFO'}),
                (stderr_line_iter, {'WARNING'})
                ):
            while True:
                line = next(line_iter).rstrip()  # rstrip all, to include \r on windows
                if not line:
                    break
                if report_type == {'INFO'}:
                    output_text = line.decode(encoding='utf-8', errors='surrogateescape')
                else:
                    error_text = line.decode(encoding='utf-8', errors='surrogateescape')
                output_type = report_type
        return (output_text, error_text, output_type)

    def _wm_enter(self, context):
        wm = context.window_manager
        window = context.window
        bpy.types.Scene.rpde_output = ""
        props = bpy.context.scene.rpde_processor_log
        props.items.clear()

        self._timer = wm.event_timer_add(0.1, window=window)
        context.window.cursor_set('WAIT')

    def _wm_exit(self, context):
        wm = context.window_manager
        window = context.window

        context.scene.rpde_percentage = 0
        wm.event_timer_remove(self._timer)
        window.cursor_set('DEFAULT')

    def modal(self, context:bpy.types.Context, event:bpy.types.Event) -> set[str]:
        rpde_processor_log = bpy.context.scene.rpde_processor_log
        try:
            if event.type == 'TIMER':
                if context.scene.rpde_cancel:
                    self.result.kill()
                    bpy.types.Scene.rpde_cancel = False
                    print("cancel rpde")
                    bpy.ops.object.select_all(action='DESELECT')
                    for node in nodes:
                        bpy.data.objects[node.name].select_set(True)
                        original_node = node.name.split("_processed")[0]
                        bpy.data.objects[original_node].hide_set(False)
                    bpy.ops.object.delete()
                    return{'FINISHED'}
                if self.result:
                    self.subprocess_poll = self.result.poll()
                    report_output = self._report_output()
                    rpde_output = ""
                    rpde_error = ""
                    if report_output:
                        rpde_output = report_output[0]
                        rpde_error = report_output[1]

                    if rpde_output and len(rpde_output) > 1:
                        print(rpde_output)
                        # displays the percentage status of rpde
                        if '% [' in rpde_output:
                            bpy.types.Scene.rpde_output = self.value
                            context.scene.rpde_percentage = int(rpde_output.split('%')[0])
                        # display other messages
                        else:
                            suppress_msg = False
                            for msg_part in suppressed_messages:
                                if msg_part in rpde_output:
                                    suppress_msg = True
                            if not suppress_msg:
                                bpy.types.Scene.rpde_output += "\n"
                                bpy.types.Scene.rpde_output += rpde_output
                                rpde_processor_log.items.add().name = rpde_output
                                rpde_processor_log.RPDE_message = len(rpde_processor_log.items) - 1
                                self.value = rpde_output
                        if context.area:
                            context.area.tag_redraw()
                    if rpde_error and len(rpde_error) > 1:
                        rpde_processor_log.items.add().name = rpde_error
                        rpde_processor_log.RPDE_message = len(rpde_processor_log.items) - 1
                        if context.area:
                            context.area.tag_redraw()

                    # rpde execution finished:
                    if self.subprocess_poll is not None:
                        # rpde not successful:
                        if self.subprocess_poll != 0:
                            # log last output
                            if "" != rpde_output:
                                suppress_msg = False
                                for msg_part in suppressed_messages:
                                    if msg_part in rpde_output:
                                        suppress_msg = True
                                if not suppress_msg:
                                    self.full_log += (rpde_output)

                            # log last error
                            if "" != rpde_error:
                                print(rpde_error)
                                self.full_log += (rpde_error)
                            bpy.types.Scene.rpde_error = True
                            bpy.types.Scene.rpde_output = self.full_log
                            rpde_processor_log.items.add().name = rpde_error
                            rpde_processor_log.RPDE_message = len(rpde_processor_log.items) - 1
                            if context.area:
                                context.area.tag_redraw()
                            rpde_processor_log.items.add().name = "RPDE interrupted!"
                            rpde_processor_log.RPDE_message = len(rpde_processor_log.items) - 1
                            self._wm_exit(context)
                            return {'FINISHED'}
                        # rpde successful:
                        else:
                            print("close session")
                            bpy.app.timers.register(functools.partial(self.close_rpde_session, context), first_interval=1)
                            self.report({'INFO'}, "RPDE finished successfully.")
                            rpde_processor_log.items.add().name = "RPDE finished successfully."
                            rpde_processor_log.RPDE_message = len(rpde_processor_log.items) - 1
                            self._wm_exit(context)
                            return {'FINISHED'}
                else:
                    print("found error in execution")
                    return {'FINISHED'}
        except Exception:
            print("Found error in execution!")
            traceback.print_stack()
            traceback.print_exc()
            bpy.types.Scene.rpde_error = "Found error in execution!"
            self._wm_exit(context)
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

        self._buffer_iter = (
                iter(self._non_blocking_readlines(self.result.stdout)),
                iter(self._non_blocking_readlines(self.result.stderr)),
                )

        wm = context.window_manager
        wm.modal_handler_add(self)

        self._wm_enter(context)

        return {'RUNNING_MODAL'}

    def cancel(self, context:bpy.types.Context):
        self._wm_exit(context)
        self._process.kill()
        wm = context.window_manager
        wm.event_timer_remove(self._timer)


#source: https://blender.stackexchange.com/questions/45731/how-to-run-an-external-command-showing-its-progress-without-locking-blender-e

# ----------------------------------------------------------------------------
# Portable non-blocking pipe.
#
# This is really black magic on ms-windows!

if os.name == "nt":
    def pipe_non_blocking_set(fd):
        # Constant could define globally but avoid polluting the name-space
        # see: https://stackoverflow.com/a/35052424/432509
        import msvcrt
        from ctypes import POINTER, WinError, byref, windll, wintypes
        from ctypes.wintypes import BOOL, DWORD, HANDLE

        LPDWORD = POINTER(DWORD)

        PIPE_NOWAIT = wintypes.DWORD(0x00000001)

        def pipe_no_wait(pipefd):
            SetNamedPipeHandleState = windll.kernel32.SetNamedPipeHandleState
            SetNamedPipeHandleState.argtypes = [HANDLE, LPDWORD, LPDWORD, LPDWORD]
            SetNamedPipeHandleState.restype = BOOL

            h = msvcrt.get_osfhandle(pipefd)

            res = windll.kernel32.SetNamedPipeHandleState(h, byref(PIPE_NOWAIT), None, None)
            if res == 0:
                print(WinError())
                return False
            return True

        return pipe_no_wait(fd)


    def pipe_non_blocking_is_error_blocking(ex):
        if not isinstance(ex, PortableBlockingIOError):
            return False
        from ctypes import GetLastError
        ERROR_NO_DATA = 232

        return (GetLastError() == ERROR_NO_DATA)

    PortableBlockingIOError = OSError
else:
    def pipe_non_blocking_set(fd):
        import fcntl
        fl = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
        return True

    # only to keep compatibility with nt version
    def pipe_non_blocking_is_error_blocking(ex):
        if not isinstance(ex, PortableBlockingIOError):
            return False
        return True

    PortableBlockingIOError = BlockingIOError

# end magic!
# ----------------------------------------------------------------------------

clss = (
    ModalTimerOperator,
)

register, unregister = bpy.utils.register_classes_factory(clss)
