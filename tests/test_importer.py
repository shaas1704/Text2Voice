import os
from pathlib import Path
from typing import Text, Dict, Type, List

import pytest
from rasa.constants import DEFAULT_CONFIG_PATH, DEFAULT_DOMAIN_PATH, DEFAULT_DATA_PATH
from rasa.core.domain import Domain
from rasa.importers.importer import (
    CombinedDataImporter,
    TrainingDataImporter,
    NluDataImporter,
    CoreDataImporter,
)
from rasa.importers.basic import RasaFileImporter

# noinspection PyUnresolvedReferences
from rasa.importers.skill import SkillSelector

# noinspection PyUnresolvedReferences
from tests.core.conftest import project


async def test_use_of_interface():
    importer = TrainingDataImporter()

    functions_to_test = [
        lambda: importer.get_config(),
        lambda: importer.get_stories(),
        lambda: importer.get_nlu_data(),
        lambda: importer.get_domain(),
    ]
    for f in functions_to_test:
        with pytest.raises(NotImplementedError):
            await f()


async def test_simple_file_importer(project: Text):
    config_path = os.path.join(project, DEFAULT_CONFIG_PATH)
    domain_path = os.path.join(project, DEFAULT_DOMAIN_PATH)
    default_data_path = os.path.join(project, DEFAULT_DATA_PATH)

    importer = RasaFileImporter(config_path, domain_path, [default_data_path])

    domain = await importer.get_domain()
    assert len(domain.intents) == 6
    assert domain.slots == []
    assert domain.entities == []
    assert len(domain.action_names) == 13
    assert len(domain.templates) == 5

    stories = await importer.get_stories()
    assert len(stories.story_steps) == 4

    nlu_data = await importer.get_nlu_data("en")
    assert len(nlu_data.intents) == 6
    assert len(nlu_data.intent_examples) == 39


async def test_simple_file_importer_with_invalid_config():
    importer = RasaFileImporter(config_file="invalid path")
    actual = await importer.get_config()

    assert actual == {}


async def test_simple_file_importer_with_invalid_domain(tmp_path: Path):
    config_file = tmp_path / "config.yml"
    config_file.write_text("")
    importer = TrainingDataImporter.load_from_dict({}, str(config_file), None, [])

    actual = await importer.get_domain()
    assert actual.as_dict() == Domain.empty().as_dict()


async def test_combined_file_importer_with_single_importer(project: Text):
    config_path = os.path.join(project, DEFAULT_CONFIG_PATH)
    domain_path = os.path.join(project, DEFAULT_DOMAIN_PATH)
    default_data_path = os.path.join(project, DEFAULT_DATA_PATH)

    importer = RasaFileImporter(config_path, domain_path, [default_data_path])
    combined = CombinedDataImporter([importer])

    assert await importer.get_config() == await combined.get_config()
    assert (await importer.get_domain()).as_dict() == (
        await combined.get_domain()
    ).as_dict()
    assert (await importer.get_nlu_data()).as_json() == (
        await combined.get_nlu_data()
    ).as_json()

    expected_stories = await importer.get_stories()
    actual_stories = await combined.get_stories()

    assert actual_stories.as_story_string() == expected_stories.as_story_string()


@pytest.mark.parametrize(
    "config, expected",
    [
        ({}, [RasaFileImporter]),
        ({"importers": []}, [RasaFileImporter]),
        ({"importers": [{"name": "RasaFileImporter"}]}, [RasaFileImporter]),
        ({"importers": [{"name": "NotExistingModule"}]}, [RasaFileImporter]),
        (
            {"importers": [{"name": "rasa.importers.skill.SkillSelector"}]},
            [SkillSelector],
        ),
        ({"importers": [{"name": "SkillSelector"}]}, [SkillSelector]),
        (
            {"importers": [{"name": "RasaFileImporter"}, {"name": "SkillSelector"}]},
            [RasaFileImporter, SkillSelector],
        ),
    ],
)
def test_load_from_dict(
    config: Dict, expected: List[Type["TrainingDataImporter"]], project: Text
):
    config_path = os.path.join(project, DEFAULT_CONFIG_PATH)
    domain_path = os.path.join(project, DEFAULT_DOMAIN_PATH)
    default_data_path = os.path.join(project, DEFAULT_DATA_PATH)
    actual = TrainingDataImporter.load_from_dict(
        config, config_path, domain_path, [default_data_path]
    )

    assert isinstance(actual, CombinedDataImporter)

    actual_importers = [i.__class__ for i in actual._importers]
    assert actual_importers == expected


def test_load_from_config(tmpdir: Path):
    import rasa.utils.io as io_utils

    config_path = str(tmpdir / "config.yml")

    io_utils.write_yaml_file({"importers": [{"name": "SkillSelector"}]}, config_path)

    importer = TrainingDataImporter.load_from_config(config_path)
    assert isinstance(importer, CombinedDataImporter)
    assert isinstance(importer._importers[0], SkillSelector)


async def test_nlu_only(project: Text):
    config_path = os.path.join(project, DEFAULT_CONFIG_PATH)
    default_data_path = os.path.join(project, DEFAULT_DATA_PATH)
    actual = TrainingDataImporter.load_nlu_importer_from_config(
        config_path, training_data_paths=[default_data_path]
    )

    assert isinstance(actual, NluDataImporter)

    stories = await actual.get_stories()
    assert stories.is_empty()

    domain = await actual.get_domain()
    assert domain.is_empty()

    config = await actual.get_config()
    assert config

    nlu_data = await actual.get_nlu_data()
    assert not nlu_data.is_empty()


async def test_core_only(project: Text):
    config_path = os.path.join(project, DEFAULT_CONFIG_PATH)
    domain_path = os.path.join(project, DEFAULT_DOMAIN_PATH)
    default_data_path = os.path.join(project, DEFAULT_DATA_PATH)
    actual = TrainingDataImporter.load_core_importer_from_config(
        config_path, domain_path, training_data_paths=[default_data_path]
    )

    assert isinstance(actual, CoreDataImporter)

    stories = await actual.get_stories()
    assert not stories.is_empty()

    domain = await actual.get_domain()
    assert not domain.is_empty()

    config = await actual.get_config()
    assert config

    nlu_data = await actual.get_nlu_data()
    assert nlu_data.is_empty()
