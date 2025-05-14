# RapidPipeline for Blender

## Changelog

### Version v0.2.1 April 24, 2025
* CAD files imported are now moved to the correct collection
* Changed position of Buttons in UI
* Updated UI for entering rpde token
* Updated Labels and tooltips on buttons
* Change to arguments on rpde call

### Version v0.2.1_1 April 30, 2025
* fixed issue of cad import deleting selection
* fixed issue of multiple runs not in the right collection

### Version v0.2.0 March 25, 2025
* Use Blender native UI instead of pyside
* Support of Mac OS 
* Complete overhall of UI scripts to adjust to Blender internal API bpy
* Removed Standalone version and pyside scripts
* Added an option to import CAD models

* Fixed naming and placemet of nodes in their collections after running
* Fixed a bug with adding a temporary token
* Added Tooltips to UI elements
* Most Input fields are now limited to a min and max value

* Tab can be enabled and disabled
* Cancle and retry button on execution
* Improved Settings export
* Minimum and Maximum limits to input fields
* general Improvements to UI


### Version v0.1.3 November 11, 2024
* Export / Import format changed to glb instead of gltf
* Output directory does not have to be defined by the user anymore
* Fixed bugs with uninstall process

### Version v0.1.2 November 07, 2024
* Updates to the schema
* Check if Blender is open during plugin installation
* Force file removal during uninstall

### Version v0.1.1 October 22, 2024

* User-defined output directory for GLTF export
* Help link now directs straight to the plugin page
* Plugin window remains in the foreground only when Blender is focused
* Improved handling of child-parent connections
* Hides collection node if all nodes within are hidden
* Verifies existence of Blender executable during installation


### Version v0.1.0 August 15th, 2024

* Enables you to use the RapidPipeline 3D Processor right from the Blender UI
* Process, optimize & simplify 3D models 100% locally
* Allows creating, saving, and loading of presets based on 3D Processor v7.x schema
