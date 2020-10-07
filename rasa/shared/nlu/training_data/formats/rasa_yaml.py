import logging
from collections import OrderedDict
from pathlib import Path
from typing import Text, Any, List, Dict, Tuple, Union, Iterator, Optional

import rasa.shared.data
from rasa.shared.exceptions import RasaException, YamlException, YamlSyntaxException
from rasa.shared.utils import validation
from ruamel.yaml import YAMLError, StringIO

from rasa.shared.constants import (
    DOCS_URL_TRAINING_DATA,
    LATEST_TRAINING_DATA_FORMAT_VERSION,
)
from rasa.shared.nlu.training_data.formats.readerwriter import (
    TrainingDataReader,
    TrainingDataWriter,
)
import rasa.shared.utils.io

from rasa.shared.nlu.training_data.training_data import TrainingData
from rasa.shared.nlu.training_data.message import Message

logger = logging.getLogger(__name__)

KEY_NLU = "nlu"
KEY_RESPONSES = "responses"
KEY_INTENT = "intent"
KEY_INTENT_EXAMPLES = "examples"
KEY_INTENT_TEXT = "text"
KEY_SYNONYM = "synonym"
KEY_SYNONYM_EXAMPLES = "examples"
KEY_REGEX = "regex"
KEY_REGEX_EXAMPLES = "examples"
KEY_LOOKUP = "lookup"
KEY_LOOKUP_EXAMPLES = "examples"
KEY_METADATA = "metadata"

MULTILINE_TRAINING_EXAMPLE_LEADING_SYMBOL = "-"

NLU_SCHEMA_FILE = "shared/nlu/training_data/schemas/nlu.yml"

STRIP_SYMBOLS = "\n\r "


