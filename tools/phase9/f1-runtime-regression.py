"""Reuse accepted product scenarios without overwriting frozen Phase9 evidence."""
from pathlib import Path
import importlib.util, os, sys

path = Path(__file__).with_name('accept-product.py')
spec = importlib.util.spec_from_file_location('phase9_acceptance', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.evidence = module.root / 'docs/handoff/evidence' / os.environ.get('ACCEPTANCE_EVIDENCE_FOLDER', 'phase9-f1')
assert module.evidence.resolve().is_relative_to((module.root / 'docs/handoff/evidence').resolve())
module.evidence.mkdir(parents=True, exist_ok=True)
module.adb = os.environ['ANDROID_ADB']
module.node = os.environ['ACCEPTANCE_NODE']
module.env.update(ANDROID_ADB=module.adb, ANDROID_SERIAL='DEVICE_ANDROID17')
{'runtime': module.runtime, 'previous': module.previous,
 'visual': module.visual, 'workspace': module.workspace}[sys.argv[1]]()
