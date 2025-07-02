## Clean up CAD Mesh

### Status

QA/Design Review.

### Usage

1. Web platform: Reimports the CAD file as well as cleans it all up.
2. Substance Painter: This should be the main CAD importer for Substance Painter plugin.
3. Rest of the DCC Plugins: Do not use this. Instead use regular CAD Import action as is. If the user wants to clean up/repair, then they use Model Clean Up magic action.

### Note
1. The export section is TBD.