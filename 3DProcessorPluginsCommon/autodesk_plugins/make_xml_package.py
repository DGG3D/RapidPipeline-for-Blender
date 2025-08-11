import os
import shutil
import uuid
import xml.etree.cElementTree as ET
from argparse import ArgumentParser
from pathlib import Path
import zipfile

"""
3ds Max Example:
<?xml version="1.0" encoding="utf-8"?>
<ApplicationPackage
    SchemaVersion="1.0"
    AutodeskProduct="3ds Max"
    ProductType="Application"
    Name="My 3ds Max Plugin"
    AppVersion="1.0.0"
    ProductCode="{caedfa12-cf58-4188-a22b-e4cf2e52baa2}"
    UpgradeCode="{68b04f36-d00b-436e-9386-7337afcffa4a}"
>
    <CompanyDetails Name="Autodesk Productions" Url="http://www.autodesk.com" />
    <Components Description="pre-start-up scripts parts">
        <RuntimeRequirements OS="Win64" Platform="3ds Max" SeriesMin="2025" SeriesMax="2025" />
        <ComponentEntry AppName="DemoMenu" Version="1.0.0" ModuleName="./pre_startup_scripts/menu_demo.ms" />
    </Components>
    <Components Description="light icon paths parts">
        <RuntimeRequirements OS="Win64" Platform="3ds Max" SeriesMin="2025" SeriesMax="2025" />
        <ComponentEntry AppName="lighticons" Version="1.0.0" ModuleName="./icons/Light" />
    </Components>
    <Components Description="dark icon paths parts">
        <RuntimeRequirements OS="Win64" Platform="3ds Max" SeriesMin="2025" SeriesMax="2025" />
        <ComponentEntry AppName="darkicons" Version="1.0.0" ModuleName="./icons/Dark" />
    </Components>
</ApplicationPackage>

Maya Example:
<?xml version="1.0" encoding="utf-8"?>
<ApplicationPackage SchemaVersion="1.0"
	ProductType="Application"

	AutodeskProduct="Maya"
	Name="MathNode"
	Description="Autodesk Maya MathNode"
	AppVersion="1.0.0"
	Author="Autodesk"
	AppNameSpace="com.autodesk.exchange.maya.mathnode"
	HelpFile="./Contents/docs/index.html"
	OnlineDocumentation="http://www.autodesk.com/maya"

	ProductCode="*"
	UpgradeCode="{52c87085-07d5-4cfa-b76e-e348553c30ac}" >

	<CompanyDetails Name="Autodesk"
		Phone=" "
		Url="http://www.autodesk.com"
		Email="labs.plugins@autodesk.com" />

	<!-- Prevent to load in other version than Maya 2008 -->
	<RuntimeRequirements SupportPath="./Contents/docs" OS="win64|macOS|linux" Platform="Maya" SeriesMin="2008"  />

	<Components>
		<RuntimeRequirements SupportPath="./Contents/docs" OS="win64|macOS|linux" Platform="Maya" SeriesMin="2008" />
		<MayaEnv expr="MAYA_SCRIPT_PATH+:=shelves" />
		<ComponentEntry ModuleName="./Contents/plug-ins/asdkMathNode.py" AutoLoad="True" />
		<ComponentEntry ModuleName="./Contents/scripts/AEasdkMathNodeTemplate.mel" />
		<ComponentEntry ModuleName="./Contents/scripts/MathNode_load.mel" />
		<ComponentEntry ModuleName="./Contents/icons/MathNode.png" />
		<ComponentEntry ModuleName="./Contents/shelves/MathNode_shelf.mel" />
	</Components>

</ApplicationPackage>
"""

"""
- UpgradeCode should be always the same for a given plugin.
- ProductCode should be unique/refreshed every version.
- Read more: https://help.autodesk.com/view/MAXDEV/2026/ENU/?guid=packagexml_format#:~:text=UpgradeCode%20(required)
"""
product_names = { # mapping between CLI arg name and internal names accepted by Autodesk format
    "max": "3ds Max",
    "maya": "Maya",
}
upgrade_codes = { # these never should change across versions!!!
    "3ds Max": "{749678e3-36be-5374-a82c-7633d48fb24d}",
    "Maya": "{8bc38fdd-0030-5fbe-ad11-dc100d7ddfdf}",
}
main_script_name = {
    "3ds Max": "RapidPipelineForMax.py",
    "Maya": "RapidPipelineForMaya.py",
}
package_name = {
    "3ds Max": "RapidPipelineForMax",
    "Maya": "RapidPipelineForMaya",
}
def add_RuntimeRequirements(parent:ET.Element, os:str, platform:str, series_min:str, series_max:str) -> ET.Element:
    ET.SubElement(parent, "RuntimeRequirements", OS=os, Platform=platform, SeriesMin=series_min, SeriesMax=series_max)

def add_Icons(parent:ET.Element, os:str, platform:str, series_min:str, series_max:str, version:str) -> ET.Element:
    light_icons = ET.SubElement(parent, "Components", Description="light icon paths parts")
    add_RuntimeRequirements(light_icons, os, platform, series_min, series_max)
    ET.SubElement(light_icons, "ComponentEntry", AppName="lighticons", Version=version, ModuleName="./rpd_plugins_common/assets/icons")

    dark_icons = ET.SubElement(parent, "Components", Description="dark icon paths parts")
    add_RuntimeRequirements(dark_icons, os, platform, series_min, series_max)
    ET.SubElement(dark_icons, "ComponentEntry", AppName="darkicons", Version=version, ModuleName="./rpd_plugins_common/assets/icons")

