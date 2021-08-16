# Importer/Exporter for Animation FCurve Data as JSON in Blender

## How to use

After installing the add on, right clicking on the graph editor will bring up the tooling at the top of the context menu.

This was built using Blender 2.93.2 and the add-on is set to run on (2, 93, 0) and up.

## Considerations

- I kept these operators in the graph editor context menu because they feel very contextually dependent. A follow up task would be figuring out a good panel layout for these options but the amount of customizable settings available didn't warrant a full panel for what it is now.
- You can either replace an entire action, replace/add the imported curves, or merge/add the imported curves. The final option amounts to adding the imported keyframes onto existing fcurves. A use case would be if you were importing keyframes from the last half of a frame range and wanted to import those animations onto existent curves from the first half of the frame range.
- These options are context dependent. The graph editor context menu will show only the "Import Action from JSON" option if no animation data exists yet since there's nothing to export and nothing to replace or merge with. Otherwise all options are shown.
- I left a small artifact argument `FCurveImporterMixin.insert_keyframes(...,filter=None,...)` in to filter fcurves out of the merge/replace process. It's unused right now but in a follow up task could be used to filter out unselected curves, etc. Didn't seem like a priority given the context of this task.
- I chose to force keyframe storage rather than have separate logic for baked curves. For one, evaluating the sampled points at each frame is basically the same thing as converting to keyframes. For two, the number of curves is almost always low enough that converting to keyframes and back for each curve is not a huge efficiency concern, considering it's only done during the export process. 
- I didn't expose the `keyframe_points.insertion` options as properties because I tested out `REPLACE` property and it didn't work as expected on my machine. This means the `FAST` property is not exposed. Although adding that property to the file browser window would be trivial.
