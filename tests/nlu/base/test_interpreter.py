import rasa.nlu

import pytest

from rasa.core.interpreter import (
    NaturalLanguageInterpreter,
    RasaNLUHttpInterpreter,
    RasaNLUInterpreter,
    RegexInterpreter,
)
from rasa.model import get_model_subdirectories, get_model
from rasa.nlu import training_data
from rasa.nlu.components import registry
from rasa.nlu.model.interpreter import Interpreter
from rasa.nlu.model.exceptions import UnsupportedModelError
from rasa.utils.endpoints import EndpointConfig
from tests.nlu import utilities


@utilities.slowtest
@pytest.mark.parametrize(
    "pipeline_template", list(registry.registered_pipeline_templates.keys())
)
async def test_interpreter(pipeline_template, component_builder, tmpdir):
    test_data = "data/examples/rasa/demo-rasa.json"
    _conf = utilities.base_test_conf(pipeline_template)
    _conf["data"] = test_data
    td = training_data.DataManager.load_data(test_data)
    interpreter = await utilities.interpreter_for(
        component_builder, "data/examples/rasa/demo-rasa.json", tmpdir.strpath, _conf
    )

    texts = ["good bye", "i am looking for an indian spot"]

    for text in texts:
        result = interpreter.parse(text, time=None)
        assert result["text"] == text
        assert not result["intent"]["name"] or result["intent"]["name"] in td.intents
        assert result["intent"]["confidence"] >= 0
        # Ensure the model doesn't detect entity types that are not present
        # Models on our test data set are not stable enough to
        # require the exact entities to be found
        for entity in result["entities"]:
            assert entity["entity"] in td.entities


@pytest.mark.parametrize(
    "metadata",
    [
        {"rasa_version": "0.11.0"},
        {"rasa_version": "0.10.2"},
        {"rasa_version": "0.12.0a1"},
        {"rasa_version": "0.12.2"},
        {"rasa_version": "0.12.3"},
        {"rasa_version": "0.13.3"},
        {"rasa_version": "0.13.4"},
        {"rasa_version": "0.13.5"},
        {"rasa_version": "0.14.0a1"},
        {"rasa_version": "0.14.0"},
        {"rasa_version": "0.14.1"},
        {"rasa_version": "0.14.2"},
        {"rasa_version": "0.14.3"},
        {"rasa_version": "0.14.4"},
        {"rasa_version": "0.15.0a1"},
        {"rasa_version": "1.0.0a1"},
    ],
)
def test_model_not_compatible(metadata):
    with pytest.raises(UnsupportedModelError):
        Interpreter.ensure_model_compatibility(metadata)


@pytest.mark.parametrize("metadata", [{"rasa_version": rasa.__version__}])
def test_model_is_compatible(metadata):
    # should not raise an exception
    assert Interpreter.ensure_model_compatibility(metadata) is None


@pytest.mark.parametrize(
    "parameters",
    [
        {
            "obj": "not-existing",
            "endpoint": EndpointConfig(url="http://localhost:8080/"),
            "type": RasaNLUHttpInterpreter,
        },
        {
            "obj": "trained_nlu_model",
            "endpoint": EndpointConfig(url="http://localhost:8080/"),
            "type": RasaNLUHttpInterpreter,
        },
        {"obj": "trained_nlu_model", "endpoint": None, "type": RasaNLUInterpreter},
        {"obj": "not-existing", "endpoint": None, "type": RegexInterpreter},
        {"obj": ["list-object"], "endpoint": None, "type": RegexInterpreter},
    ],
)
def test_create_interpreter(parameters, trained_nlu_model):
    obj = parameters["obj"]
    if obj == "trained_nlu_model":
        _, obj = get_model_subdirectories(get_model(trained_nlu_model))

    interpreter = NaturalLanguageInterpreter.create(obj, parameters["endpoint"])

    assert isinstance(interpreter, parameters["type"])
