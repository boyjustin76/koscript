# `premiere` — hand an edit to Premiere Pro, and read what it already has

No Premiere needed. No extra packages.

```python
from koscript.premiere import fcp7

xml, tracks = fcp7.build({
    'name': 'rough cut', 'fps': 29.97, 'width': 1920, 'height': 1080,
    'sources': {'cam': {'path': 'D:/footage/a (1).mp4', 'dur': 882.2}},
    'cuts': [{'src': 'cam', 'in': 12.3, 'out': 15.1, 'label': 'intro'},
             {'src': 'cam', 'in': 40.0, 'out': 44.5}],
})
open('cut.xml', 'w', encoding='utf-8', newline='\n').write(xml)
```

Import `cut.xml` in Premiere: **File → Import**.

## If Premiere says "the project is damaged and cannot be opened"

That is the only error you get. It never names the clip. Worse, several causes only
bite once the file is big enough — so a three-cut test passes and a seventy-cut edit
fails, which looks like a clip-count limit. It is not.

Six causes, all of which `fcp7.build` handles:

| | |
|---|---|
| **1. `pathurl` encoding** | Premiere writes the drive colon as `%3a`, hex in **lowercase**, and leaves `( ) [ ] &` **literal**. Percent-encode the brackets and it cannot find the media; with many clips the import then collapses. |
| **2. `end - start` ≠ `out - in`** | Round the timeline position and the source range separately and they drift a frame apart. |
| **3. `out` past the end of the media** | Round the last frame *up* and you land past the file. Floor it. |
| **4. `timebase` not in 24/25/30/50/60** | A 240 fps phone clip written as `<timebase>240</timebase>` fails. Write the sequence timebase and count in/out as `seconds × sequence fps`. |
| **5. Overlap inside one track** | Not even one frame. |
| **6. Clips out of start order** | They import, but most do not show and the rest flicker. |

Still failing? Build with `thin=True`. That drops the audio/video `<link>` elements —
clips no longer grab as one piece, but the file is far easier to bisect.

### Just the URL

If you only want the encoding, that is one function:

```python
from koscript.premiere import pathurl
pathurl(r'C:\media\a (1) & b.mp4')
# 'file://localhost/C%3a/media/a%20(1)%20&%20b.mp4'
```

## Reading a `.prproj`

A `.prproj` is **gzipped XML**. Everything is in there — sequences, effects, keyframes,
media paths. Checking a project by screenshotting Premiere is wasted effort.

```python
from koscript.premiere import project

project.read_xml('edit.prproj')           # the whole XML
gone, total = project.offline('edit.prproj')
```

### Before you move a folder, ask who points at it

```python
for proj, paths in project.referencing('old/footage', 'D:/work'):
    print(proj, len(paths))
```

Moving a folder once took ten sources offline in an edit nobody connected to it. The
person moving checked that every file was in the box and never asked *who points at
this path*. **Check the using side, not the packing side** — and include the
destination folder in the search, since a project already sitting there may still
point at the old location.

### `RelativePath` is escaped twice

`&` arrives as `&amp;amp;`. That is Premiere's own habit, not corruption — untouched
projects show it, with `ActualMediaFilePath` normal. Unescape once and you will report
healthy clips as broken. `project.links` unescapes twice.

A clip counts as offline only when the absolute path is gone **and** no relative-path
candidate of the same name exists — otherwise Premiere would still find it.
