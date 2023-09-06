from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List
from rasa.cdu.stack.dialogue_stack import DialogueStackFrame
from rasa.shared.constants import RASA_DEFAULT_FLOW_PATTERN_PREFIX
from rasa.cdu.stack.frames import PatternFlowStackFrame


FLOW_PATTERN_CONTINUE_INTERRUPTED = (
    RASA_DEFAULT_FLOW_PATTERN_PREFIX + "continue_interrupted"
)


@dataclass
class ContinueInterruptedPatternFlowStackFrame(PatternFlowStackFrame):
    flow_id: str = FLOW_PATTERN_CONTINUE_INTERRUPTED
    previous_flow_name: str = ""

    @classmethod
    def type(cls) -> str:
        """Returns the type of the frame."""
        return "pattern_continue_interrupted"

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> ContinueInterruptedPatternFlowStackFrame:
        """Creates a `DialogueStackFrame` from a dictionary.

        Args:
            data: The dictionary to create the `DialogueStackFrame` from.

        Returns:
            The created `DialogueStackFrame`.
        """
        return ContinueInterruptedPatternFlowStackFrame(
            data["frame_id"],
            step_id=data["step_id"],
            previous_flow_name=data["previous_flow_name"],
        )

    def as_dict(self) -> Dict[str, Any]:
        super_dict = super().as_dict()
        super_dict.update(
            {
                "previous_flow_name": self.previous_flow_name,
            }
        )
        return super_dict

    def context_as_dict(
        self, underlying_frames: List[DialogueStackFrame]
    ) -> Dict[str, Any]:
        super_dict = super().context_as_dict(underlying_frames)
        super_dict.update(
            {
                "previous_flow_name": self.previous_flow_name,
            }
        )
        return super_dict
