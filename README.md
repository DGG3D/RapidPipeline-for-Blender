![RapidPipeline](resources/images/logo_black.svg#gh-light-mode-only)
![RapidPipeline](resources/images/logo_white.svg#gh-dark-mode-only)

# RapidPipeline 3D Processor for Blender

Introduction
---------------------------------------

The RapidPipeline Plugin for Blender:
* Enables you to use the RapidPipeline 3D Processor right from the Blender UI
* Process, optimize & simplify 3D models 100% locally
* Leverage RapidPipeline Presets to customize and share them with your team

The RapidPipeline 3D Processor is a tool to effectively convert, optimize and prepare 3D content.
The RapidPipeline Plugin for Blender allows the user to leverage this powerful tool directly in Blender with a native user interface.

Major Functionalities include:
* Mesh decimation
* Draw call reduction (scene graph optimization, material merging)
* Remeshing 
* Texture baking
* UV unwrapping
and more.

You can find the full documentation for the 3D Processor [here](https://docs.rapidpipeline.com/docs/componentDocs/3dProcessor/3d-processor-overview)

To access the functionalities of the 3D Processor the RapidPipeline Plugin for Blender uses a RapidPipeline 3D Processor Engine ("rpde").


This executable needs to be provided in addition to the code in this repository.
You can download the Engine executable [at our RapidPipeline portal](https://app.rapidpipeline.com/plugins) after creating an account using eighter the trial version or a "Team License" or higher.
After unpacking the downloaded files there will be a folder called "rpde" that needs to be in the same directory as the code for the Plugin.

The 3D Processor Engine is necessary to use the capabilities of the RapidPipeline Plugin for Blender.


The Engine is an executable that is called from within the Plugin using the selected values in the UI ("settings").

To repeat the same actions across multiple .blend files it is also possible to save and load those settings in a JSON format.

To learn more about the Plugin and its usage please refer to our [Documentation page](https://docs.rapidpipeline.com/docs/componentDocs/BlenderPlugin/blender-plugin-overview) as well as our [Tutorial Page](https://docs.rapidpipeline.com/docs/3dProcessor-Tutorials/blender-plugin-tutorials)



⚠️ System Requirements
---------------------------------------

* Windows 10/11 64bits / MacOS
* Blender versions 3.5 to 4.4 64bits
    * Recommended: Blender v4.4
* The RapidPipeline 3D Processor Engine ("rpde") executable:
    * You can download the Engine executable [at our RapidPipeline portal](https://app.rapidpipeline.com/plugins).
    * Please see the license notes below, under Licensing, or in the file [COPYING.md](./COPYING.md) for considerations regarding the rpde executable EULA.
* A compatible version of the RapidPipeline Settings Schema:
    * The most recent compatible JSON schema is included here, in [resources/schema.json](resources/schema.json).


🏡 Installation Instructions
---------------------------------------

Installation instructions for the RapidPipeline Plugin for Blender can be found at the
[RapidPipeline Documentation Portal](https://docs.rapidpipeline.com/docs/componentDocs/BlenderPlugin/blender-plugin-setup).


📝 User Documentation
---------------------------------------

Documentation for the RapidPipeline Plugin for Blender can be found at the
[RapidPipeline Documentation Portal](https://docs.rapidpipeline.com/docs/componentDocs/BlenderPlugin/blender-plugin-overview).


⚖️ Licensing
---------------------------------------

RapidPipeline, the RapidPipeline 3D Processor, the RapidPipeline 3D Processor
Plugin for Blender and their logos are 2024 (c) Copyright Darmstadt Graphics Group GmbH.

The RapidPipeline 3D Processor Plugin for Blender uses the GNU General Public
License, version 3 or later, which describes the rights to distribute or change
the code of the Python and GUI application here included.

Please read this file for the full license of the GUI plugin:
[licenses/processorpluginblender.txt](./licenses/processorpluginblender.txt)

**Note that the RapidPipeline 3D Processor Engine CLI ("rpde") is a copyrighted
software governed by its own EULA. The RapidPipeline 3D Processor Engine CLI
does NOT make use of the 3D Processor Plugin For Blender and does NOT follow
the GNU GPL-3.0 license. See the RapidPipeline 3D Processor EULA file (under
```rpde/EULA_RapidPipelineEngine.rtf``` after installation, or during the installation
process itself) for further information.**


🐛 Known Issues & Limitations
---------------------------------------

The list of currently known issues and/or limitations are as follows:
* Modifiers will be ignored during export:
    * Modifiers need to be manually applied before using the plugin.
* Currently, some materials are not supported:
    * Supported are Principled BSDF node, image Textures, color Attributes…
	* All procedural materials are unsupported.
* If an old version of the Plugin was previously installed, the Blender application needs to be restarted on installing the new version
* The Plugin currently only works on meshes in "Object Mode"


How configuring RapidPipeline Engine works
---------------------------------------

The rpde process is started in the run_rpde.py file using the "runPipeline" function. 
As input file (-i) rpde uses the selected meshes exported from blender through the function "exportModel".
Rpde then processes this model locally based on the settings (--read_config) selected in the UI and saves the processed model at the specified output folder. (-o)
This model then needs to be imported into Blender using the function "importModel"
For further information on the structure of the settings file please see our [Documentation on RapidPipeline settings](https://docs.rapidpipeline.com/docs/componentDocs/3dProcessingSchemaSettings/processor-schema-settings-v1.1)


☎️ Contact & reporting problems
---------------------------------------

To get in touch or report a bug, you may contact us at [info@dgg3d.com](info@dgg3d.com).

