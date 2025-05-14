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
import traceback
from typing import Any, List, Union


class JSonUtils:
    @staticmethod
    def loadJSON(json_file: str) -> dict:
        """
        Opens JSON file and returns Python dictionary.
        """
        print(f"Loading JSON file {json_file}...")
        if not os.path.isfile(json_file):
            raise ValueError(f"The JSon file {json_file} does not exist.")
        try:
            with open(json_file, "r", encoding="utf-8") as json_handle:
                json_value = json.load(json_handle)
                if not json_value:
                    raise ValueError(f"The JSon file {json_file} is invalid.")
                return json_value
        except Exception:
            print(f"Unable to open JSon file: {json_file}.")
            raise

    @staticmethod
    def saveJSON(dictionary: dict, file_path: str) -> bool:
        """
        Saves Python dictionary to JSON file, returning False on failure, True otherwise.
        """
        try:
            if not os.path.isdir(os.path.dirname(file_path)):
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as json_handle:
                json.dump(dictionary, json_handle, indent=2)
                json_handle.flush()
            return True
        except Exception:
            print(traceback.format_exc())
            return False

    @staticmethod
    def getSchemaDefs(schema: dict) -> dict:
        """
        Returns definitions of a schema, solving possible intra-references.
        """

        def get_schema_defs_recursive(schema: Union[dict, list, Any]) -> List[dict]:
            definitions = []
            if r"$defs" in schema:
                definitions.append(schema[r"$defs"])
            else:
                if isinstance(schema, list):
                    for value in schema:
                        definitions.extend(get_schema_defs_recursive(value))
                elif isinstance(schema, dict):
                    for value in schema.values():
                        definitions.extend(get_schema_defs_recursive(value))
            return definitions

        definitions = get_schema_defs_recursive(schema)[0]
        references = set()
        while True:
            replaced_references = set()
            new_definition, replaced_references = JSonUtils.solveSchemaRefs(definitions, definitions, set())
            if new_definition == definitions:
                return definitions
            if references == replaced_references:
                print("ERROR: circluar dependency in schema definitions!")
                return definitions
            references = replaced_references
            definitions = new_definition

    @staticmethod
    def solveSchemaRefs(
        schema: Union[dict, list, Any], schema_defs: dict, replaced_definitions: set[str] = set()
    ) -> dict:
        """
        Solves a schema, replacing references by their definition values.
        """
        dict_out = {}

        if isinstance(schema, dict):
            for k, v in schema.items():
                if r"$ref" in k:
                    ref_key = str(schema["$ref"]).split(r"#/$defs/")[1]
                    replaced_definitions.add(ref_key)
                    if ref_key in schema_defs:
                        for entry_k, entry_v in schema_defs[ref_key].items():  # unpack definition
                            if entry_k == r"$ref":  # definition points to another reference
                                if ref_key == entry_v.split(r"#/$defs/")[1]:  # reference points to itself
                                    print(f"ERROR: reference {ref_key} leads to own definition")
                                    return dict_out, replaced_definitions
                            dict_out[entry_k] = entry_v
                    else:
                        print(f"ERROR: definition {ref_key} for reference not found")
                        return dict_out, replaced_definitions
                else:
                    dict_out[k], replaced_definitions = JSonUtils.solveSchemaRefs(v, schema_defs, replaced_definitions)
            return dict_out, replaced_definitions
        elif isinstance(schema, list):
            dict_out = []
            replaced_definitions_in_list = set()
            for value in schema:
                refs, replaced_definitions = JSonUtils.solveSchemaRefs(value, schema_defs, replaced_definitions)
                dict_out.append(refs)
                replaced_definitions_in_list.update(replaced_definitions)
            return dict_out, replaced_definitions_in_list
        else:
            dict_out = schema
            return dict_out, replaced_definitions
