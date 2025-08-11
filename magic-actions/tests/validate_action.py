import os
import json
from pathlib import Path
from typing import List, Union, Any
from argparse import ArgumentParser
import traceback

from jsonschema import validate, ValidationError
from prettytable import PrettyTable
# from spellchecker import SpellChecker


################################################
############ jSon and Schema Utils #############
################################################

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
                raise ValueError(f"Unable to find setting with leaf oneOf path {path}")
            return next_input["properties"][next_setting], next_setting

    # here we still have more parts to the path, recurse
    next_setting, next_path = result[0], result[1]

    if not input_type:
        raise ValueError(f"Unable to find setting with remaining path {path}")
    if input_type == "object" and "oneOf" not in input_dict:
        return getSchemaPropertyFromPath(input_dict["properties"][next_setting], next_path)
    elif input_type == "object" and "oneOf" in input_dict:
        next_input = next((i for i in input_dict["oneOf"] if next_setting in i.get("properties", {})), {})
        if not next_input:
            raise ValueError(f"Unable to find setting with remaining oneOf path {path}")
        return getSchemaPropertyFromPath(next_input["properties"][next_setting], next_path)
    elif input_type == "array":
        next_input = input_dict.get("items", {}).get("properties", {})
        if not next_input or next_setting not in next_input:
            raise ValueError(f"Unable to find setting with remaining array path {path}")
        return getSchemaPropertyFromPath(next_input[next_setting], next_path)
    raise ValueError(f"Setting of type {input_type} is currently unsupported.")

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

################################################
################# Action Utils #################
################################################

# def has_spelling_errors(text) -> Tuple[bool, set]:
#     """
#     Check if a string has spelling errors. True if spelling errors found, False otherwise
#     """
#     spell = SpellChecker()

#     # Extract words (only alphabetic characters)
#     words = re.findall(r'\b[a-zA-Z]+\b', text.lower())

#     # Check for misspelled words
#     misspelled = spell.unknown(words)
#     if misspelled:
#         return True, misspelled
#     return False, misspelled

def collect_action_files(folder_path:str) -> dict:
    """
    Collect Magic Action files.
    """

    actions = {}

    # Look for version directories (v0.1, v0.2, etc.)
    version_dirs = list(Path(folder_path).glob('v*/'))

    if not version_dirs:
        print("No version directories found (looking for v*/)")
        return []

    print(f"Found version directories: {version_dirs}")

    for version_dir in version_dirs:
        version = version_dir.name
        print(f"Processing version: {version}")
        actions[version] = {}

        # Find all subdirectories in this version
        variants = list(version_dir.glob("*"))

        if not variants:
            print(f"No subdirectories found in {version_dir}")
            continue

        print(f"Found subdirectories: {[d.name for d in variants]}")

        # Find all subdirectories in this variant
        for variant_dir in variants:
            variant = variant_dir.name
            print(f"Processing Variant: {variant}")
            actions[version][variant] = []

            # Find all subdirectories in this variant
            subdirs = list(variant_dir.glob("*"))

            if not subdirs:
                print(f"No subdirectories found in {variant_dir}")
                continue

            print(f"Found subdirectories: {[d.name for d in subdirs]}")
            for subdir in subdirs:
                subdir_name = subdir.name

                # Find all JSON files in this subdirectory
                meta_path = Path(subdir, "meta.json")
                config_path = Path(subdir, "rpd_config.json")
                if not meta_path.is_file() or not config_path.is_file():
                    print(f"Required JSON files not found in {subdir}")
                    continue

                print(f"Found JSON files: {[str(meta_path), str(config_path)]}")

                # load metadata to include some info in the action dict
                meta_json = loadJSON(meta_path)

                actions[version][variant].append({
                    'version': version,
                    'variant': variant,
                    'subfolder': subdir_name,
                    'action_name': meta_json.get("name", subdir_name),
                    'meta': str(meta_path),
                    'config': str(config_path)
                })

    return actions

