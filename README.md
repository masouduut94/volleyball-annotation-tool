# Volleyball Annotation Tool

A Qt-based annotation platform designed specifically for volleyball video and image annotation.

The application provides a desktop interface for manually annotating volleyball footage, organizing annotations by jobs and labels, navigating video frame-by-frame, and using AI models to accelerate annotation.

Repository: https://github.com/masouduut94/volleyball-annotation-tool

---

## Table of Contents

- [Overview](#overview)
- [Main Features](#main-features)
- [Project Architecture](#project-architecture)
- [Repository Structure](#repository-structure)
- [Application Entry Point](#application-entry-point)
- [Main Window](#main-window)
- [Graphics Scene and View](#graphics-scene-and-view)
- [Annotation System](#annotation-system)
- [Jobs and Labels](#jobs-and-labels)
- [Video and Frame Navigation](#video-and-frame-navigation)
- [Database](#database)
- [AI Annotation](#ai-annotation)
- [Configuration](#configuration)
- [Export](#export)
- [Keyboard Shortcuts](#keyboard-shortcuts)
- [Typical Workflow](#typical-workflow)
- [Coordinate Systems and Scaling](#coordinate-systems-and-scaling)
- [Adding New Features](#adding-new-features)
- [Development Notes](#development-notes)
- [License](#license)

---

## Overview

The Volleyball Annotation Tool is a desktop annotation application built with Python and Qt.

It is intended for computer-vision datasets related to volleyball, where different types of information may need to be annotated independently. Examples include:

- Volleyball court geometry
- Ball location or segmentation
- Player detection
- Player roles
- Volleyball actions
- Frame-level metadata
- Object bounding boxes
- Polygon/segmentation annotations

A central design principle of the application is that annotations belong to a **Job**. This makes it possible to annotate the same video multiple times for different purposes without mixing unrelated labels or annotations.

For example:

- A **Court** job can contain `Net`, `Attack Zone`, and `Back Zone`.
- A **Players** job can contain `Ordinary Player` and `Libero`.
- A **Ball** job can contain ball segmentation.
- An **Actions** job can contain `Block`, `Spike`, `Set`, and `Receive`.

---

# Main Features

## Image annotation

The application can display images and allows annotations to be created on top of them.

Supported annotation concepts include:

- Rectangles / bounding boxes
- Polygons
- Labels
- Per-frame annotations
- Different annotation jobs

## Video annotation

Videos can be opened and navigated frame-by-frame.

The application maintains:

- Current frame
- Total frame count
- Video capture
- Current annotations
- Frame navigation controls

This allows an annotator to inspect individual frames and create annotations precisely.

## Job-based annotation

Jobs separate different annotation tasks.

This is particularly important for volleyball because the same frame can contain:

- Court annotations
- Player annotations
- Ball annotations
- Action annotations

The UI should only display annotations belonging to the currently selected job.

## AI-assisted annotation

AI models can be configured and used to automatically generate annotations.

The intended AI tools include:

- Ball segmentation
- Court segmentation
- Player detection
- Action detection

AI-generated results can then be reviewed and corrected manually.

---

# Project Architecture

The application follows a relatively modular architecture:

```text
                    +----------------+
                    |    main.py     |
                    +-------+--------+
                            |
                            v
                    +----------------+
                    | MainWindow     |
                    | main_window.py |
                    +-------+--------+
                            |
             +--------------+--------------+
             |              |              |
             v              v              v
       Graphics UI      Configuration    Services
             |              |              |
             v              v              v
      GraphicsScene   Config Dialog    AI / Database
             |
             v
       Annotation Items
```

The main responsibilities are divided between:

- Application startup
- Main UI orchestration
- Graphics rendering
- Annotation interaction
- Database persistence
- Configuration
- AI services

`main_window.py` acts as the central coordinator. It connects the different UI components and services together.

---

# Repository Structure

The repository currently contains the following major components:

```text
volleyball-annotation-tool/
│
├── database/
│
├── resources/
│
├── services/
│
├── ui/
│
├── config_dialog.py
├── graphics_scene.py
├── graphics_view.py
├── main.py
├── main_window.py
├── __init__.py
├── LICENSE
└── .gitignore
```

The exact contents of the individual directories may evolve as the project grows.

## `database/`

Contains the persistence layer.

Its responsibility is to store and retrieve information such as:

- Jobs
- Labels
- Annotation data
- Configuration
- Frame-related information

The database keeps the UI from having to manage persistence directly.

## `resources/`

Contains application resources such as:

- Icons
- Images
- UI assets

Examples of resources used by the application include icons for AI tools, players, ball, actions, jobs, and settings.

## `services/`

Contains application/business logic that should not be tightly coupled to Qt widgets.

This is where functionality such as AI inference and other non-UI services can live.

## `ui/`

Contains reusable UI components and dialogs.

Keeping these components separate from `MainWindow` makes the application easier to maintain.

---

# Application Entry Point

## `main.py`

`main.py` is the application entry point.

Its main responsibility is to:

1. Create the Qt application.
2. Create the main window.
3. Show the main window.
4. Start the Qt event loop.

Conceptually:

```python
app = QApplication(...)
window = MainWindow(...)
window.show()
app.exec()
```

The entry point should remain lightweight.

Application-specific behavior belongs in `MainWindow` or the appropriate service/component rather than being implemented directly in `main.py`.

---

# Main Window

## `main_window.py`

`main_window.py` contains the central `MainWindow` class.

This is the most important integration point in the application.

It gathers together:

- Main toolbar
- Video/image display
- Frame navigation
- Annotation controls
- Job selection
- Label selection
- AI tools
- Configuration
- Saving/loading
- Export
- Keyboard shortcuts
- Database access
- Annotation state

The main window should primarily act as an **orchestrator**.

For example, when the user presses the "Next Frame" button, `MainWindow` coordinates:

```text
User action
    |
    v
MainWindow
    |
    +--> determine next frame
    |
    +--> load frame
    |
    +--> retrieve annotations
    |
    +--> update graphics scene
    |
    +--> update frame controls
```

This makes `MainWindow` the bridge between the UI and the underlying application logic.

---

# Graphics Scene and View

The annotation canvas is based on Qt's graphics framework.

Two important components are:

- `graphics_scene.py`
- `graphics_view.py`

## `graphics_scene.py`

The graphics scene manages objects drawn on top of the image.

Responsibilities can include:

- Displaying the current frame
- Creating annotation items
- Managing annotation graphics
- Handling mouse interaction
- Keeping track of temporary drawing states
- Updating annotation positions

The scene is where annotation objects ultimately live.

## `graphics_view.py`

The graphics view is responsible for displaying the graphics scene.

It can also handle interaction such as:

- Zooming
- Panning
- Mouse movement
- Image navigation gestures

The separation between scene and view follows Qt's graphics-view architecture.

---

# Annotation System

Annotations are represented as graphical objects placed over the displayed frame.

The basic flow is:

```text
Mouse input
     |
     v
GraphicsScene
     |
     v
Create annotation item
     |
     v
User modifies annotation
     |
     v
Annotation state
     |
     v
Save to database
```

## Rectangle annotations

Rectangles are appropriate for object detection tasks such as:

- Players
- Ball
- Other volleyball objects

A rectangle normally stores:

```text
x
y
width
height
label
job
frame
```

Very small accidental rectangles should not be treated as valid annotations.

## Polygon annotations

Polygons are appropriate for:

- Court regions
- Segmentation
- Irregular objects

A polygon consists of multiple points:

```text
P1 -> P2 -> P3 -> ... -> Pn
```

A valid polygon requires at least three points.

For court annotation, the project has also used a four-corner representation where the court geometry is represented by four important corner points.

---

# Jobs and Labels

Jobs are one of the most important concepts in the application.

A job represents a specific annotation task.

For example:

```text
Court
 ├── Net
 ├── Attack Zone
 └── Back Zone

Players
 ├── Ordinary Player
 └── Libero

Ball
 └── Ball

Actions
 ├── Block
 ├── Spike
 ├── Set
 └── Receive
```

## Why jobs are necessary

Suppose the same video is annotated for both court segmentation and player detection.

The court job may use polygons while the player job may use rectangles.

Showing all annotations simultaneously would make the interface confusing and could result in accidentally modifying annotations belonging to another task.

Therefore:

```text
Current Job
     |
     v
Load annotations for this job
     |
     v
Display only those annotations
```

When switching jobs, annotations from the previous job should not leak into the new job.

---

# Video and Frame Navigation

The application supports frame-by-frame video annotation.

The video workflow is conceptually:

```text
Open Video
    |
    v
OpenCV VideoCapture
    |
    v
Determine frame count
    |
    v
Display current frame
    |
    v
Annotate
    |
    v
Save annotations
    |
    v
Next / Previous frame
```

The application uses OpenCV for video frame access.

Important state includes:

```python
video_path
cap
total_frames
current_index
current_frame
```

The frame number shown in the UI should correspond to the actual frame being displayed.

---

# Database

The application uses a database to persist annotation-related information.

The database layer is intentionally separated from the UI.

Instead of doing SQL operations directly inside every widget, the application can use a database manager/service.

Conceptually:

```text
UI
 |
 v
Database Manager
 |
 v
SQLite
```

This provides a cleaner separation between:

- Presentation
- Application logic
- Persistence

The database can store information such as:

- Jobs
- Labels
- Annotation JSON
- Video name
- Frame index
- AI model configuration
- Other application settings

---

# AI Annotation

AI is used to accelerate the annotation process.

The application is designed around several model types.

## Ball segmentation

The ball model detects/segments the volleyball.

Typical workflow:

```text
Video frame
    |
    v
Ball model
    |
    v
Segmentation result
    |
    v
Convert result to annotation
    |
    v
Display on scene
```

## Players detection

A YOLO-based model can detect players.

The resulting bounding boxes can be converted into player annotations.

Player labels should be identified by their semantic label/name rather than relying on fixed numerical class indices wherever possible.

This is safer when model class ordering changes.

## Court segmentation

The court can be detected using a segmentation model.

For the court geometry, the application can convert the model result into a polygon.

For the specialized court representation, four meaningful corner points can be extracted and stored.

## Action detection

The action model is intended for volleyball actions such as:

- Block
- Spike
- Set
- Receive

These can be associated with the appropriate Actions job.

---

# AI Configuration

AI model configuration is separated from AI execution.

The configuration UI allows users to specify paths to locally available models.

Typical model configuration includes:

```text
Ball model
Court model
Player model
Action model
```

The model paths can be stored in the application's database so they do not need to be entered every time the application starts.

---

# AI Batch Inference

The platform can run AI inference over multiple frames.

A typical workflow is:

```text
AI Panel
   |
   v
Select model
   |
   v
Select target Job
   |
   v
Select labels
   |
   v
Choose frame range / all frames
   |
   v
Run inference
   |
   v
Create annotations
```

The batch inference dialog can provide model checkboxes such as:

- Ball
- Court
- Actions
- Players

It can also allow the user to select the target job and labels.

A useful option is to annotate **all frames**, which can be enabled by default for batch processing.

---

# Configuration

`config_dialog.py` contains configuration-related UI.

Configuration should be used for settings that are not part of the normal frame annotation workflow.

Examples include:

- Job configuration
- Label configuration
- AI model paths
- Other application settings

Keeping configuration in a dedicated dialog avoids overloading the annotation canvas with administrative controls.

---

# Export

Export is responsible for converting the application's internal annotation representation into a format that can be consumed by downstream computer-vision pipelines.

The export design should distinguish between:

## Combined export

A combined export places the relevant annotation information into a common output structure.

This is useful when downstream processing expects a single dataset containing multiple annotation types.

## Separated export

A separated export keeps different annotation jobs or annotation types independent.

This is useful when:

- Different models require different datasets.
- Court, player, ball, and action annotations are trained separately.
- Different annotation formats are required for different tasks.

The export interface should make this distinction clear through labels/tooltips so that users understand what each mode does before exporting.

---

# Keyboard Shortcuts

The application uses keyboard shortcuts to make frame annotation faster.

Current important shortcuts include:

| Shortcut | Action |
|---|---|
| `A` | Previous frame |
| `D` | Next frame |
| `Ctrl + S` | Save |
| `Shift + Delete` | Remove all annotations from the current frame |
| `Ctrl + Shift + A` | Open/run AI batch annotation workflow |

Keyboard shortcuts are particularly important in video annotation because annotators frequently need to move between frames without taking their hands away from the keyboard.

---

# Typical Workflow

A typical annotation session looks like this:

## 1. Start the application

Run the application through the main entry point.

## 2. Configure jobs

Create or select the required annotation jobs.

For example:

```text
Court
Players
Ball
Actions
```

## 3. Configure labels

Create the labels required by each job.

Example:

```text
Court:
    Net
    Attack Zone
    Back Zone

Players:
    Ordinary Player
    Libero

Actions:
    Block
    Spike
    Set
    Receive
```

## 4. Open a video

Load the volleyball video to annotate.

The application determines the frame count and initializes frame navigation.

## 5. Select a job

Choose the task currently being annotated.

Only annotations belonging to the selected job should be displayed.

## 6. Select a label

Choose the semantic label to use for new annotations.

## 7. Draw annotations

Use the appropriate annotation tool.

For example:

- Rectangle for players
- Polygon for court regions
- Segmentation result for the ball

## 8. Navigate frames

Use:

- Previous/Next buttons
- Frame number control
- `A`
- `D`

## 9. Save

Use `Ctrl + S` or the Save action.

## 10. Use AI when appropriate

Configure a model and use AI annotation to automatically generate annotations.

The generated annotations should be reviewed by the annotator.

## 11. Export

When annotation is complete, export the dataset in the required format.

---

# Coordinate Systems and Scaling

One important technical detail is the difference between:

1. Original video/image coordinates
2. Display coordinates

The application may display frames at a fixed UI size such as:

```text
960 x 540
```

while the original video can have a different resolution.

Therefore, annotation points must be converted correctly.

For example:

```text
original coordinate
        |
        | scale
        v
display coordinate
        |
        | user interaction
        v
display annotation
        |
        | inverse scale
        v
original coordinate
```

If:

```python
scale_x = original_width / display_width
scale_y = original_height / display_height
```

then:

```python
original_x = display_x * scale_x
original_y = display_y * scale_y
```

When loading stored original coordinates back into the display:

```python
display_x = original_x / scale_x
display_y = original_y / scale_y
```

Keeping this conversion consistent is essential.

Incorrect coordinate conversion can cause annotations to appear shifted, stretched, or incorrectly positioned after loading.

---

# Adding New Features

When adding a new feature, avoid placing all of the implementation inside `MainWindow`.

A good approach is:

```text
New Feature
    |
    +--> UI component
    |
    +--> Business/service logic
    |
    +--> Database changes if necessary
    |
    +--> MainWindow integration
```

For example, if adding a new AI model:

### Step 1 — Create the model/service logic

Put inference-specific code in the appropriate service module.

### Step 2 — Add configuration

Add a model-path/configuration field to the configuration layer.

### Step 3 — Add UI

Add the required controls/dialog entries.

### Step 4 — Connect to MainWindow

`MainWindow` should coordinate the operation rather than contain the complete model implementation.

### Step 5 — Convert results

Convert model outputs into the application's common annotation representation.

### Step 6 — Save

Use the database layer to persist annotations.

---

# Development Notes

## Keep UI and logic separate

Avoid mixing large amounts of computer-vision or database logic directly into Qt event handlers.

Instead of:

```python
def on_button_clicked(self):
    # hundreds of lines of inference/database/UI code
```

prefer:

```python
def on_button_clicked(self):
    result = self.service.run(...)
    self.update_ui(result)
```

This keeps the application easier to test and maintain.

## Use semantic labels

When working with AI detections, prefer semantic label names over hard-coded class indices when the model/API allows it.

For example:

```python
if detected_label == "libero":
    ...
```

is generally more robust than assuming:

```python
if class_id == 7:
    ...
```

## Avoid annotation leakage between jobs

Whenever the active job changes, the scene should be refreshed using annotations belonging only to the selected job.

Conceptually:

```python
scene.clear_annotations()

annotations = database.get_annotations(
    video=video,
    frame=frame,
    job=current_job,
)

scene.load_annotations(annotations)
```

## Keep frame navigation responsive

Video annotation requires frequent frame changes.

Avoid expensive work on the Qt GUI thread when possible.

Operations such as large batch inference should be moved to worker threads/tasks so the interface remains responsive.

---

# Design Philosophy

The project is intended to grow beyond a simple drawing application.

The overall architecture should therefore preserve these boundaries:

```text
                    Application
                         |
          +--------------+--------------+
          |              |              |
          v              v              v
         UI          Application      Services
                      State
                         |
              +----------+----------+
              |                     |
              v                     v
           Database              AI Models
```

The UI should be responsible for interaction.

The application layer should coordinate workflows.

Services should perform specialized work.

The database should persist information.

AI models should be isolated behind reusable inference interfaces.

This structure makes it easier to add future capabilities such as:

- Additional annotation types
- More AI models
- Tracking
- Dataset validation
- Annotation statistics
- Advanced export formats
- Multi-video projects
- Annotation review
- Quality-control tools

---

# License

This project is licensed under the MIT License.

See [`LICENSE`](LICENSE) for the full license text.

---

# Repository

GitHub:

https://github.com/masouduut94/volleyball-annotation-tool

