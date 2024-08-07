import io
import copy
from os import PathLike
from pathlib import Path
from collections.abc import Mapping, Sequence

from jsonschema import validators
from jsonschema.exceptions import _Error, ValidationError
from ruamel.yaml.compat import ordereddict
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml import YAML, RoundTripRepresenter
yaml = YAML()
yaml.default_flow_style = False

from . import json

# Remove comparability of ValidationError and SchemaError,
# and endow them with hashability instead.
# Otherwise they can choke pytest.
# See https://github.com/Julian/jsonschema/issues/477
_Error.__eq__ = object.__eq__
_Error.__ne__ = object.__ne__
_Error.__hash__ = object.__hash__


def load_config(path_or_file, schema={}, inject_defaults=True):
    """
    Convenience wrapper around :py:func:`validate()`.
    (This function accepts a file).
    
    Load the config data from the given file (or path to a file),
    and validate it against the given schema.
    
    All missing values will be inserted from schema defaults.
    If a setting is missing and the schema contains no default
    value for it, a ``ValidationError`` is raised.
    
    Note:
        If your config data is already loaded into a dict and
        you just want to validate it and/or inject defaults,
        see :py:func:`validate()`.
    
    Args:
        path_or_file:
            The raw config data. Either a file object or a file path.
        schema:
            The config schema, already loaded into a Python ``dict``.
        
    Returns:
        ``dict``
    """
    assert isinstance(schema, Mapping), \
        "Invalid schema type: should be a dict of jsonschema specs"
    
    if isinstance(path_or_file, str):
        path_or_file = Path(path_or_file)

    def _load_config(f, schema):
        config = yaml.load(f)
        validate(config, schema, inject_defaults=inject_defaults)
        return config

    if isinstance(path_or_file, PathLike):
        with open(path_or_file, 'r') as f:
            return _load_config(f, schema)
    else:
        return _load_config(path_or_file, schema)


def dump_config(config_data, path_or_file=None):
    """
    Convenience wrapper for YAML().dump()

    Dump the given config data to the given path or file.
    If no path or file is given, return it as a string.
    """
    if path_or_file is None:
        f = io.StringIO()
        yaml.dump(config_data, f)
        f.seek(0)
        return f.getvalue()
    elif isinstance(path_or_file, (str, PathLike)):
        with open(path_or_file, 'w') as f:
            yaml.dump(config_data, f)
    else:
        yaml.dump(config_data, path_or_file)


def dump_default_config(schema, f=None, format="yaml"): #@ReservedAssignment
    """
    Convenience wrapper around :py:func:`emit_defaults()`.
    (This function writes to a file).

    Dump the default config settings from the given schema.
    Settings without default values will use ``"{{NO_DEFAULT}}"`` as a placeholder.
    
    Args:
        schema:
            The config schema

        f:
            File object to which default config data will be dumped.
            If ``None``, then the default config is returned as a string.
    format:
        Either ``"json"``, ``"yaml"``, or ``"yaml-with-comments"``.
        The ``"yaml-with-comments"`` format inserts comments above each setting,
        populated with the setting's ``"description"`` field from the schema.

    Returns:
        ``None``, unless no file was provided, in which
        case the default config is returned as a string.
    """
    assert format in ("json", "yaml", "yaml-with-comments")

    if f is None:
        output_stream = io.StringIO()
    else:
        output_stream = f

    if format == "json":
        default_instance = emit_defaults( schema )
        json.dump( default_instance, output_stream, indent=4 )
    else:
        default_instance = emit_defaults( schema, (format == "yaml-with-comments"), 2 )
        yaml.dump(default_instance, output_stream )

    if f is None:
        return output_stream.getvalue()


