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

from typing import Any
import traceback

import bpy


def deselect_all():
    try:
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')
    except Exception:  # noqa: S110
        pass

def set_object_mode():
    try:
        bpy.ops.object.mode_set(mode='OBJECT')
    except Exception:  # noqa: S110
        pass

# There are different ways for animation to be handled in blender the default behavior for the blender glb exporter is
# to convert animations into  NLA but only the first one is enabled. This function enables all animations, we could
# alternatively also convert all animations into key frames if this is requested
def fix_animation(selected_objects:Any):
    for obj in selected_objects:
        anim = obj.animation_data
        if anim is None:
            continue

        anim.use_nla = True
        nla_tracks = anim.nla_tracks
        if nla_tracks:
            if anim.action:
                anim.action = None  # clears active action so NLA takes over
            for track in nla_tracks:
                track.mute = False
                for strip in track.strips:
                    strip.mute = False

        # Convert to Keyframes:
        #NOTE this conversion is lossy since NLA can be layered but keyframes can not
#            anim.use_nla = False
#            if anim.action is None and anim.nla_tracks:
#                for track in anim.nla_tracks:
#                    if track.strips:
#                        anim.action = track.strips[0].action
#                        break


def select_children():
    try:
        selected_obj = bpy.context.selected_objects
        for obj in selected_obj:
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.select_grouped(type='CHILDREN_RECURSIVE', extend=True)
            obj.select_set(True)
    except Exception:
        traceback.print_stack()
        traceback.print_exc()
