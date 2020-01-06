from jsonschema import ValidationError
from .core import load_config, dump_config, dump_default_config, validate, emit_defaults, flow_style, convert_to_base_types
from . import json

from ._version import get_versions
__version__ = get_versions()['version']
del get_versions
