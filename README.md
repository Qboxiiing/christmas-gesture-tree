# Christmas Gesture Tree

1. Open christmas_tree.html in Safari.
2. Press the camera icon in the top-right corner and allow camera access.
3. Show either hand and hold a gesture briefly:
   Open palm: Freely dispersed particle cloud
   Fist: Christmas tree
   Thumb/index pinch: Merry Christmas

If Safari cannot enable the camera from a local file, double-click
start_gesture_tree.command. It starts a local-only server and opens Safari.
Keep the Terminal window open while using the page. Press Ctrl+C to stop.
You can also run: python3 generate_tree.py --serve

Mouse and keyboard controls remain available:
Click the tree to form text; click the text to restore the tree.
Hold the left mouse button and drag to rotate the tree.
Use the nebula icon, or press 1 (tree), 2 (text), or 3 (nebula).
The replay and pause icons keep their original behavior.

Hold a gesture for about 0.25-0.35 seconds to confirm it. Brief uncertain frames
are tolerated. Both hands can be detected; the larger, clearly posed hand takes
priority when both are visible. Losing sight of the hand leaves the current shape in place.
Changing a confirmed gesture during a transition continues from the particles'
current positions. All six directed transitions are supported.

Hand tracking uses Safari's compatible page backend, or a browser worker where
supported. A failed worker automatically falls back to the page backend. Camera images are not
recorded or uploaded. No microphone access is requested. Press the camera icon
again to stop the camera. Safari does not need worker OffscreenCanvas support
for camera mode. All models and runtime assets are embedded in the
HTML, so the page works without an Internet connection.

The HTML includes MediaPipe Tasks Vision 1.2.3 and Google's Hand Landmarker model.
Upstream: https://github.com/google-ai-edge/mediapipe
License: Apache-2.0; see LICENSE-MEDIAPIPE.txt and the embedded asset metadata.

To regenerate the page, keep generate_tree.py beside christmas_tree.html.
The generator preserves the model assets embedded in the existing HTML.


## GitHub Pages

Publish this folder as the repository root. Enable Settings > Pages > Deploy
from a branch, choose main and /(root), then Save. The index.html entry redirects
to christmas_tree.html. Camera access is requested only when the camera icon
is pressed. The embedded hand model does not require an external service.

Use GitHub Desktop or Git to upload: christmas_tree.html exceeds GitHub's
25 MiB browser-upload limit, but remains below the 100 MiB Git file limit.