def emit_defaults(schema, include_yaml_comments=False, yaml_indent=2, base_cls=None, *args, **kwargs):
    """
    Emit all default values for the given schema.
    
    Similar to calling ``validate({}, schema, inject_defaults=True)``, except:
    
    1. Ignore schema validation errors and 'required' property errors
    
    2. If no default is given for a property, inject ``"{{NO_DEFAULT}}"``,
       even if the property isn't supposed to be a string.
       
    3. If ``include_yaml_comments`` is True, insert ``CommentedMap`` objects instead of ordinary dicts,
       and insert a comment above each key, with the contents of the property ``"description"`` in the schema.
    
    Args:
        schema:
            The schema data to pull defaults from

        include_yaml_comments:
            Whether or not to return ``ruamel.yaml`` objects so that
            comments will be written when the data is dumped to YAML.

        yaml_indent:
            To ensure correctly indented comments, you must specify the indent
            step you plan to use when this data is eventually dumped as yaml.

    Returns:
        A copy of instance, with default values injected, and comments if specified.
    """
    instance = {}
    
    instance = convert_to_commented(instance, 0, yaml_indent)
    if "description" in schema:
        instance.yaml_set_start_comment('\n' + schema["description"] + '\n\n')
    
    if base_cls is None:
        base_cls = validators.validator_for(schema)
    base_cls.check_schema(schema)

    def is_object(checker, instance):
        return ( base_cls.TYPE_CHECKER.is_type(instance, "object") or
                 isinstance(instance, (ordereddict, CommentedMap)) )

    def is_array(checker, instance):
        return ( base_cls.TYPE_CHECKER.is_type(instance, "array") or
                 isinstance(instance, CommentedSeq) )

    # By default, jsonschema expects JSON objects to be of type 'dict'.
    # We also want to permit ruamel.yaml.comments.CommentedSeq and CommentedMap
    type_checker = base_cls.TYPE_CHECKER.redefine_many(
        {"object": is_object, "array": is_array} )

    cls = validators.extend(base_cls, type_checker=type_checker)

    # Add default-injection behavior to the validator
    cls = extend_with_default_without_validation(cls, yaml_indent)
    extended_validator = cls(schema, *args, **kwargs)

    # Inject defaults.
    extended_validator.validate(instance)

    if not include_yaml_comments:
        instance = convert_to_commented(instance, 0, yaml_indent, strip_comments=True)
    return instance


def validate(instance, schema, base_cls=None, *args, inject_defaults=False, **kwargs):
    """
    Drop-in replacement for ``jsonschema.validate()``,
    with the following extended functionality:

    - Specifically allow types from ``ruamel.yaml.comments``
    - If ``inject_defaults`` is ``True``, this function *modifies* the instance IN-PLACE
      to fill missing properties with their schema-provided default values.

    See the `jsonschema FAQ <http://python-jsonschema.readthedocs.org/en/latest/faq>`_
    for details and caveats.
    """
    if base_cls is None:
        base_cls = validators.validator_for(schema)
    base_cls.check_schema(schema)

    def is_object(checker, instance):
        return ( base_cls.TYPE_CHECKER.is_type(instance, "object") or
                 isinstance(instance, (ordereddict, CommentedMap)) )

    def is_array(checker, instance):
        return ( base_cls.TYPE_CHECKER.is_type(instance, "array") or
                 isinstance(instance, CommentedSeq) )

    # By default, jsonschema expects JSON objects to be of type 'dict'.
    # We also want to permit ruamel.yaml.comments.CommentedSeq and CommentedMap
    type_checker = base_cls.TYPE_CHECKER.redefine_many(
        {"object": is_object, "array": is_array} )

    cls = validators.extend(base_cls, type_checker=type_checker)

    if inject_defaults:
        # Add default-injection behavior to the validator
        cls = extend_with_default(cls)
        
    # Validate and inject defaults.
    validator = cls(schema, *args, **kwargs)
    validator.validate(instance)