def validate_action(action, schema, variant):
    """
    Validate a given magic action against the solved schema.
    """
    # validate meta
    meta_json = loadJSON(action["meta"])

    # TODO: what other fields should be obligatory?
    obligatory_fields = {
        "name":"string",
        "button_name":"string",
    }
    for field in obligatory_fields:
        if field not in meta_json:
            return False, f"Action Metadata is missing obligatory field '{field}' of type {obligatory_fields[field]}."

    # action_description = meta_json.get("explanation", "")
    # if action_description:
    #     flag, spelling_errors = has_spelling_errors(action_description)
    #     if flag:
    #         return False, f"The Action's explanation has one or more spelling errors in the following words: {spelling_errors}"

    # action_description = meta_json.get("explanation_long", "")
    # if action_description:
    #     flag, spelling_errors = has_spelling_errors(action_description)
    #     if flag:
    #         return False, f"The Action's long explanation has one or more spelling errors in the following words: {spelling_errors}"

    # verify all exposed actions
    exposed_settings = meta_json.get("exposed_options", None)
    for setting in list(exposed_settings):
        if not isinstance(setting, dict):
            return False, f"Action has invalid type {type(setting)} in field 'exposed_options', expected dict."

        # if we don't have a setting, it's invalid
        # all options need to have valid paths
        setting_path = setting.get("path", None)
        if not setting_path:
            return False, "Action has setting missing obligatory field 'path' of type string."

        # check if path is valid
        # the path is valid if we can find it on the schema
        try:
            getSchemaPropertyFromPath(schema, setting_path)
        except Exception:
            traceback.print_exc()
            return False, f"Unable to get setting from schema path: {setting_path}"

    # validate config
    config_json = loadJSON(action["config"])
    # the export section may not be provided here - we override it
    if variant != "export":
        overrideExports(config_json, "gltf", "scene_file")
    try:
        validate(instance=config_json, schema=schema)
    except ValidationError:
        traceback.print_exc()
        return False, f"The preset config file is invalid against the schema: {action}"

    return True, "The action has been validated against the schema."

################################################
################# Main Program #################
################################################

def main(actions_folder:str, schema_path:str):
    print("=== Validating Magic Actions ===\n")

    if not os.path.isfile(schema_path):
        raise FileNotFoundError(f"The schema file could not be found at: {schema_path}")

    # load and solve schema
    schema = loadJSON(schema_path)
    schema_defs = getSchemaDefs(schema)
    schema, _ = solveSchemaRefs(schema, schema_defs)

    # collect files for all actions
    actions_per_version = collect_action_files(actions_folder)

    if not actions_per_version:
        print("ERROR: No JSON files found to validate")
        return

    # counts all actions
    total_actions = 0
    for version in actions_per_version:
        total_actions += sum(len(actions_per_version[version][v]) for v in actions_per_version[version])

    print("\n=== Collected Actions ===")
    print(f"Total Actions: {total_actions}")
    print(json.dumps(actions_per_version, indent=2))

    total_valid_count = 0
    for version in actions_per_version:
        print(f"\n=== Action Preview - Version {version} ===")
        valid_count = 0
        total_version_count = 0
        for variant in actions_per_version[version]:
            total_version_count += len(actions_per_version[version][variant])
            for action in actions_per_version[version][variant]:
                print(f"\n {variant} Action {action['version']} - {action['action_name']}")
                print(f"  Variant: {action['variant']}")
                print(f"  Version: {action['version']}")
                print(f"  Subfolder: {action['subfolder']}")
                print(f"  Meta JSon: {action['meta']}")
                print(f"  Config JSon: {action['config']}")

                # Test validation
                action['is_valid'], message = validate_action(action, schema, variant)
                if action['is_valid']:
                    valid_count += 1
                    status = "VALID"
                else:
                    status = "INVALID"
                action['valid_status'] = status
                action['valid_message'] = message
                print(f"  Status: {status} - {message}")

        print(f"\n=== Summary for version {version} ===")
        print(f"Valid Actions: {valid_count}/{total_version_count}")
        total_valid_count += valid_count

    # print summary table
    table = PrettyTable()
    table.title = "Summary for All Versions"
    table.field_names = ['Version', 'Variant', 'Action Name', 'Action Folder', 'Status']
    for j, version in enumerate(actions_per_version):
        for i, variant in enumerate(actions_per_version[version]):
            for k, action in enumerate(actions_per_version[version][variant]):
                use_divider = (k + 1) == len(actions_per_version[version][variant]) # only for last one
                table.add_row([version, variant, action['action_name'], action['subfolder'], action['valid_status']], divider=use_divider)

    # add footer
    footer_msg = "All Magic Actions are valid!" if total_valid_count == total_actions else "Some Magic Actions have issues."
    table.add_row(["", "", f"Valid Actions: {total_valid_count}/{total_actions}", footer_msg, ""])

    print(f"\n\n{table}\n")

    if total_valid_count == total_actions:
        exit(0)
    else:
        exit(1)

if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument('-a', '--actions', required=True, help="Root folder for magic actions. Version folders should be children of this folder.")
    parser.add_argument('-s', '--schema', required=True, help="Path to Schema file.")
    args = parser.parse_args()
    main(args.actions, args.schema)