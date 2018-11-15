from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from rasa_nlu.extractors.nested_entity_extractor import NestedEntityExtractor


def test_composite_entities():
    entities = [{
        "entity": "meal",
        "value": "rice and chicken",
        "start": 0,
        "end": 6
    }, {
        "entity": "meal",
        "value": "yam, egg",
        "start": 0,
        "end": 6
    }, {
        "entity": "meal",
        "value": "noodles",
        "start": 0,
        "end": 6
    }]
    nested_entities = {
        "lookup_tables": [
            {
                "name": "carbohydrates",
                "elements": [
                    "noodles",
                    "noodle",
                    "rice",
                    "yam"
                ]
            },
            {
                "name": "protein",
                "elements": [
                    "chicken",
                    "eggs",
                    "pork",
                    "egg"
                ]
            }
        ],
        "composite_entities": [
            {
                "composites": [
                    "@protein",
                    "@carbohydrates"
                ],
                "name": "meal"
            }
        ]
    }
    NestedEntityExtractor(
        nested_entities=nested_entities).split_nested_entities(entities)
    assert len(entities) == 3
    assert entities[0]["value"] == {
        "protein": "chicken",
        "carbohydrates": "rice"
    }
    assert entities[1]["value"] == {
        "protein": "egg",
        "carbohydrates": "yam"
    }
    assert entities[2]["value"] == {
        "carbohydrates": "noodles"
    }
