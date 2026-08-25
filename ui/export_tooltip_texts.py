EXPORT_MODE_HELP = """
<b>Export Mode</b><br><br>

Choose how the selected annotations are organized into datasets.<br><br>

<b>Separate</b><br>
Creates a separate dataset folder for each selected layer.
For example, selecting Players and Actions creates:
<pre>
    players/
        images/
        labels/
        data.yaml
    
    actions/
        images/
        labels/
        data.yaml
</pre>

Each dataset contains only the selected labels belonging to
that layer.<br><br>

<b>Combined</b><br>
Creates one dataset containing annotations from all selected
layers. Labels from the selected layers are combined into one
class list.

<pre>
    dataset/
        images/
        labels/
        data.yaml
</pre>  
"""

ANNOTATION_FORMAT_HELP = """
<b>Annotation Format</b><br><br>

Choose the geometry format used by the exported YOLO dataset.<br><br>

<b>Bounding Box (object detection format)</b><br>
All annotations are exported as YOLO bounding boxes.
Polygon annotations are converted to the smallest bounding
rectangle that contains the entire polygon.<br><br>

<b>Segmentation (object segmentation format) </b><br>
All annotations are exported as YOLO segmentation polygons.
Bounding-box annotations are converted into four-point
rectangles.

<pre>
DB annotation       Requested format       Output
------------------------------------------------------
polygon              bbox                  bounding box
rectangle            bbox                  bounding box

polygon              segmentation         polygon
rectangle            segmentation         4-point polygon
</pre>
"""

LAYERS_HELP = """
<b>Layers</b><br><br>

Select which annotation layers (and subset of their labels) should be included in the
exported dataset. This part is used for yolo .yaml file generation with labels.<br><br>

Only annotations belonging to the selected layers will be exported.
"""

LABELS_HELP = """
<b>Labels</b><br><br>

Select the individual labels that should be included in the
exported dataset.<br><br>

Only annotations whose layer and label are both selected will
be exported.<br><br>

The selected labels become the classes in the YOLO
dataset.

For example:
<pre>
    Players
        ☑ player
        ☑ libero
    
    Actions
        ☑ spike
        ☑ block
        ☐ set
        ☐ receive
        
results in:
</> YAML
names:
  0: player
  1: libero
  2: spike
  3: block

</pre>
"""

VIDEOS_HELP = """
<b>Media / Videos</b><br><br>

Select which videos should be included in the exported
dataset.<br><br>

Only annotated frames from the selected videos are exported.
Frames that contain no selected annotations are ignored.
"""

AUGMENTATION_HELP = """
<b>Augmentation</b><br><br>

Augmentations are used to increase the size of the exported
dataset.<br><br>

The selected augmentations are always applied. Each selected
augmentation creates one additional version of every original
image.<br><br>

For example, with 100 original images:<br>
• No augmentation → 100 images<br>
• Brightness & Contrast → 200 images<br>
• Brightness & Contrast + Color Jitter → 300 images<br>
• All three augmentations → 400 images<br><br>

The original images are always preserved.
"""

VALIDATION_HELP = """
<b>Validation Set</b><br><br>

Choose what percentage of the exported images should be placed
in the validation set.<br><br>

0% means that no validation set is created.<br><br>

For example, with 100 exported images and a validation ratio
of 20%:<br>
• Training: 80 images<br>
• Validation: 20 images

"""















