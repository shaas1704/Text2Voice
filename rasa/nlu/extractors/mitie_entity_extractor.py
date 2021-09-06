from __future__ import annotations
import logging
import os
import typing
from typing import Any, Dict, List, Text

from rasa.engine.graph import GraphComponent, ModelStorage, ExecutionContext
from rasa.engine.storage.resource import Resource
from rasa.nlu.constants import TOKENS_NAMES
from rasa.shared.nlu.constants import TEXT, ENTITIES
from rasa.nlu.utils.mitie_utils import MitieModel
from rasa.nlu.extractors.extractor import EntityExtractorMixin
from rasa.shared.nlu.training_data.training_data import TrainingData
from rasa.shared.nlu.training_data.message import Message
import rasa.shared.utils.io
from rasa.nlu.extractors._mitie_entity_extractor import MitieEntityExtractor
from rasa.shared.exceptions import InvalidConfigException

logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    import mitie

# TODO: remove when everything has been migrated
MitieEntityExtractor = MitieEntityExtractor


class MitieEntityExtractorGraphComponent(GraphComponent, EntityExtractorMixin):
    """A Mitie Entity Extractor (which is a thin wrapper around `Dlib-ml`)."""

    MITIE_RESOURCE_FILE = "mitie_ner.dat"

    @staticmethod
    def required_packages() -> List[Text]:
        """Any extra python dependencies required for this component to run."""
        return ["mitie"]

    @staticmethod
    def get_default_config() -> Dict[Text, Any]:
        """The component's default config (see parent class for full docstring)."""
        return {
            "mitie_file": None,
            "num_threads": 1,
        }

    def __init__(
        self,
        config: Dict[Text, Any],
        model_storage: ModelStorage,
        resource: Resource,
        execution_context: ExecutionContext,
    ) -> None:
        """Creates a new instance.

        Args:
            config: The configuration.
            model_storage: Storage which graph components can use to persist and load
                themselves.
            resource: Resource locator for this component which can be used to persist
                and load itself from the `model_storage`.
            execution_context: Information about the current graph run. Unused.
        """
        # graph component
        self._config = {**self.get_default_config(), **config}
        self._model_storage = model_storage
        self._resource = resource
        self.validate_config(self._config)
        # extractor
        self._ner = None

    def validate_config(cls, config: Dict[Text, Any]) -> None:
        """Checks whether the given configuration is valid."""
        model_file = config.get("mitie_file")
        if not model_file or not os.path.isfile(model_file):
            raise InvalidConfigException(
                f"Can not run MITIE entity extractor without a language model. "
                f"Expected configuration `mitie_file` to be an absolute path to a "
                f"mitie language model, but received {model_file} (which does not "
                f"exist or does not point to a file)."
            )
        num_threads = config.get("num_threads")
        if num_threads is not None or num_threads <= 0:
            raise InvalidConfigException(
                f"Expected `num_threads` to be some value >= 1 (default: 1)."
                f"but received {num_threads}"
            )

    @classmethod
    def create(
        cls,
        config: Dict[Text, Any],
        model_storage: ModelStorage,
        resource: Resource,
        execution_context: ExecutionContext,
    ) -> GraphComponent:
        """Creates a new `MitieEntityExtractorGraphComponent`.

        Args:
            config: This config overrides the `default_config`.
            model_storage: Storage which graph components can use to persist and load
                themselves.
            resource: Resource locator for this component which can be used to persist
                and load itself from the `model_storage`.
            execution_context: Information about the current graph run.

        Returns: An instantiated `MitieEntityExtractorGraphComponent`.
        """
        return cls(config, model_storage, resource, execution_context)

    def _load(self, ner: "mitie.named_entity_extractor") -> None:
        """Sets all attributes that can be persisted, i.e the mitie entity extractor.

        Args:
           ner: a mitie entity extractor
        """
        self._ner = ner

    def train(self, training_data: TrainingData,) -> Resource:
        """Trains a MITIE named entity recognizer.

        Args:
            training_data: the training data
        Returns:
            resource for loading the trained model
        """
        import mitie

        # FIXME: why don't we need the MitieModel during train (but during process)?

        trainer = mitie.ner_trainer(self._config["mitie_file"])
        trainer.num_threads = int(self._config.get("num_threads", 1))

        # check whether there are any (not pre-trained) entities in the training data
        found_one_entity = False

        # filter out pre-trained entity examples
        filtered_entity_examples = self.filter_trainable_entities(
            training_data.nlu_examples
        )

        for example in filtered_entity_examples:
            sample = self._prepare_mitie_sample(example)

            found_one_entity = sample.num_entities > 0 or found_one_entity
            trainer.add(sample)

        # Mitie will fail to train if there is not a single entity tagged
        if found_one_entity:
            self.ner = trainer.train()

        self.persist()
        return self._resource

    @staticmethod
    def _prepare_mitie_sample(training_example: Message) -> Any:
        """Prepare a message so that it can be passed to a MITIE trainer."""
        import mitie

        text = training_example.get(TEXT)
        tokens = training_example.get(TOKENS_NAMES[TEXT])
        sample = mitie.ner_training_instance([t.text for t in tokens])
        for ent in training_example.get(ENTITIES, []):
            try:
                # if the token is not aligned an exception will be raised
                start, end = MitieEntityExtractor.find_entity(ent, text, tokens)
            except ValueError as e:
                rasa.shared.utils.io.raise_warning(
                    f"Failed to use example '{text}' to train MITIE "
                    f"entity extractor. Example will be skipped."
                    f"Error: {e}"
                )
                continue
            try:
                # mitie will raise an exception on malicious
                # input - e.g. on overlapping entities
                sample.add_entity(list(range(start, end)), ent["entity"])
            except Exception as e:
                rasa.shared.utils.io.raise_warning(
                    f"Failed to add entity example "
                    f"'{str(e)}' of sentence '{str(text)}'. "
                    f"Example will be ignored. Reason: "
                    f"{e}"
                )
                continue
        return sample

    def process(
        self, messages: List[Message], mitie_model: MitieModel
    ) -> List[Message]:
        """Extracts entities from messages and appends them to the attribute.

        If no patterns where found during training, then the given messages will not
        be modified. In particular, if no `ENTITIES` attribute exists yet, then
        it will *not* be created.

        If no pattern can be found in the given message, then no entities will be
        added to any existing list of entities. However, if no `ENTITIES` attribute
        exists yet, then an `ENTITIES` attribute will be created.

        Returns:
           the given list of messages that have been modified
        """
        if not self._ner:
            return messages

        for message in messages:
            entities = self._extract_entities(message, mitie_model)
            extracted = self.add_extractor_name(entities)
            message.set(
                ENTITIES, message.get(ENTITIES, []) + extracted, add_to_output=True
            )
        return messages

    def _extract_entities(
        self, message: Message, mitie_model: MitieModel,
    ) -> List[Dict[Text, Any]]:
        """Extract entities of the given type from the given user message.

        Args:
            message: a user message
            mitie_model: MitieModel containing a `mitie.total_word_feature_extractor`

        Returns:
            a list of dictionaries describing the entities
        """
        text = message.get(TEXT)
        tokens = message.get(TOKENS_NAMES[TEXT])

        entities = []
        token_texts = [token.text for token in tokens]
        entities = self._ner.extract_entities(
            token_texts, mitie_model.word_feature_extractor
        )
        for e in entities:
            if len(e[0]):
                start = tokens[e[0][0]].start
                end = tokens[e[0][-1]].end

                entities.append(
                    {
                        "entity": e[1],
                        "value": text[start:end],
                        "start": start,
                        "end": end,
                        "confidence": None,
                    }
                )
        return entities

    @classmethod
    def load(
        cls,
        config: Dict[Text, Any],
        model_storage: ModelStorage,
        resource: Resource,
        execution_context: ExecutionContext,
        **kwargs: Any,
    ) -> MitieEntityExtractorGraphComponent:
        """Loads trained component (see parent class for full docstring)."""
        import mitie

        graph_component = MitieEntityExtractorGraphComponent(
            config, model_storage, resource, execution_context
        )
        try:
            with model_storage.write_to(resource) as model_path:
                ner_file = model_path / cls.MITIE_RESOURCE_FILE
                if not os.path.isfile(ner_file):
                    raise FileNotFoundError(
                        f"Expected a MITIE extractor file at {ner_file}."
                    )
                ner = mitie.named_entity_extractor(ner_file)
                graph_component._load(ner)
        except FileNotFoundError:
            rasa.shared.utils.io.raise_warning(
                f"Failed to load {cls.__name__} from model storage. "
                f"This can happen if the model could not be trained because regexes "
                f"could not be extracted from the given training data - and hence "
                f"could not be persisted."
            )
        return graph_component

    def persist(self) -> None:
        """Persist this model."""
        if not self.ner:
            return
        with self._model_storage.write_to(self._resource) as model_path:
            ner_file = model_path / self.MITIE_RESOURCE_FILE
            self.ner.save_to_disk(ner_file, pure_model=True)
