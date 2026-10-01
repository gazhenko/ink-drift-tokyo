"""Entry point:  blender -b -P Tools/blender/foliage/build.py -- <ModelName|group|all> [...] [--no-preview]

Builds each model in a fresh scene, exports FBX to Game/Assets/InkDrift/Models/Trees/,
renders a toon preview into Tools/blender/foliage/previews/, and re-imports the FBX to verify it.
"""
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import foliage_lib as fl  # noqa: E402

REGISTRY = {}


def load_registry():
    import importlib
    for mod in ("trees", "shrubs", "ground", "rocks"):
        try:
            m = importlib.import_module(mod)
        except ModuleNotFoundError as e:
            if e.name == mod:
                continue
            raise
        for k, v in m.BUILDERS.items():
            REGISTRY[k] = (mod, v)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    preview = "--no-preview" not in argv
    names = [a for a in argv if not a.startswith("--")]
    load_registry()
    todo = []
    for n in names or ["all"]:
        if n == "all":
            todo += list(REGISTRY)
        elif n in REGISTRY:
            todo.append(n)
        else:
            pref = [k for k in REGISTRY if k.startswith(n) or REGISTRY[k][0] == n]
            if not pref:
                print("UNKNOWN MODEL", n)
            todo += pref
    failures = []
    for n in todo:
        t0 = time.time()
        try:
            res = REGISTRY[n][1]()
            objs, extra = res if isinstance(res, tuple) else (res, {})
            if preview:
                fl.finish(n, objs, preview_kw=extra.pop("preview_kw", None), extra=extra)
            else:
                fl.export_fbx(objs, n)
                fl.write_stats(n, objs, extra)
        except Exception:
            traceback.print_exc()
            failures.append(n)
        print(f"DONE {n} in {time.time() - t0:.1f}s")
    if failures:
        print("FAILURES", failures)


main()
