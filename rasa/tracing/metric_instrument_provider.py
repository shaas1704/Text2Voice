from typing import ClassVar, Dict, Any

from opentelemetry.metrics import get_meter_provider
from opentelemetry.sdk.metrics import Meter

from rasa.utils.singleton import Singleton
from rasa.tracing.constants import (
    LLM_COMMAND_GENERATOR_CPU_USAGE_INSTRUMENT_NAME,
    LLM_COMMAND_GENERATOR_MEMORY_USAGE_INSTRUMENT_NAME,
    LLM_COMMAND_GENERATOR_PROMPT_TOKEN_USAGE_INSTRUMENT_NAME,
    LLM_COMMAND_GENERATOR_LLM_RESPONSE_DURATION_INSTRUMENT_NAME,
    ENTERPRISE_SEARCH_POLICY_LLM_RESPONSE_DURATION_INSTRUMENT_NAME,
    INTENTLESS_POLICY_LLM_RESPONSE_DURATION_INSTRUMENT_NAME,
    CONTEXTUAL_RESPONSE_REPHRASER_LLM_RESPONSE_DURATION_INSTRUMENT_NAME,
    RASA_CLIENT_REQUEST_DURATION_INSTRUMENT_NAME,
    RASA_CLIENT_REQUEST_BODY_SIZE_INSTRUMENT_NAME,
)


class MetricInstrumentProvider(metaclass=Singleton):
    """Singleton provider class of metric instruments."""

    instruments: ClassVar[Dict[str, Any]] = {}

    def register_instruments(self) -> None:
        """Update instruments class attribute.

        The registered instruments are subclasses of the
        opentelemetry.metrics._internal.instrument.Instrument interface.
        """
        meter = get_meter_provider().get_meter(__name__)

        instruments = {
            **self._create_llm_command_generator_instruments(meter),
            **self._create_llm_response_duration_instruments(meter),
            **self._create_client_request_instruments(meter),
        }

        self.instruments.update(instruments)

    def get_instrument(self, name: str) -> Any:
        """Get the instrument mapped to the provided name."""
        return self.instruments.get(name)

    @staticmethod
    def _create_llm_command_generator_instruments(meter: Meter) -> Dict[str, Any]:
        llm_command_generator_cpu_usage = meter.create_histogram(
            name=LLM_COMMAND_GENERATOR_CPU_USAGE_INSTRUMENT_NAME,
            description="CPU percentage for LLMCommandGenerator",
            unit="%",
        )

        llm_command_generator_memory_usage = meter.create_histogram(
            name=LLM_COMMAND_GENERATOR_MEMORY_USAGE_INSTRUMENT_NAME,
            description="RAM memory usage for LLMCommandGenerator",
            unit="%",
        )

        llm_command_generator_prompt_token_usage = meter.create_histogram(
            name=LLM_COMMAND_GENERATOR_PROMPT_TOKEN_USAGE_INSTRUMENT_NAME,
            description="LLMCommandGenerator prompt token length",
            unit="1",
        )

        llm_response_duration_llm_command_generator = meter.create_histogram(
            name=LLM_COMMAND_GENERATOR_LLM_RESPONSE_DURATION_INSTRUMENT_NAME,
            description="The duration of LLMCommandGenerator's LLM call",
            unit="ms",
        )

        return {
            LLM_COMMAND_GENERATOR_CPU_USAGE_INSTRUMENT_NAME: llm_command_generator_cpu_usage,  # noqa: E501
            LLM_COMMAND_GENERATOR_MEMORY_USAGE_INSTRUMENT_NAME: llm_command_generator_memory_usage,  # noqa: E501
            LLM_COMMAND_GENERATOR_PROMPT_TOKEN_USAGE_INSTRUMENT_NAME: llm_command_generator_prompt_token_usage,  # noqa: E501
            LLM_COMMAND_GENERATOR_LLM_RESPONSE_DURATION_INSTRUMENT_NAME: llm_response_duration_llm_command_generator,  # noqa: E501
        }

    @staticmethod
    def _create_llm_response_duration_instruments(meter: Meter) -> Dict[str, Any]:
        llm_response_duration_enterprise_search = meter.create_histogram(
            name=ENTERPRISE_SEARCH_POLICY_LLM_RESPONSE_DURATION_INSTRUMENT_NAME,
            description="The duration of EnterpriseSearchPolicy's LLM call",
            unit="ms",
        )

        llm_response_duration_intentless = meter.create_histogram(
            name=INTENTLESS_POLICY_LLM_RESPONSE_DURATION_INSTRUMENT_NAME,
            description="The duration of IntentlessPolicy's LLM call",
            unit="ms",
        )

        llm_response_duration_contextual_nlg = meter.create_histogram(
            name=CONTEXTUAL_RESPONSE_REPHRASER_LLM_RESPONSE_DURATION_INSTRUMENT_NAME,
            description="The duration of ContextualResponseRephraser's LLM call",
            unit="ms",
        )

        return {
            ENTERPRISE_SEARCH_POLICY_LLM_RESPONSE_DURATION_INSTRUMENT_NAME: llm_response_duration_enterprise_search,  # noqa: E501
            INTENTLESS_POLICY_LLM_RESPONSE_DURATION_INSTRUMENT_NAME: llm_response_duration_intentless,  # noqa: E501
            CONTEXTUAL_RESPONSE_REPHRASER_LLM_RESPONSE_DURATION_INSTRUMENT_NAME: llm_response_duration_contextual_nlg,  # noqa: E501
        }

    @staticmethod
    def _create_client_request_instruments(
        meter: Meter,
    ) -> Dict[str, Any]:
        client_request_duration = meter.create_histogram(
            name=RASA_CLIENT_REQUEST_DURATION_INSTRUMENT_NAME,
            description="The duration of the rasa client request",
            unit="ms",
        )

        client_request_body_size = meter.create_histogram(
            name=RASA_CLIENT_REQUEST_BODY_SIZE_INSTRUMENT_NAME,
            description="The rasa client request's body size",
            unit="byte",
        )

        return {
            RASA_CLIENT_REQUEST_DURATION_INSTRUMENT_NAME: client_request_duration,
            RASA_CLIENT_REQUEST_BODY_SIZE_INSTRUMENT_NAME: client_request_body_size,
        }