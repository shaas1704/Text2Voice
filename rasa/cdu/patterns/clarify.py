from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import structlog
from rasa.cdu.stack.dialogue_stack import (
    DialogueStack,
    DialogueStackFrame,
)
from rasa.cdu.stack.frames import PatternFlowStackFrame
from rasa.core.actions import action
from rasa.core.channels.channel import OutputChannel
from rasa.core.nlg.generator import NaturalLanguageGenerator
from rasa.shared.constants import RASA_DEFAULT_FLOW_PATTERN_PREFIX
from rasa.shared.core.constants import ACTION_CLARIFY_FLOWS, DIALOGUE_STACK_SLOT
from rasa.shared.core.domain import Domain
from rasa.shared.core.events import Event, SlotSet
from rasa.shared.core.trackers import DialogueStateTracker


structlogger = structlog.get_logger()

FLOW_PATTERN_CLARIFICATION = RASA_DEFAULT_FLOW_PATTERN_PREFIX + "clarification"


@dataclass
class ClarifyPatternFlowStackFrame(PatternFlowStackFrame):
    flow_id: str = FLOW_PATTERN_CLARIFICATION
    names: List[str] = field(default_factory=list)
    clarification_options: str = ""

    @classmethod
    def type(cls) -> str:
        """Returns the type of the frame."""
        return "pattern_clarification"

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> ClarifyPatternFlowStackFrame:
        """Creates a `DialogueStackFrame` from a dictionary.

        Args:
            data: The dictionary to create the `DialogueStackFrame` from.

        Returns:
            The created `DialogueStackFrame`.
        """
        return ClarifyPatternFlowStackFrame(
            data["frame_id"],
            step_id=data["step_id"],
            names=data["names"],
            clarification_options=data["clarification_options"],
        )

    def as_dict(self) -> Dict[str, Any]:
        super_dict = super().as_dict()
        super_dict.update(
            {
                "names": self.names,
                "clarification_options": self.clarification_options,
            }
        )
        return super_dict

    def context_as_dict(
        self, underlying_frames: List[DialogueStackFrame]
    ) -> Dict[str, Any]:
        super_dict = super().context_as_dict(underlying_frames)
        super_dict.update(
            {
                "names": self.names,
                "clarification_options": self.clarification_options,
            }
        )
        return super_dict


class ActionClarifyFlows(action.Action):
    """Action which clarifies which flow to start."""

    def name(self) -> str:
        """Return the flow name."""
        return ACTION_CLARIFY_FLOWS

    @staticmethod
    def assemble_options_string(names: List[str]) -> str:
        """Concatenate options to a human-readable string."""
        clarification_message = ""
        for i, name in enumerate(names):
            if i == 0:
                clarification_message += name
            elif i == len(names) - 1:
                clarification_message += f" or {name}"
            else:
                clarification_message += f", {name}"
        return clarification_message

    async def run(
        self,
        output_channel: "OutputChannel",
        nlg: "NaturalLanguageGenerator",
        tracker: "DialogueStateTracker",
        domain: "Domain",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Event]:
        """Correct the slots."""
        stack = DialogueStack.from_tracker(tracker)
        if not (top := stack.top()):
            structlogger.warning("action.clarify_flows.no_active_flow")
            return []

        if not isinstance(top, ClarifyPatternFlowStackFrame):
            structlogger.warning("action.clarify_flows.no_correction_frame", top=top)
            return []

        options_string = self.assemble_options_string(top.names)
        top.clarification_options = options_string
        # since we modified the stack frame, we need to update the stack
        return [SlotSet(DIALOGUE_STACK_SLOT, stack.as_dict())]
