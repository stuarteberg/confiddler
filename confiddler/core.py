import io
import copy
from pathlib import Path
from os import PathLike
from collections.abc import Mapping

from jsonschema import Draft4Validator, validators
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml import YAML
yaml = YAML()
yaml.default_flow_style = True

from . import json


def load_config(path_or_file, schema):
    """
    Load the config data from the given file (or path to a file),
    and validate it against the given schema.
    
    All missing values will be inserted from schema defaults.
    If a setting is missing and the schema contains no default
    value for it, a ValidationError is raised.
    
    Args:
        path_or_file:
            The raw config data. Either a file object or a file path.
        schema:
            The config schema, already loaded into a Python dict.
        
    Returns:
        dict
    """
    assert isinstance(schema, Mapping), \
        "Invalid schema type: should be a dict of jsonschema specs"
    
    if isinstance(path_or_file, str):
        path_or_file = Path(path_or_file)

    if isinstance(path_or_file, PathLike):
        with open(path_or_file, 'r') as f:
            return _load_config(f, schema)
    else:
        return _load_config(path_or_file, schema)


def _load_config(f, schema):
    config = yaml.load(f)
    validate_and_inject_defaults(config, schema)


def dump_default_config(schema, f=None, format="yaml"): #@ReservedAssignment
    """
    Dump the default config settings from the given schema.
    Settings without default values will use '{{NO_DEFAULT}}' as a placeholder.
    
    
    Args:
        schema:
            The config schema

        f:
            File object to which default config data will be dumped.
            If None, then the default config is returned as a string.
    format:
        Either "json", "yaml", or "yaml-with-comments".
        The "yaml-with-comments" format inserts comments above each setting,
        populated with the setting's "description" field from the schema.

    Returns:
        None, unless no file was provided, in which
        case the default config is returned as a string.
    """
    assert format in ("json", "yaml", "yaml-with-comments")

    if f is None:
        output_stream = io.StringIO()
    else:
        output_stream = f

    if format == "json":
        default_instance = inject_defaults( {}, schema )
        json.dump( default_instance, output_stream, indent=4 )
    else:
        default_instance = inject_defaults( {}, schema, (format == "yaml-with-comments"), 2 )
        yaml.dump(default_instance, output_stream )

    if f is None:
        return output_stream.getvalue()


def flow_style(ob):
    """
    Convert the object into its corresponding ruamel.yaml subclass,
    to alter the yaml pretty printing behavior for this object.
    
    This allows us to print default configs in yaml 'block style', except for specific
    values (e.g. int sequences), which look nicer in 'flow style'.
    
    (For all other uses, the returned ob still looks like a list/dict/whatever)
    """
    sio = io.StringIO()
    yaml.dump(ob, sio)
    sio.seek(0)
    l = yaml.load(sio)
    assert l.fa.flow_style()
    return l


