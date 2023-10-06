from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict
from rasa.shared.constants import RASA_DEFAULT_FLOW_PATTERN_PREFIX
from rasa.dialogue_understanding.stack.frames import PatternFlowStackFrame


FLOW_PATTERN_SEARCH = RASA_DEFAULT_FLOW_PATTERN_PREFIX + "search"


@dataclass
class SearchPatternFlowStackFrame(PatternFlowStackFrame):
    """A pattern flow stack frame that gets added if an interruption is completed."""

    flow_id: str = FLOW_PATTERN_SEARCH
    """The ID of the flow."""

    @classmethod
    def type(cls) -> str:
        """Returns the type of the frame."""
        return FLOW_PATTERN_SEARCH

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> SearchPatternFlowStackFrame:
        """Creates a `DialogueStackFrame` from a dictionary.

        Args:
            data: The dictionary to create the `DialogueStackFrame` from.

        Returns:
            The created `DialogueStackFrame`.
        """
        return SearchPatternFlowStackFrame(
            frame_id=data["frame_id"],
            step_id=data["step_id"],
        )