def add_mainScript(parent:ET.Element, os:str, platform:str, series_min:str, series_max:str) -> ET.Element:
    components = ET.SubElement(parent, "Components")
    if platform == "3ds Max":
        # post-start-up is 3ds Max specific
        components.attrib["Description"] = "post-start-up scripts parts"
    add_RuntimeRequirements(components, os, platform, series_min, series_max)

    component_entry = ET.SubElement(components, "ComponentEntry", ModuleName=f"./{main_script_name[platform]}")
    if platform == "Maya":
        # AutoLoad and AutoLoadOnce are Maya specific
        component_entry.attrib["AutoLoadOnce"] = "True"

def make_XML_package(product: str, version: str, output_folder:str):
    # product code should be unique per version, so we hash it based on the upgrade code,
    # which is always the same for a given plugin, and a string that includes the version
    product_str = f"RapidPipeline for {product}"
    upgrade_uuid = uuid.UUID(upgrade_codes[product])
    product_uuid = uuid.uuid5(upgrade_uuid, f"{product_str} {version}")
    product_code = "{" + str(product_uuid) + "}"

    package = ET.Element(
        "ApplicationPackage",
        SchemaVersion="1.0",
        AutodeskProduct=product,  # e.g. '3ds Max' or 'Maya'
        ProductType="Application",
        Name=product_str,
        # Description=f"{product} Plug-in for the RapidPipeline 3D Processor.",
        AppVersion=version,  # plugin version in 'major.minor.patch' format, e.g. '1.0.0'
        UpgradeCode=upgrade_codes[product],
        ProductCode=product_code,
    )
    ET.SubElement(
        package,
        "CompanyDetails",
        Name="Darmstadt Graphics Group GmbH",
        Url="https://www.rapidpipeline.com",
    )

    add_RuntimeRequirements(package, "Win64", product, "2025", "2026")
    add_mainScript(package, "Win64", product, "2025", "2026")
    add_Icons(package, "Win64", product, "2025", "2026", version)

    # ident and write out package
    ET.indent(package)
    tree = ET.ElementTree(package)

    # create folder and save xml file
    os.makedirs(output_folder, exist_ok=True)
    tree.write(os.path.join(output_folder, "PackageContents.xml"), encoding="utf-8", xml_declaration=True)

def copy_input_files(input_folder:str, rpde_folder:str, schema_file:str, output_folder:str, version:str):
    to_ignore = ["__pycache__", ".git", ".github", ".venv", "input", "output", ".gitignore",
                 ".gitmodules", "temp_config.json", "temp_system.json", "rpd_temp_files", "settings_file.json", "action_cache.json", "__version__.py"]
    if rpde_folder:
        to_ignore.append("rpde")
    if schema_file:
        to_ignore.append("schema.json")
    
    shutil.copytree(input_folder, output_folder, ignore=shutil.ignore_patterns(*to_ignore), dirs_exist_ok=True)
    if schema_file:
        shutil.copy(schema_file, output_folder)
    
    # create __version__ file
    versionContent = '__version__ = "' + version + '"'
    with open(os.path.join(output_folder, "__version__.py"), "w") as f:
        f.write(versionContent)

def copy_rpde_files(rpde_folder:str, output_folder:str):
    if not rpde_folder:
        return
    
    output_folder_rpde = str(Path(output_folder) / Path("rpde"))
    shutil.copytree(rpde_folder, output_folder_rpde, dirs_exist_ok=True)

def package_folder(input_folder:str, archive_path:str):
    package_folder = Path(input_folder)
    hoops_dir = package_folder / os.path.join("rpde", "hoops")
    hoops_build = os.path.isdir(hoops_dir)
    if hoops_build:
        outPath = Path(archive_path)
        new_stem = outPath.stem + "_CAD"
        archive_path = str(outPath.with_stem(new_stem))

    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive_file:
        for file_path in package_folder.rglob("*"):
            if file_path.is_file():
                archive_file.write(file_path, os.path.relpath(file_path, package_folder))

    # test if file is OK
    with zipfile.ZipFile(archive_path, "r") as archive_file:
        bad_file = zipfile.ZipFile.testzip(archive_file)
        if bad_file:
            raise zipfile.BadZipFile(f"CRC check failed for {archive_path} with file {bad_file}.")

if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("-p", "--product", choices=("max", "maya"), type=str.lower, required=True, help="Product being packaged. Possible options: %(choices)s.")
    parser.add_argument("-i", "--input", type=str, help="Root input folder for packaging.")
    parser.add_argument("-r", "--rpde", type=str, help="Root input folder for rpde packaging.")
    parser.add_argument("-s", "--schema", type=str, help="Schema file for rpde packaging.")
    parser.add_argument("-o", "--output", type=str, help="Root output folder for packaging.")
    parser.add_argument("-v", "--version", type=str, required=True, help="Version of the plugin. Format: X.Y.Z, e.g.: 1.0.1")
    args = parser.parse_args()

    # validate version string
    if not all([c.isdigit() or c == "." for c in str(args.version)]) or str(args.version).count(".") != 2:
        error_str = "The version string parameter is incorrect.\n"
        error_str += "Format Required: 'X.Y.Z' where X, Y and Z are numbers.\n"
        error_str += f"String Provided: {args.version}"
        raise ValueError(error_str)

    product = product_names[args.product]

    copy_input_files(args.input, args.rpde, args.schema, args.output, args.version)
    copy_rpde_files(args.rpde, args.output)

    make_XML_package(product, args.version, args.output)

    package_folder(args.output, os.path.join(os.path.dirname(args.output), f"{package_name[product]}_v{args.version}.zip"))