"""Entry point:  blender -b -P Tools/blender/props/build_props.py -- <module> [builder ...] [--no-preview] [--no-export]
Builds the registered builders of Tools/blender/props/<module>.py, exports FBX into
Game/Assets/InkDrift/Models/Props/ and renders previews into Tools/blender/props/previews/."""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import propkit

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
flags = [a for a in argv if a.startswith('--')]
args = [a for a in argv if not a.startswith('--')]
if '--no-preview' in flags:
    propkit.OPTIONS['preview'] = False
if '--no-export' in flags:
    propkit.OPTIONS['export'] = False
module = args[0]
fails = propkit.run_builders(module, args[1:] or None)
sys.exit(1 if fails else 0)