class RasaYAMLReader(TrainingDataReader):
    """Reads YAML training data and creates a TrainingData object."""

    def __init__(self) -> None:
        super().__init__()
        self.training_examples: List[Message] = []
        self.entity_synonyms: Dict[Text, Text] = {}
        self.regex_features: List[Dict[Text, Text]] = []
        self.lookup_tables: List[Dict[Text, Any]] = []
        self.responses: Dict[Text, List[Dict[Text, Any]]] = {}

    def validate(self, string: Text) -> None:
        """Check if the string adheres to the NLU yaml data schema.

        If the string is not in the right format, an exception will be raised."""
        try:
            validation.validate_yaml_schema(string, NLU_SCHEMA_FILE)
        except YamlException as e:
            e.filename = self.filename
            raise e

    def reads(self, string: Text, **kwargs: Any) -> "TrainingData":
        """Reads TrainingData in YAML format from a string.

        Args:
            string: String with YAML training data.
            **kwargs: Keyword arguments.

        Returns:
            New `TrainingData` object with parsed training data.
        """
        self.validate(string)

        # TODO
        yaml_content = rasa.shared.utils.io.read_yaml(string)

        if not validation.validate_training_data_format_version(
            yaml_content, self.filename
        ):
            return TrainingData()

        for key, value in yaml_content.items():  # pytype: disable=attribute-error
            if key == KEY_NLU:
                self._parse_nlu(value)
            elif key == KEY_RESPONSES:
                self.responses = value

        return TrainingData(
            self.training_examples,
            self.entity_synonyms,
            self.regex_features,
            self.lookup_tables,
            self.responses,
        )

    def _parse_nlu(self, nlu_data: Optional[List[Dict[Text, Any]]]) -> None:

        if not nlu_data:
            return

        for nlu_item in nlu_data:
            if not isinstance(nlu_item, dict):
                rasa.shared.utils.io.raise_warning(
                    f"Unexpected block found in '{self.filename}':\n"
                    f"{nlu_item}\n"
                    f"Items under the '{KEY_NLU}' key must be YAML dictionaries. "
                    f"This block will be skipped.",
                    docs=DOCS_URL_TRAINING_DATA,
                )
                continue

            if KEY_INTENT in nlu_item.keys():
                self._parse_intent(nlu_item)
            elif KEY_SYNONYM in nlu_item.keys():
                self._parse_synonym(nlu_item)
            elif KEY_REGEX in nlu_item.keys():
                self._parse_regex(nlu_item)
            elif KEY_LOOKUP in nlu_item.keys():
                self._parse_lookup(nlu_item)
            else:
                rasa.shared.utils.io.raise_warning(
                    f"Issue found while processing '{self.filename}': "
                    f"Could not find supported key in the section:\n"
                    f"{nlu_item}\n"
                    f"Supported keys are: '{KEY_INTENT}', '{KEY_SYNONYM}', "
                    f"'{KEY_REGEX}', '{KEY_LOOKUP}'. "
                    f"This section will be skipped.",
                    docs=DOCS_URL_TRAINING_DATA,
                )

    def _parse_intent(self, intent_data: Dict[Text, Any]) -> None:
        import rasa.shared.nlu.training_data.entities_parser as entities_parser
        import rasa.shared.nlu.training_data.synonyms_parser as synonyms_parser

        intent = intent_data.get(KEY_INTENT, "")
        if not intent:
            rasa.shared.utils.io.raise_warning(
                f"Issue found while processing '{self.filename}': "
                f"The intent has an empty name. "
                f"Intents should have a name defined under the {KEY_INTENT} key. "
                f"It will be skipped.",
                docs=DOCS_URL_TRAINING_DATA,
            )
            return

        examples = intent_data.get(KEY_INTENT_EXAMPLES, "")
        intent_metadata = intent_data.get(KEY_METADATA)
        for example, entities, metadata in self._parse_training_examples(
            examples, intent
        ):

            plain_text = entities_parser.replace_entities(example)

            synonyms_parser.add_synonyms_from_entities(
                plain_text, entities, self.entity_synonyms
            )

            self.training_examples.append(
                Message.build(plain_text, intent, entities, intent_metadata, metadata)
            )

    def _parse_training_examples(
        self, examples: Union[Text, List[Dict[Text, Any]]], intent: Text
    ) -> List[Tuple[Text, List[Dict[Text, Any]], Optional[Any]]]:
        import rasa.shared.nlu.training_data.entities_parser as entities_parser

        if isinstance(examples, list):
            example_tuples = [
                (
                    # pytype: disable=attribute-error
                    example.get(KEY_INTENT_TEXT, "").strip(STRIP_SYMBOLS),
                    example.get(KEY_METADATA),
                )
                for example in examples
                if example
            ]
        # pytype: enable=attribute-error
        elif isinstance(examples, str):
            example_tuples = [
                (example, None)
                for example in self._parse_multiline_example(intent, examples)
            ]
        else:
            rasa.shared.utils.io.raise_warning(
                f"Unexpected block found in '{self.filename}' "
                f"while processing intent '{intent}':\n"
                f"{examples}\n"
                f"This block will be skipped.",
                docs=DOCS_URL_TRAINING_DATA,
            )
            return []

        if not example_tuples:
            rasa.shared.utils.io.raise_warning(
                f"Issue found while processing '{self.filename}': "
                f"Intent '{intent}' has no examples.",
                docs=DOCS_URL_TRAINING_DATA,
            )

        results = []
        for example, metadata in example_tuples:
            entities = entities_parser.find_entities_in_training_example(example)
            results.append((example, entities, metadata))

        return results

    def _parse_synonym(self, nlu_item: Dict[Text, Any]) -> None:
        import rasa.shared.nlu.training_data.synonyms_parser as synonyms_parser

        synonym_name = nlu_item[KEY_SYNONYM]
        if not synonym_name:
            rasa.shared.utils.io.raise_warning(
                f"Issue found while processing '{self.filename}': "
                f"The synonym has an empty name. "
                f"Synonyms should have a name defined under the {KEY_SYNONYM} key. "
                f"It will be skipped.",
                docs=DOCS_URL_TRAINING_DATA,
            )
            return

        examples = nlu_item.get(KEY_SYNONYM_EXAMPLES, "")

        if not examples:
            rasa.shared.utils.io.raise_warning(
                f"Issue found while processing '{self.filename}': "
                f"{KEY_SYNONYM}: {synonym_name} doesn't have any examples. "
                f"It will be skipped.",
                docs=DOCS_URL_TRAINING_DATA,
            )
            return

        if not isinstance(examples, str):
            rasa.shared.utils.io.raise_warning(
                f"Unexpected block found in '{self.filename}':\n"
                f"{examples}\n"
                f"It will be skipped.",
                docs=DOCS_URL_TRAINING_DATA,
            )
            return

        for example in self._parse_multiline_example(synonym_name, examples):
            synonyms_parser.add_synonym(example, synonym_name, self.entity_synonyms)

    def _parse_regex(self, nlu_item: Dict[Text, Any]) -> None:
        regex_name = nlu_item[KEY_REGEX]
        if not regex_name:
            rasa.shared.utils.io.raise_warning(
                f"Issue found while processing '{self.filename}': "
                f"The regex has an empty name."
                f"Regex should have a name defined under the '{KEY_REGEX}' key. "
                f"It will be skipped.",
                docs=DOCS_URL_TRAINING_DATA,
            )
            return

        examples = nlu_item.get(KEY_REGEX_EXAMPLES, "")
        if not examples:
            rasa.shared.utils.io.raise_warning(
                f"Issue found while processing '{self.filename}': "
                f"'{KEY_REGEX}: {regex_name}' doesn't have any examples. "
                f"It will be skipped.",
                docs=DOCS_URL_TRAINING_DATA,
            )
            return

        if not isinstance(examples, str):
            rasa.shared.utils.io.raise_warning(
                f"Unexpected block found in '{self.filename}':\n"
                f"{examples}\n"
                f"This block will be skipped.",
                docs=DOCS_URL_TRAINING_DATA,
            )
            return

        for example in self._parse_multiline_example(regex_name, examples):
            self.regex_features.append({"name": regex_name, "pattern": example})

    def _parse_lookup(self, nlu_item: Dict[Text, Any]):
        import rasa.shared.nlu.training_data.lookup_tables_parser as lookup_tables_parser

        lookup_item_name = nlu_item[KEY_LOOKUP]
        if not lookup_item_name:
            rasa.shared.utils.io.raise_warning(
                f"Issue found while processing '{self.filename}': "
                f"The lookup item has an empty name. "
                f"Lookup items should have a name defined under the '{KEY_LOOKUP}' "
                f"key. It will be skipped.",
                docs=DOCS_URL_TRAINING_DATA,
            )
            return

        examples = nlu_item.get(KEY_LOOKUP_EXAMPLES, "")
        if not examples:
            rasa.shared.utils.io.raise_warning(
                f"Issue found while processing '{self.filename}': "
                f"'{KEY_LOOKUP}: {lookup_item_name}' doesn't have any examples. "
                f"It will be skipped.",
                docs=DOCS_URL_TRAINING_DATA,
            )
            return

        if not isinstance(examples, str):
            rasa.shared.utils.io.raise_warning(
                f"Unexpected block found in '{self.filename}':\n"
                f"{examples}\n"
                f"This block will be skipped.",
                docs=DOCS_URL_TRAINING_DATA,
            )
            return

        for example in self._parse_multiline_example(lookup_item_name, examples):
            lookup_tables_parser.add_item_to_lookup_tables(
                lookup_item_name, example, self.lookup_tables
            )

    def _parse_multiline_example(self, item: Text, examples: Text) -> Iterator[Text]:
        for example in examples.splitlines():
            if not example.startswith(MULTILINE_TRAINING_EXAMPLE_LEADING_SYMBOL):
                rasa.shared.utils.io.raise_warning(
                    f"Issue found while processing '{self.filename}': "
                    f"The item '{item}' contains an example that doesn't start with a "
                    f"'{MULTILINE_TRAINING_EXAMPLE_LEADING_SYMBOL}' symbol: "
                    f"{example}\n"
                    f"This training example will be skipped.",
                    docs=DOCS_URL_TRAINING_DATA,
                )
                continue
            yield example[1:].strip(STRIP_SYMBOLS)

    @staticmethod
    def is_yaml_nlu_file(filename: Text) -> bool:
        """Checks if the specified file possibly contains NLU training data in YAML.

        Args:
            filename: name of the file to check.

        Returns:
            `True` if the `filename` is possibly a valid YAML NLU file,
            `False` otherwise.
        """
        if not rasa.shared.data.is_likely_yaml_file(filename):
            return False

        content = rasa.shared.utils.io.read_yaml_file(filename)

        return any(key in content for key in {KEY_NLU, KEY_RESPONSES})