class Dict(dict):
    """
    This subclass allows us to tag dicts with a new attribute 'from_default'
    to indicate that the config sub-object was generated from scratch.
    (This is useful for figuring out which fields were user-provided and
    which were automatically supplied from the schema.)
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.from_default = False



def extend_with_default(validator_class):
    """
    This code was adapted from the jsonschema FAQ:
    http://python-jsonschema.readthedocs.org/en/latest/faq/
    """
    validate_properties = validator_class.VALIDATORS["properties"]

    def set_defaults_and_validate(validator, properties, instance, schema):
        for _property, subschema in properties.items():
            if "default" in subschema:
                default = copy.deepcopy(subschema["default"])
                if isinstance(default, dict):
                    default = Dict(default)
                    default.from_default = True
                instance.setdefault(property, default)

        for error in validate_properties(validator, properties, instance, schema):
            yield error

    return validators.extend(validator_class, {"properties" : set_defaults_and_validate})

DefaultValidatingDraft4Validator = extend_with_default(Draft4Validator)

def validate(instance, schema, cls=None, *args, inject_defaults=False, **kwargs):
    """
    Drop-in replacement for jsonschema.validate(), with the following extended functionality:

    - Specifically allow types from ruamel.yaml.comments
    - If inject_defaults is True, this function *modifies* the instance IN-PLACE
      to fill missing properties with their schema-provided default values.

    See the jsonschema FAQ:
    http://python-jsonschema.readthedocs.org/en/latest/faq/
    """
    if cls is None:
        cls = validators.validator_for(schema)
    cls.check_schema(schema)

    if inject_defaults:
        # Add default-injection behavior to the validator
        cls = extend_with_default(cls)
    
    # By default, jsonschema expects JSON objects to be of type 'dict'.
    # We also want to permit ruamel.yaml.comments.CommentedSeq and CommentedMap
    # https://python-jsonschema.readthedocs.io/en/stable/validate/?highlight=str#validating-with-additional-types
    kwargs["types"] = {"object": (CommentedMap, dict),
                       "array": (CommentedSeq, list)} # Can't use collections.abc.Sequence because that would catch strings, too!
    
    # Validate and inject defaults.
    cls(schema, *args, **kwargs).validate(instance)


def validate_and_inject_defaults(instance, schema, cls=None, *args, **kwargs):
    validate(instance, schema, cls=None, *args, inject_defaults=True, **kwargs)


def extend_with_default_without_validation(validator_class, include_yaml_comments=False, yaml_indent=2):
    validate_properties = validator_class.VALIDATORS["properties"]
    validate_items = validator_class.VALIDATORS["items"]

    def set_default_object_properties(validator, properties, instance, schema):
        for property, subschema in properties.items():
            if instance == "{{NO_DEFAULT}}":
                continue
            if "default" in subschema:
                default = copy.deepcopy(subschema["default"])
                
                if isinstance(default, list):
                    try:
                        # Lists of numbers should use 'flow style'
                        # and so should lists-of-lists of numbers
                        # (e.g. bounding boxes like [[0,0,0],[1,2,3]])
                        if ( subschema["items"]["type"] in ("integer", "number") or
                             ( subschema["items"]["type"] == "array" and 
                               subschema["items"]["items"]["type"] in ("integer", "number") ) ):
                            default = flow_style(default)
                    except KeyError:
                        pass
                
                if include_yaml_comments and isinstance(default, dict):
                    default = CommentedMap(default)
                    # To keep track of the current indentation level,
                    # we just monkey-patch this member onto the dict.
                    default.key_indent = instance.key_indent + yaml_indent
                    default.from_default = True
                if include_yaml_comments and isinstance(default, list):
                    if not isinstance(default, CommentedSeq):
                        default = CommentedSeq(copy.copy(default))
                    
                    # To keep track of the current indentation level,
                    # we just monkey-patch this member onto the dict.
                    default.key_indent = instance.key_indent + yaml_indent
                    default.from_default = True
                if property not in instance:
                    instance[property] = default
            else:
                if property not in instance:
                    instance[property] = "{{NO_DEFAULT}}"

            if include_yaml_comments and "description" in subschema:
                comment = '\n' + subschema["description"]
                if comment[-1] == '\n':
                    comment = comment[:-1]
                instance.yaml_set_comment_before_after_key(property, comment, instance.key_indent)

        for _error in validate_properties(validator, properties, instance, schema):
            # Ignore validation errors
            pass

    def fill_in_default_array_items(validator, items, instance, schema):
        if include_yaml_comments and items["type"] == "object":
            new_items = []
            for item in instance:
                new_item = CommentedMap(item)
                new_item.key_indent = instance.key_indent + yaml_indent
                new_items.append(new_item)
            instance.clear()
            instance.extend(new_items)

        # Descend into array list
        for _error in validate_items(validator, items, instance, schema):
            # Ignore validation errors
            pass

    def ignore_required(validator, required, instance, schema):
        return

    return validators.extend(validator_class, { "properties" : set_default_object_properties,
                                                "items": fill_in_default_array_items,
                                                "required": ignore_required })

#DefaultInjector = extend_with_default(Draft4Validator)

def inject_defaults(instance, schema, include_yaml_comments=False, yaml_indent=2, cls=None, *args, **kwargs):
    """
    Like the above validate_and_inject_defaults, but:
    
    1. Ignore schema validation errors and 'required' property errors
    
    2. If no default is given for a property, inject '{{NO_DEFAULT}}',
       even if the property isn't supposed to be a string.
       
    3. If include_yaml_comments is True, insert CommentedMap objects instead of ordinary dicts,
       and insert a comment above each key, with the contents of the property "description" in the schema.
    
    Args:
        instance:
            The Python object to inject defaults into.  May be an empty dict ({}).

        schema:
            The schema data to pull defaults from

        include_yaml_comments:
            Whether or not to return ruamel.yaml-compatible dicts so that
            comments will be written when the data is dumped to YAML.
    
        yaml_indent:
            To ensure correctly indented comments, you must specify the indent
            step you plan to use when this data is eventually dumped as yaml.
    
    Returns:
        A copy of instance, with default values injected, and comments if specified.
    """
    if cls is None:
        cls = validators.validator_for(schema)
    cls.check_schema(schema)

    # Add default-injection behavior to the validator
    extended_cls = extend_with_default_without_validation(cls, include_yaml_comments, yaml_indent)
    
    if include_yaml_comments:
        instance = CommentedMap(instance)
        instance.key_indent = 0 # monkey-patch!
    else:
        instance = dict(instance)
    
    # Inject defaults.
    extended_cls(schema, *args, **kwargs).validate(instance)
    return instance

if __name__ == "__main__":
    schema = {
        "type": "object",
        "properties": {
            "outer-object": {
                "type": "object",
                "properties" : {
                    "inner-object": {
                        "type": "string",
                        "description": "This is an inner object string",
                        "default": "INNER-DEFAULT"
                    },
                    "inner-object-2": {
                        "description": "This is an inner object integer",
                        "type": "integer"
                    },
                    "inner-list": {
                        "description": "This is a list, and the default YAML style should be shown in flow-style",
                        "type": "array",
                        "items": { "type": "integer" }, # <-- Must set "type": "integer" for flow style to be applied in YAML dumps
                        "default": [1,2,3]
                    }
                },
                "default": {} # <-- MUST PROVIDE DEFAULT OBJECT
            }
        }
    }
    
    import json #@Reimport
    
    obj1 = {}
    DefaultValidatingDraft4Validator(schema).validate(obj1)
    assert obj1 == {'outer-object': {'inner-object': 'INNER-DEFAULT', "inner-list": [1,2,3]}}
    assert obj1['outer-object'].from_default

    print("obj1:")
    print(json.dumps(obj1, indent=4) + '\n')
        
    schema_nodefault = copy.deepcopy(schema)
    del schema_nodefault["properties"]["outer-object"]["default"]
    obj2 = {}
    DefaultValidatingDraft4Validator(schema_nodefault).validate(obj2)
    assert obj2 == {} # whoops

    print("obj2:")
    print(json.dumps(obj2, indent=4) + '\n')
    
    obj3 = {}
    obj3_with_defaults = inject_defaults(obj3, schema, include_yaml_comments=True)
    print(obj3)

    print("obj3_with_defaults:")
    #print(json.dumps(obj3, indent=4) + '\n')
    
    import sys
    from ruamel.yaml import YAML #@Reimport
    yaml = YAML()
    yaml.default_flow_style = False
    yaml.dump(obj3_with_defaults, sys.stdout)
