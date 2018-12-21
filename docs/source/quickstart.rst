.. _quickstart:


Quickstart
----------

Define your schema

.. code-block:: python

    >>> from confiddler import dump_default_config, load_config
    
    >>> schema = {
          "description": "Settings for a robot vacuum cleaner",
          "properties": {
            "speed": {
              "description": "Speed of the robot (1-10)",
              "type": "number",
              "minValue": 1,
              "maxValue": 10,
              "default": 1
            },
            "movement": {
              "description": "Movement strategy: random, raster, or spiral",
              "type": "string",
              "enum": ["random", "raster", "spiral"],
              "default": "random"
            }
          }
        }


Show your user the default config.

.. code-block:: python

    >>> dump_default_config(schema, sys.stdout, 'yaml')
    speed: 1
    movement: random
    
    >>> dump_default_config(schema, sys.stdout, 'yaml-with-comments')
    #
    # Settings for a robot vacuum cleaner
    #
    
    # Speed of the robot (1-10)
    speed: 1
    
    # Movement strategy: random, raster, or spiral
    movement: random


Load your user's config.

.. code-block:: yaml

    # my-robot-config.yaml
    speed: 2

.. code-block:: python

    >>> load_config('my-robot-config.yaml', schema, inject_defaults=True)
    {'speed': 2, 'movement': 'random'}