def extend_with_default(validator_class):
    """
    Helper function for validate(..., inject_defaults=True)
    
    This code was adapted from the jsonschema FAQ:
    http://python-jsonschema.readthedocs.org/en/latest/faq/
    
    Unlike extend_with_default_without_validation(), below,
    this function does not bother to convert the defaults to
    commented YAML types before injecting them.
    (The results of this function are not meant for pretty-printing.)
    """
    validate_properties = validator_class.VALIDATORS["properties"]
    validate_additionalProperties = validator_class.VALIDATORS["additionalProperties"]
    validate_items = validator_class.VALIDATORS["items"]

    def _set_property_defaults(properties, instance):
        for property_name, subschema in properties.items():
            if isinstance(instance, Mapping) and "default" in subschema:
                default = copy.deepcopy(subschema["default"])
                if isinstance(default, dict):
                    default = _Dict(default)
                    default.from_default = True
                instance.setdefault(property_name, default)

    def set_defaults_and_validate(validator, properties_schema, instance, schema):
        _set_property_defaults(properties_schema, instance)
        for error in validate_properties(validator, properties_schema, instance, schema):
            yield error

    def set_additional_props_defaults_and_validate(validator, additionalProperties_schema, instance, schema):
        if additionalProperties_schema in (True, False, None) or additionalProperties_schema.get('type', 'object') != 'object':
            for error in validate_additionalProperties(validator, additionalProperties_schema, instance, schema):
                yield error
        else:
            # Figure out which of the instance's properties are not named by
            # the properties schema and therefore count as 'additionalProperties'
            extra_prop_names = set(instance.keys()) - set(schema.get('properties', {}).keys())

            # To re-use _set_property_defaults function to insert defaults into the 'additional' properties,
            # we'll duplicate the schema for each additional name.
            extra_prop_schemas = {k: additionalProperties_schema for k in extra_prop_names}
            _set_property_defaults(extra_prop_schemas, instance)

            for error in validate_properties(validator, extra_prop_schemas, instance, {"properties": extra_prop_schemas, "default": schema.get("default", {})}):
                yield error

    def fill_in_default_array_items(validator, items_schema, instance, schema):
        if "default" in items_schema and isinstance(items_schema["default"], Mapping):
            new_items = []
            for item in instance:
                if not isinstance(item, Mapping):
                    new_items.append(item)
                else:
                    default = copy.deepcopy(items_schema["default"])
                    default = _Dict(default)
                    if item == {}:
                        # FIXME: Instead of a simple bool, it would be better to specify
                        #        WHICH properties in this dict were copied from the default value.
                        default.from_default = True
                    default.update(item)
                    new_items.append(default)

            instance.clear()
            instance.extend(new_items)

        # Descend into array list
        for error in validate_items(validator, items_schema, instance, schema):
            yield error


    def check_required(validator, required, instance, schema):
        # We only check 'required' properties that don't have specified defaults
        for prop in required:
            if prop in instance:
                continue
            if prop not in schema['properties'] or 'default' not in schema['properties'][prop]:
                yield ValidationError("%r is a required property and has no default value in your schema" % prop)

    return validators.extend(
        validator_class,
        {
            "properties" : set_defaults_and_validate,
            "additionalProperties": set_additional_props_defaults_and_validate,
            "items": fill_in_default_array_items,
            "required": check_required
        }
    )


def extend_with_default_without_validation(validator_class, yaml_indent=2):
    """
    Helper function for emit_defaults(), above.
    Similar to extend_with_default(), but does not validate
    (errors are ignored) and also uses yaml types (for printing).
    """
    validate_properties = validator_class.VALIDATORS["properties"]
    validate_additionalProperties = validator_class.VALIDATORS["additionalProperties"]
    validate_items = validator_class.VALIDATORS["items"]

    def set_default_object_properties_and_ignore_errors(validator, properties, instance, schema):
        _set_default_object_properties(properties, instance, yaml_indent)
        for _error in validate_properties(validator, properties, instance, schema):
            # Ignore validation errors
            pass

    def set_default_additionalProperties_and_ignore_errors(validator, additionalProperties, instance, schema):
        if additionalProperties in (True, False, None):
            for _error in validate_additionalProperties(validator, additionalProperties, instance, schema):
                # Ignore validation errors
                pass
        elif instance == '{{NO_DEFAULT}}':
            return
        elif not isinstance(instance, Mapping):
            raise ValidationError(f"Expected an object for '{instance}', not ({type(instance)})")
        else:
            # Figure out which of the instance's properties are not named by
            # the properties schema and therefore count as 'additionalProperties'
            extra_prop_names = set(instance.keys()) - set(schema.get('properties', {}).keys())

            # To re-use _set_property_defaults function to insert defaults into the 'additional' properties,
            # we'll duplicate the schema for each additional name.
            extra_prop_schemas = {k: additionalProperties for k in extra_prop_names}

            _set_default_object_properties(extra_prop_schemas, instance, yaml_indent)
            for _error in validate_properties(validator, extra_prop_schemas, instance, {"properties": extra_prop_schemas, "default": schema.get("default", {})}):
                # Ignore validation errors
                pass

    def fill_in_default_array_items(validator, items_schema, instance, schema):
        if "default" in items_schema and isinstance(items_schema["default"], Mapping):
            new_items = []
            for item in instance:
                if not isinstance(item, Mapping):
                    new_items.append(item)
                else:
                    default = convert_to_commented(items_schema["default"], instance.key_indent + yaml_indent, yaml_indent)
                    new_item = convert_to_commented(item, instance.key_indent + yaml_indent, yaml_indent)
                    if item == {}:
                        default.from_default = True
                    default.update(new_item)
                    new_items.append(default)
            instance.clear()
            instance.extend(new_items)

        # Descend into array list
        for _error in validate_items(validator, items_schema, instance, schema):
            # Ignore validation errors
            pass

    def ignore_required(validator, required, instance, schema):
        return

    return validators.extend(
        validator_class,
        {
            "properties" : set_default_object_properties_and_ignore_errors,
            "additionalProperties" : set_default_additionalProperties_and_ignore_errors,
            "items": fill_in_default_array_items,
            "required": ignore_required
        }
    )


