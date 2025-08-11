
import os
import json
import base64
import hashlib
from typing import List, Union, Any, Dict
import xml.etree.ElementTree as ET

def get_local_folder():
    return __file__

def parseTextFile(file_path: str, encoding: bool = "utf-8") -> List[str]:
    """
    Utility function to open a text file in read mode, and parse it into
    a list of strings/lines.
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"The file {file_path} doesn't exist.")

    with open(file_path, "r", encoding=encoding) as file_handle:
        return file_handle.readlines()

def getXMLAttributes(file_path:str) -> dict:
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"Unable to find XML File: {file_path}")
    tree = ET.parse(file_path)
    root = tree.getroot()
    return root.attrib

#-------------------------------------------------------------------------------------- JSON tools

def loadJSON(json_file: str) -> dict:
    """
    Opens JSON file and returns Python dictionary.
    """
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

def saveJSON(dictionary: dict, file_path: str) -> bool:
    """
    Saves Python dictionary to JSON file, returning False on failure, True otherwise.
    """
    try:
        if not os.path.isdir(os.path.dirname(file_path)):
            os.makedirs(os.path.dirname(file_path))
        with open(file_path, "w", encoding="utf-8") as json_handle:
            json.dump(dictionary, json_handle, indent=4, ensure_ascii=True)
            json_handle.flush()
    except Exception:
        print(f"Unable to save JSon file: {file_path}")
        raise

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
        new_definition, replaced_references = solveSchemaRefs(definitions, definitions, set())
        if new_definition == definitions:
            return definitions
        if references == replaced_references:
            print("ERROR: circular dependency in schema definitions!")
            return definitions
        references = replaced_references
        definitions = new_definition

def solveSchemaRefs(schema: Union[dict, list, Any], schema_defs: dict, replaced_definitions: set[str] = None) -> dict:
    """
    Solves a schema, replacing references by their definition values.
    """
    dict_out = {}

    if replaced_definitions is None:
        replaced_definitions = set()

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
                dict_out[k], replaced_definitions = solveSchemaRefs(v, schema_defs, replaced_definitions)
        return dict_out, replaced_definitions
    elif isinstance(schema, list):
        dict_out = []
        replaced_definitions_in_list = set()
        for value in schema:
            refs, replaced_definitions = solveSchemaRefs(value, schema_defs, replaced_definitions)
            dict_out.append(refs)
            replaced_definitions_in_list.update(replaced_definitions)
        return dict_out, replaced_definitions_in_list
    else:
        dict_out = schema
        return dict_out, replaced_definitions

def getSchemaPropertyFromPath(input_dict:dict, path:str):
    """
    Recursively searches a schema given a path to a setting. Assumes a "." divisor.
    """
    input_type = input_dict.get("type", None)

    result = path.split(".", maxsplit=1)

    # if length of result is 1, that means we got to the result
    if len(result) == 1:
        next_setting = result[0]
        if input_type == "object" and "oneOf" not in input_dict:
            return input_dict["properties"][next_setting], next_setting
        elif input_type == "object" and "oneOf" in input_dict:
            next_input = next((i for i in input_dict["oneOf"] if next_setting in i.get("properties", {})), {})
            if not next_input:
                return None, None
            return next_input["properties"][next_setting], next_setting

    # here we still have more parts to the path, recurse
    next_setting, next_path = result[0], result[1]

    if not input_type:
        return None, None
    if input_type == "object" and "oneOf" not in input_dict:
        return getSchemaPropertyFromPath(input_dict["properties"][next_setting], next_path)
    elif input_type == "object" and "oneOf" in input_dict:
        next_input = next((i for i in input_dict["oneOf"] if next_setting in i.get("properties", {})), {})
        if not next_input:
            return None, None
        return getSchemaPropertyFromPath(next_input["properties"][next_setting], next_path)
    elif input_type == "array":
        next_input = input_dict.get("items", {}).get("properties", {})
        if not next_input or next_setting not in next_input:
            return None, None
        return getSchemaPropertyFromPath(next_input[next_setting], next_path)
    return None, None

def getSettingValueFromPath(input_dict:dict, path:str, default:Any, full_path:str):
    """
    Recursively searches a setting dict given a path and returns its value. Assumes a "." divisor.
    """
    result = path.split(".", maxsplit=1)
    if len(result) == 1:
        # in some cases, we might be exposing something that's not in the preset config
        if result[0] not in input_dict:
            return default
        return input_dict[result[0]]

    # here we still have more parts to the path, recurse
    next_setting, next_path = result[0], result[1]
    next_input = input_dict.get(next_setting, None)
    if not next_input:
        print(f"Unable to find path in settings preset: {full_path}")
        print(f"Using default of: {default}")
        return default
    elif next_setting == "export" and isinstance(next_input, list):
        next_input = next_input[0]
        if not next_input:
            print(f"Unable to find path in export settings preset: {full_path}")
            print(f"Using default of: {default}")
            return default
    return getSettingValueFromPath(next_input, next_path, default, full_path)

def setSettingValueFromPath(input_dict:dict, path:str, value:Any, full_path:str):
    """
    Recursively searches a setting dict given a path. Assumes a "." divisor.
    """
    result = path.split(".", maxsplit=1)
    if len(result) == 1:
        input_dict[result[0]] = value
        return

    # here we still have more parts to the path, recurse
    next_setting, next_path = result[0], result[1]
    next_input = input_dict.get(next_setting, None)
    if not next_input:
        print()
        print(f"Next Input: {next_input} - Next Setting: {next_setting} - Next Path: {next_path}")
        print(f"Unable to find path: {full_path}")
        print()
        return
    elif next_setting == "export" and isinstance(next_input, list):
        if not next_input[0]:
            print()
            print(f"Next Input: {next_input} - Next Setting: {next_setting} - Next Path: {next_path}")
            print(f"Unable to find path in Export: {full_path}")
            print()
            return
        next_input = next_input[0]
    setSettingValueFromPath(next_input, next_path, value, full_path)

def removeSettingFromPath(input_dict:dict, path:str, full_path:str):
    """
    Recursively searches a setting dict given a path. Assumes a "." divisor.
    """
    result = path.split(".", maxsplit=1)
    if len(result) == 1:
        input_dict.pop(result[0])
        return

    # here we still have more parts to the path, recurse
    next_setting, next_path = result[0], result[1]
    next_input = input_dict.get(next_setting, None)
    if not next_input:
        print()
        print(f"Next Input: {next_input} - Next Setting: {next_setting} - Next Path: {next_path}")
        print(f"Unable to find path: {full_path}")
        print()
        return
    elif next_setting == "export" and isinstance(next_input, list):
        next_input = next_input[0]
        if not next_input:
            print()
            print(f"Next Input: {next_input} - Next Setting: {next_setting} - Next Path: {next_path}")
            print(f"Unable to find path in Export: {full_path}")
            print()
            return
    removeSettingFromPath(next_input, next_path, full_path)

#-------------------------------------------------------------------------------------- MagicAction import

class MagicAction():
    def __init__(self, name:str, version:str, description:str, action_config:dict, action_meta:dict, action_video:str, action_gif:str, icon_dark:str, icon_light:str):
        self.name : str = name
        self.version = version
        self.description : str = description
        self.config : dict = action_config
        self.meta : dict = action_meta
        self.video_path : str = action_video
        self.gif_path :str = action_gif
        self.icon_dark_path : str = icon_dark
        self.icon_light_path : str = icon_light
        self.file_format : str = "" # by default, actions are not fileformat specific
        self.ui_prio_hints : dict = action_meta.get("ui_prio_hints", {})
        print(f"Created Magic Action: {name}")

def import_magic_actions(root_folder) -> Dict[str, Dict[str, List[MagicAction]]]:
    magic_actions : List[MagicAction] = {}

    # TODO: export is commented out for now
    variants = ["import", "processing", "export"]

    magic_actions_folder = os.path.join(root_folder, 'magic-actions', 'actions')
    for version in os.listdir(magic_actions_folder):
        magic_actions[version] = {}
        version_folder = os.path.join(magic_actions_folder, version)

        for variant in variants:
            variant_folder = os.path.join(version_folder, variant)
            magic_actions[version][variant] = []

            if not os.path.isdir(variant_folder):
                continue

            for magic_action in os.listdir(variant_folder):
                action_folder = os.path.join(variant_folder, magic_action)
                if not os.path.isdir(action_folder):
                    continue

                # path definition
                meta_path = os.path.join(action_folder, "meta.json")
                config_path = os.path.join(action_folder, "rpd_config.json")
                video_path = os.path.join(action_folder, "video.mp4")
                gif_path = os.path.join(action_folder, "video.gif")
                icon_dark_path = os.path.join(action_folder, "icon-dark.svg")
                icon_light_path = os.path.join(action_folder, "icon-light.svg")

                if not os.path.isfile(meta_path):
                    print(f"ERROR: Unable to create the {version} {variant} action from the folder {magic_action}.")
                    print("The meta.json file doesn't exist or can't be found. Skipping.")
                    continue
                elif not os.path.isfile(config_path):
                    print(f"ERROR: Unable to create the {version} {variant} action from the folder {magic_action}.")
                    print("The rpd_config.json file doesn't exist or can't be found. Skipping.")
                    continue

                # meta and config
                try:
                    action_meta = loadJSON(meta_path)
                except json.JSONDecodeError:
                    print(f"ERROR: Unable to create the {version} {variant} action from the folder {magic_action}.")
                    print("The meta.json file is invalid or could not be opened. Skipping.")
                    continue
                try:
                    action_config = loadJSON(config_path)
                except json.JSONDecodeError:
                    print(f"ERROR: Unable to create the {version} {variant} action from the folder {magic_action}.")
                    print("The rpd_config.json file is invalid or could not be opened. Skipping.")
                    continue

                name = action_meta.get("name", action_meta.get("title", ""))
                description = action_meta.get("description", action_meta.get("explanation", ""))

                action = MagicAction(name, version, description, action_config, action_meta, video_path, gif_path, icon_dark_path, icon_light_path)
                # for export actions, the action folder is the format
                if variant == "export":
                    action.file_format = magic_action
                magic_actions[version][variant].append(action)

    return magic_actions

#-------------------------------------------------------------------------------------- command utilities

def getCommandSignature(rpde_path:str, cmd_args:List[str]) -> str:
    cmd_str = ''.join([rpde_path] + cmd_args)
    cmd_str_enc = str.encode(cmd_str)
    hash_object = hashlib.sha1(cmd_str_enc)
    signature = base64.b64encode(hash_object.digest()).decode()
    return signature

def getDefaultConversionConfig(fileName:str, fileType:str):
    config = {
        "export": [
            {
                "fileName": fileName,
                "format": {}
            }
        ]
    }

    if fileType == "fbx":
        config["export"][0]["format"]["fbx"] = {
            "3dsMaxPhysicalMaterial": {
                "textureFormat": {
                    "default": "png"
                }
            }
        }
    elif fileType in ["gltf", "glb"]:
        config["export"][0]["format"][fileType] = {
            "pbrMaterial": {
                "textureFormat": {
                    "default": "png"
                }
            }
        }
    elif fileType in ["usd", "usdz", "usda", "usdc"]:
        config["export"][0]["format"][fileType] = {
            "usdPreviewSurface": {
                "textureFormat": {
                    "default": "png"
                }
            }
        }

    return config

def overrideExports(config, file_format, name_override:str = ""):
    if name_override:
        file_name = name_override
    else:
        file_name = "scene_file"

    if "export" in config:
        config.pop("export")
    config["export"] = getDefaultConversionConfig(file_name, file_format)["export"]