class RasaYAMLWriter(TrainingDataWriter):
    """Writes training data into a file in a YAML format."""

    def dumps(self, training_data: "TrainingData") -> Text:
        """Turns TrainingData into a string."""
        stream = StringIO()
        self.dump(stream, training_data)
        return stream.getvalue()

    def dump(
        self, target: Union[Text, Path, StringIO], training_data: "TrainingData"
    ) -> None:
        """Writes training data into a file in a YAML format.

        Args:
            target: Name of the target object to write the YAML to.
            training_data: TrainingData object.
        """
        result = self.training_data_to_dict(training_data)

        if result:
            rasa.shared.utils.io.write_yaml(result, target, True)

    @classmethod
    def training_data_to_dict(
        cls, training_data: "TrainingData"
    ) -> Optional[OrderedDict]:
        """Represents NLU training data to a dict/list structure ready to be
        serialized as YAML.

        Args:
            training_data: `TrainingData` to convert.

        Returns:
            `OrderedDict` containing all training data.
        """
        from rasa.shared.utils.validation import KEY_TRAINING_DATA_FORMAT_VERSION
        from ruamel.yaml.scalarstring import DoubleQuotedScalarString

        nlu_items = []
        nlu_items.extend(cls.process_intents(training_data))
        nlu_items.extend(cls.process_synonyms(training_data))
        nlu_items.extend(cls.process_regexes(training_data))
        nlu_items.extend(cls.process_lookup_tables(training_data))

        if not any([nlu_items, training_data.responses]):
            return None

        result = OrderedDict()
        result[KEY_TRAINING_DATA_FORMAT_VERSION] = DoubleQuotedScalarString(
            LATEST_TRAINING_DATA_FORMAT_VERSION
        )

        if nlu_items:
            result[KEY_NLU] = nlu_items

        if training_data.responses:
            result[KEY_RESPONSES] = training_data.responses

        return result

    @classmethod
    def process_intents(cls, training_data: "TrainingData") -> List[OrderedDict]:
        training_data = cls.prepare_training_examples(training_data)
        return RasaYAMLWriter.process_training_examples_by_key(
            training_data,
            KEY_INTENT,
            KEY_INTENT_EXAMPLES,
            TrainingDataWriter.generate_message,
        )

    @classmethod
    def process_synonyms(cls, training_data: "TrainingData") -> List[OrderedDict]:
        inverted_synonyms = OrderedDict()
        for example, synonym in training_data.entity_synonyms.items():
            if not inverted_synonyms.get(synonym):
                inverted_synonyms[synonym] = []
            inverted_synonyms[synonym].append(example)

        return cls.process_training_examples_by_key(
            inverted_synonyms, KEY_SYNONYM, KEY_SYNONYM_EXAMPLES
        )

    @classmethod
    def process_regexes(cls, training_data: "TrainingData") -> List[OrderedDict]:
        inverted_regexes = OrderedDict()
        for regex in training_data.regex_features:
            if not inverted_regexes.get(regex["name"]):
                inverted_regexes[regex["name"]] = []
            inverted_regexes[regex["name"]].append(regex["pattern"])

        return cls.process_training_examples_by_key(
            inverted_regexes, KEY_REGEX, KEY_REGEX_EXAMPLES
        )

    @classmethod
    def process_lookup_tables(cls, training_data: "TrainingData") -> List[OrderedDict]:
        prepared_lookup_tables = OrderedDict()
        for lookup_table in training_data.lookup_tables:
            # this is a lookup table filename
            if isinstance(lookup_table["elements"], str):
                continue
            prepared_lookup_tables[lookup_table["name"]] = lookup_table["elements"]

        return cls.process_training_examples_by_key(
            prepared_lookup_tables, KEY_LOOKUP, KEY_LOOKUP_EXAMPLES
        )

    @staticmethod
    def process_training_examples_by_key(
        training_examples: Dict,
        key_name: Text,
        key_examples: Text,
        example_extraction_predicate=lambda x: x,
    ) -> List[OrderedDict]:
        from ruamel.yaml.scalarstring import LiteralScalarString

        result = []
        for entity_key, examples in training_examples.items():

            converted_examples = [
                TrainingDataWriter.generate_list_item(
                    example_extraction_predicate(example).strip(STRIP_SYMBOLS)
                )
                for example in examples
            ]

            next_item = OrderedDict()
            next_item[key_name] = entity_key
            next_item[key_examples] = LiteralScalarString("".join(converted_examples))
            result.append(next_item)

        return result