def _set_default_object_properties(properties, instance, yaml_indent):
    """
    Helper for extend_with_default_without_validation().
    Inject default values for the given object properties on the given instance.
    """
    for property_name, subschema in properties.items():
        if instance == "{{NO_DEFAULT}}":
            continue

        # In tricky cases such as {oneOf: [{type: object, type: str}]},
        # then the 'instance' may not be valid for the particular 'oneOf' schema we're looking at.
        if not isinstance(instance, (list, dict)):
            continue

        if "default" in subschema:
            if isinstance(subschema["default"], (dict, list)):
                subschema["default"] = convert_to_commented(subschema["default"], instance.key_indent + yaml_indent, yaml_indent)
            default = convert_to_commented(subschema["default"], instance.key_indent + yaml_indent, yaml_indent)

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

            if isinstance(instance, Mapping) and property_name not in instance:
                instance[property_name] = default
        else:
            if isinstance(instance, Mapping) and property_name not in instance:
                instance[property_name] = "{{NO_DEFAULT}}"

        if "description" in subschema:
            comment = '\n' + subschema["description"]
            if comment[-1] == '\n':
                comment = comment[:-1]
            instance.yaml_set_comment_before_after_key(property_name, comment, instance.key_indent)


def flow_style(ob):
    """
    This function can be used to fine-tune the format of exported YAML configs.
    (It is only needed rarely.)
    
    By default, :py:func:`dump_default_config()` uses 'block style':
    
    .. code-block:: python
    
        >>> schema = {
              "properties": {
                 "names": {
                   "default": ['a', 'b', 'c']
                 }
               }
            }

        >>> dump_default_config(schema, sys.stdout)
        names:
        - a
        - b
        - c
    
    But if you'd prefer for a particular value to be written with 'flow style',
    wrap it with ``flow_style()``:
    
    .. code-block:: python
    
        >>> from confiddler import flow_style
        >>> schema = {
              "properties": {
                 "names": {
                   "default": flow_style(['a', 'b', 'c'])
                 }
               }
            }

        >>> dump_default_config(schema, sys.stdout)
        names: [a, b, c]

    """
    sio = io.StringIO()
    yaml.dump(ob, sio)
    sio.seek(0)
    l = yaml.load(sio)
    l.fa.set_flow_style()
    assert l.fa.flow_style()
    return l


def convert_to_commented(o, key_indent, indent_increment, strip_comments=False):
    """
    Recurse into the given list or dict and convert all
    dicts within it to CommentedMap or CommentedSeq,
    and monkey-patch a 'key_indent' property onto it.
    """
    o = copy.deepcopy(o)
    return _convert_to_commented(o, key_indent, indent_increment, strip_comments)


def _convert_to_commented(o, key_indent, indent_increment, strip_comments=False):
    # We take pains to preserve the parent object if it is already a CommentedMap,
    # so we also preserve any flags it has, such as o.fa.flow_style() or o.from_default
    if isinstance(o, Mapping):
        for k in o.keys():
            o[k] = _convert_to_commented(o[k], key_indent + indent_increment, indent_increment, strip_comments)
        if not isinstance(o, CommentedMap):
            o = CommentedMap(o)
        o.key_indent = key_indent
        if strip_comments and hasattr(o, 'ca'):
            o.ca.items.clear()
        return o
    elif isinstance(o, list):
        for i in range(len(o)):
            o[i] = _convert_to_commented(o[i], key_indent + indent_increment, indent_increment, strip_comments)
        if not isinstance(o, CommentedSeq):
            o = CommentedSeq(o)
        o.key_indent = key_indent
        if strip_comments and hasattr(o, 'ca'):
            o.ca.items.clear()
        return o
    else:
        return o


def convert_to_base_types(o):
    """
    Convert the given container into a standard dict or list (recursively).
    This is useful if you need to pass your config to a function that is
    hard-coded to check for dicts or lists rather than Mapping or Sequence.
    """
    if type(o) != dict and isinstance(o, Mapping):
        return { k: convert_to_base_types(v) for k,v in o.items() }
    if type(o) not in (list, str, bytes) and isinstance(o, Sequence):
        return [convert_to_base_types(i) for i in o]
    return o


class _Dict(dict):
    """
    This subclass allows us to tag dicts with a new attribute 'from_default'
    to indicate that the config sub-object was generated from scratch.
    (This is useful for figuring out which fields were user-provided and
    which were automatically supplied from the schema.)
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.from_default = False

RoundTripRepresenter.add_representer(_Dict, RoundTripRepresenter.represent_dict)
