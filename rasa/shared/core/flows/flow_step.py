from __future__ import annotations

from dataclasses import dataclass
from typing import (
    Any,
    Dict,
    Generator,
    List,
    Optional,
    Protocol,
    Set,
    Text,
    Union,
    runtime_checkable,
)
import structlog

from rasa.shared.core.trackers import DialogueStateTracker
from rasa.shared.constants import UTTER_PREFIX
from rasa.shared.nlu.constants import ENTITY_ATTRIBUTE_TYPE, INTENT_NAME_KEY

from rasa.shared.utils.llm import (
    DEFAULT_OPENAI_GENERATE_MODEL_NAME,
    DEFAULT_OPENAI_TEMPERATURE,
)

structlogger = structlog.get_logger()

START_STEP = "START"

END_STEP = "END"

DEFAULT_STEPS = {END_STEP, START_STEP}


@dataclass
class StepSequence:
    child_steps: List[FlowStep]

    @staticmethod
    def from_json(steps_config: List[Dict[Text, Any]]) -> StepSequence:
        """Used to read steps from parsed YAML.

        Args:
            steps_config: The parsed YAML as a dictionary.

        Returns:
            The parsed steps.
        """

        flow_steps: List[FlowStep] = [step_from_json(config) for config in steps_config]

        return StepSequence(child_steps=flow_steps)

    def as_json(self) -> List[Dict[Text, Any]]:
        """Returns the steps as a dictionary.

        Returns:
            The steps as a dictionary.
        """
        return [
            step.as_json()
            for step in self.child_steps
            if not isinstance(step, InternalFlowStep)
        ]

    @property
    def steps(self) -> List[FlowStep]:
        """Returns the steps of the flow."""
        return [
            step
            for child_step in self.child_steps
            for step in child_step.steps_in_tree()
        ]

    def first(self) -> Optional[FlowStep]:
        """Returns the first step of the sequence."""
        if len(self.child_steps) == 0:
            return None
        return self.child_steps[0]


def step_from_json(flow_step_config: Dict[Text, Any]) -> FlowStep:
    """Used to read flow steps from parsed YAML.

    Args:
        flow_step_config: The parsed YAML as a dictionary.

    Returns:
        The parsed flow step.
    """
    if "action" in flow_step_config:
        return ActionFlowStep.from_json(flow_step_config)
    if "intent" in flow_step_config:
        return UserMessageStep.from_json(flow_step_config)
    if "collect" in flow_step_config:
        return CollectInformationFlowStep.from_json(flow_step_config)
    if "link" in flow_step_config:
        return LinkFlowStep.from_json(flow_step_config)
    if "set_slots" in flow_step_config:
        return SetSlotsFlowStep.from_json(flow_step_config)
    if "generation_prompt" in flow_step_config:
        return GenerateResponseFlowStep.from_json(flow_step_config)
    else:
        return BranchFlowStep.from_json(flow_step_config)


@dataclass
class FlowStep:
    """Represents the configuration of a flow step."""

    custom_id: Optional[Text]
    """The id of the flow step."""
    idx: int
    """The index of the step in the flow."""
    description: Optional[Text]
    """The description of the flow step."""
    metadata: Dict[Text, Any]
    """Additional, unstructured information about this flow step."""
    next: "FlowLinks"
    """The next steps of the flow step."""

    @classmethod
    def _from_json(cls, flow_step_config: Dict[Text, Any]) -> FlowStep:
        """Used to read flow steps from parsed YAML.

        Args:
            flow_step_config: The parsed YAML as a dictionary.

        Returns:
            The parsed flow step.
        """
        return FlowStep(
            # the idx is set later once the flow is created that contains
            # this step
            idx=-1,
            custom_id=flow_step_config.get("id"),
            description=flow_step_config.get("description"),
            metadata=flow_step_config.get("metadata", {}),
            next=FlowLinks.from_json(flow_step_config.get("next", [])),
        )

    def as_json(self) -> Dict[Text, Any]:
        """Returns the flow step as a dictionary.

        Returns:
            The flow step as a dictionary.
        """
        dump = {"next": self.next.as_json(), "id": self.id}

        if self.description:
            dump["description"] = self.description
        if self.metadata:
            dump["metadata"] = self.metadata
        return dump

    def steps_in_tree(self) -> Generator[FlowStep, None, None]:
        """Returns the steps in the tree of the flow step."""
        yield self
        yield from self.next.steps_in_tree()

    @property
    def id(self) -> Text:
        """Returns the id of the flow step."""
        return self.custom_id or self.default_id()

    def default_id(self) -> str:
        """Returns the default id of the flow step."""
        return f"{self.idx}_{self.default_id_postfix()}"

    def default_id_postfix(self) -> str:
        """Returns the default id postfix of the flow step."""
        raise NotImplementedError()

    @property
    def utterances(self) -> Set[str]:
        """Return all the utterances used in this step"""
        return set()


class InternalFlowStep(FlowStep):
    """Represents the configuration of a built-in flow step.

    Built in flow steps are required to manage the lifecycle of a
    flow and are not intended to be used by users.
    """

    @classmethod
    def from_json(cls, flow_step_config: Dict[Text, Any]) -> ActionFlowStep:
        """Used to read flow steps from parsed JSON.

        Args:
            flow_step_config: The parsed JSON as a dictionary.

        Returns:
            The parsed flow step.
        """
        raise ValueError("A start step cannot be parsed.")

    def as_json(self) -> Dict[Text, Any]:
        """Returns the flow step as a dictionary.

        Returns:
            The flow step as a dictionary.
        """
        raise ValueError("A start step cannot be dumped.")


@dataclass
class StartFlowStep(InternalFlowStep):
    """Represents the configuration of a start flow step."""

    def __init__(self, start_step_id: Optional[Text]) -> None:
        """Initializes a start flow step.

        Args:
            start_step: The step to start the flow from.
        """
        if start_step_id is not None:
            links: List[FlowLink] = [StaticFlowLink(start_step_id)]
        else:
            links = []

        super().__init__(
            idx=0,
            custom_id=START_STEP,
            description=None,
            metadata={},
            next=FlowLinks(links=links),
        )


@dataclass
class EndFlowStep(InternalFlowStep):
    """Represents the configuration of an end to a flow."""

    def __init__(self) -> None:
        """Initializes an end flow step."""
        super().__init__(
            idx=0,
            custom_id=END_STEP,
            description=None,
            metadata={},
            next=FlowLinks(links=[]),
        )


CONTINUE_STEP_PREFIX = "NEXT:"


@dataclass
class ContinueFlowStep(InternalFlowStep):
    """Represents the configuration of a continue-step flow step."""

    def __init__(self, next: str) -> None:
        """Initializes a continue-step flow step."""
        super().__init__(
            idx=0,
            custom_id=CONTINUE_STEP_PREFIX + next,
            description=None,
            metadata={},
            # The continue step links to the step that should be continued.
            # The flow policy in a sense only "runs" the logic of a step
            # when it transitions to that step, once it is there it will use
            # the next link to transition to the next step. This means that
            # if we want to "re-run" a step, we need to link to it again.
            # This is why the continue step links to the step that should be
            # continued.
            next=FlowLinks(links=[StaticFlowLink(next)]),
        )

    @staticmethod
    def continue_step_for_id(step_id: str) -> str:
        return CONTINUE_STEP_PREFIX + step_id


@dataclass
class ActionFlowStep(FlowStep):
    """Represents the configuration of an action flow step."""

    action: Text
    """The action of the flow step."""

    @classmethod
    def from_json(cls, flow_step_config: Dict[Text, Any]) -> ActionFlowStep:
        """Used to read flow steps from parsed YAML.

        Args:
            flow_step_config: The parsed YAML as a dictionary.

        Returns:
            The parsed flow step.
        """
        base = super()._from_json(flow_step_config)
        return ActionFlowStep(
            action=flow_step_config.get("action", ""),
            **base.__dict__,
        )

    def as_json(self) -> Dict[Text, Any]:
        """Returns the flow step as a dictionary.

        Returns:
            The flow step as a dictionary.
        """
        dump = super().as_json()
        dump["action"] = self.action
        return dump

    def default_id_postfix(self) -> str:
        return self.action

    @property
    def utterances(self) -> Set[str]:
        """Return all the utterances used in this step"""
        return {self.action} if self.action.startswith(UTTER_PREFIX) else set()


@dataclass
class BranchFlowStep(FlowStep):
    """Represents the configuration of a branch flow step."""

    @classmethod
    def from_json(cls, flow_step_config: Dict[Text, Any]) -> BranchFlowStep:
        """Used to read flow steps from parsed YAML.

        Args:
            flow_step_config: The parsed YAML as a dictionary.

        Returns:
            The parsed flow step.
        """
        base = super()._from_json(flow_step_config)
        return BranchFlowStep(**base.__dict__)

    def as_json(self) -> Dict[Text, Any]:
        """Returns the flow step as a dictionary.

        Returns:
            The flow step as a dictionary.
        """
        dump = super().as_json()
        return dump

    def default_id_postfix(self) -> str:
        """Returns the default id postfix of the flow step."""
        return "branch"


@dataclass
class LinkFlowStep(FlowStep):
    """Represents the configuration of a link flow step."""

    link: Text
    """The link of the flow step."""

    @classmethod
    def from_json(cls, flow_step_config: Dict[Text, Any]) -> LinkFlowStep:
        """Used to read flow steps from parsed YAML.

        Args:
            flow_step_config: The parsed YAML as a dictionary.

        Returns:
            The parsed flow step.
        """
        base = super()._from_json(flow_step_config)
        return LinkFlowStep(
            link=flow_step_config.get("link", ""),
            **base.__dict__,
        )

    def as_json(self) -> Dict[Text, Any]:
        """Returns the flow step as a dictionary.

        Returns:
            The flow step as a dictionary.
        """
        dump = super().as_json()
        dump["link"] = self.link
        return dump

    def default_id_postfix(self) -> str:
        """Returns the default id postfix of the flow step."""
        return f"link_{self.link}"


@dataclass
class TriggerCondition:
    """Represents the configuration of a trigger condition."""

    intent: Text
    """The intent to trigger the flow."""
    entities: List[Text]
    """The entities to trigger the flow."""

    def is_triggered(self, intent: Text, entities: List[Text]) -> bool:
        """Check if condition is triggered by the given intent and entities.

        Args:
            intent: The intent to check.
            entities: The entities to check.

        Returns:
            Whether the trigger condition is triggered by the given intent and entities.
        """
        if self.intent != intent:
            return False
        if len(self.entities) == 0:
            return True
        return all(entity in entities for entity in self.entities)


@runtime_checkable
class StepThatCanStartAFlow(Protocol):
    """Represents a step that can start a flow."""

    def is_triggered(self, tracker: DialogueStateTracker) -> bool:
        """Check if a flow should be started for the tracker

        Args:
            tracker: The tracker to check.

        Returns:
            Whether a flow should be started for the tracker.
        """
        ...


@dataclass
class UserMessageStep(FlowStep, StepThatCanStartAFlow):
    """Represents the configuration of an intent flow step."""

    trigger_conditions: List[TriggerCondition]
    """The trigger conditions of the flow step."""

    @classmethod
    def from_json(cls, flow_step_config: Dict[Text, Any]) -> UserMessageStep:
        """Used to read flow steps from parsed YAML.

        Args:
            flow_step_config: The parsed YAML as a dictionary.

        Returns:
            The parsed flow step.
        """
        base = super()._from_json(flow_step_config)

        trigger_conditions = []
        if "intent" in flow_step_config:
            trigger_conditions.append(
                TriggerCondition(
                    intent=flow_step_config["intent"],
                    entities=flow_step_config.get("entities", []),
                )
            )
        elif "or" in flow_step_config:
            for trigger_condition in flow_step_config["or"]:
                trigger_conditions.append(
                    TriggerCondition(
                        intent=trigger_condition.get("intent", ""),
                        entities=trigger_condition.get("entities", []),
                    )
                )

        return UserMessageStep(
            trigger_conditions=trigger_conditions,
            **base.__dict__,
        )

    def as_json(self) -> Dict[Text, Any]:
        """Returns the flow step as a dictionary.

        Returns:
            The flow step as a dictionary.
        """
        dump = super().as_json()

        if len(self.trigger_conditions) == 1:
            dump["intent"] = self.trigger_conditions[0].intent
            if self.trigger_conditions[0].entities:
                dump["entities"] = self.trigger_conditions[0].entities
        elif len(self.trigger_conditions) > 1:
            dump["or"] = [
                {
                    "intent": trigger_condition.intent,
                    "entities": trigger_condition.entities,
                }
                for trigger_condition in self.trigger_conditions
            ]

        return dump

    def is_triggered(self, tracker: DialogueStateTracker) -> bool:
        """Returns whether the flow step is triggered by the given intent and entities.

        Args:
            intent: The intent to check.
            entities: The entities to check.

        Returns:
            Whether the flow step is triggered by the given intent and entities.
        """
        if not tracker.latest_message:
            return False

        intent: Text = tracker.latest_message.intent.get(INTENT_NAME_KEY, "")
        entities: List[Text] = [
            e.get(ENTITY_ATTRIBUTE_TYPE, "") for e in tracker.latest_message.entities
        ]
        return any(
            trigger_condition.is_triggered(intent, entities)
            for trigger_condition in self.trigger_conditions
        )

    def default_id_postfix(self) -> str:
        """Returns the default id postfix of the flow step."""
        return "intent"


DEFAULT_LLM_CONFIG = {
    "_type": "openai",
    "request_timeout": 5,
    "temperature": DEFAULT_OPENAI_TEMPERATURE,
    "model_name": DEFAULT_OPENAI_GENERATE_MODEL_NAME,
}


@dataclass
class GenerateResponseFlowStep(FlowStep):
    """Represents the configuration of a step prompting an LLM."""

    generation_prompt: Text
    """The prompt template of the flow step."""
    llm_config: Optional[Dict[Text, Any]] = None
    """The LLM configuration of the flow step."""

    @classmethod
    def from_json(cls, flow_step_config: Dict[Text, Any]) -> GenerateResponseFlowStep:
        """Used to read flow steps from parsed YAML.

        Args:
            flow_step_config: The parsed YAML as a dictionary.

        Returns:
            The parsed flow step.
        """
        base = super()._from_json(flow_step_config)
        return GenerateResponseFlowStep(
            generation_prompt=flow_step_config.get("generation_prompt", ""),
            llm_config=flow_step_config.get("llm", None),
            **base.__dict__,
        )

    def as_json(self) -> Dict[Text, Any]:
        """Returns the flow step as a dictionary.

        Returns:
            The flow step as a dictionary.
        """
        dump = super().as_json()
        dump["generation_prompt"] = self.generation_prompt
        if self.llm_config:
            dump["llm"] = self.llm_config

        return dump

    def generate(self, tracker: DialogueStateTracker) -> Optional[Text]:
        """Generates a response for the given tracker.

        Args:
            tracker: The tracker to generate a response for.

        Returns:
            The generated response.
        """
        from rasa.shared.utils.llm import llm_factory, tracker_as_readable_transcript
        from jinja2 import Template

        context = {
            "history": tracker_as_readable_transcript(tracker, max_turns=5),
            "latest_user_message": tracker.latest_message.text
            if tracker.latest_message
            else "",
        }
        context.update(tracker.current_slot_values())

        llm = llm_factory(self.llm_config, DEFAULT_LLM_CONFIG)
        prompt = Template(self.generation_prompt).render(context)

        try:
            return llm(prompt)
        except Exception as e:
            # unfortunately, langchain does not wrap LLM exceptions which means
            # we have to catch all exceptions here
            structlogger.error(
                "flow.generate_step.llm.error", error=e, step=self.id, prompt=prompt
            )
            return None

    def default_id_postfix(self) -> str:
        return "generate"


@dataclass
class SlotRejection:
    """A slot rejection."""

    if_: str
    """The condition that should be checked."""
    utter: str
    """The utterance that should be executed if the condition is met."""

    @staticmethod
    def from_dict(rejection_config: Dict[Text, Any]) -> SlotRejection:
        """Used to read slot rejections from parsed YAML.

        Args:
            rejection_config: The parsed YAML as a dictionary.

        Returns:
            The parsed slot rejection.
        """
        return SlotRejection(
            if_=rejection_config["if"],
            utter=rejection_config["utter"],
        )

    def as_dict(self) -> Dict[Text, Any]:
        """Returns the slot rejection as a dictionary.

        Returns:
            The slot rejection as a dictionary.
        """
        return {
            "if": self.if_,
            "utter": self.utter,
        }


@dataclass
class CollectInformationFlowStep(FlowStep):
    """Represents the configuration of a collect information flow step."""

    collect: Text
    """The collect information of the flow step."""
    utter: Text
    """The utterance that the assistant uses to ask for the slot."""
    rejections: List[SlotRejection]
    """how the slot value is validated using predicate evaluation."""
    ask_before_filling: bool = False
    """Whether to always ask the question even if the slot is already filled."""
    reset_after_flow_ends: bool = True
    """Determines whether to reset the slot value at the end of the flow."""

    @classmethod
    def from_json(cls, flow_step_config: Dict[Text, Any]) -> CollectInformationFlowStep:
        """Used to read flow steps from parsed YAML.

        Args:
            flow_step_config: The parsed YAML as a dictionary.

        Returns:
            The parsed flow step.
        """
        base = super()._from_json(flow_step_config)
        return CollectInformationFlowStep(
            collect=flow_step_config["collect"],
            utter=flow_step_config.get(
                "utter", f"utter_ask_{flow_step_config['collect']}"
            ),
            ask_before_filling=flow_step_config.get("ask_before_filling", False),
            reset_after_flow_ends=flow_step_config.get("reset_after_flow_ends", True),
            rejections=[
                SlotRejection.from_dict(rejection)
                for rejection in flow_step_config.get("rejections", [])
            ],
            **base.__dict__,
        )

    def as_json(self) -> Dict[Text, Any]:
        """Returns the flow step as a dictionary.

        Returns:
            The flow step as a dictionary.
        """
        dump = super().as_json()
        dump["collect"] = self.collect
        dump["utter"] = self.utter
        dump["ask_before_filling"] = self.ask_before_filling
        dump["reset_after_flow_ends"] = self.reset_after_flow_ends
        dump["rejections"] = [rejection.as_dict() for rejection in self.rejections]

        return dump

    def default_id_postfix(self) -> str:
        """Returns the default id postfix of the flow step."""
        return f"collect_{self.collect}"

    @property
    def utterances(self) -> Set[str]:
        """Return all the utterances used in this step"""
        return {self.utter} | {r.utter for r in self.rejections}


@dataclass
class SetSlotsFlowStep(FlowStep):
    """Represents the configuration of a set_slots flow step."""

    slots: List[Dict[str, Any]]
    """Slots to set of the flow step."""

    @classmethod
    def from_json(cls, flow_step_config: Dict[Text, Any]) -> SetSlotsFlowStep:
        """Used to read flow steps from parsed YAML.

        Args:
            flow_step_config: The parsed YAML as a dictionary.

        Returns:
            The parsed flow step.
        """
        base = super()._from_json(flow_step_config)
        slots = [
            {"key": k, "value": v}
            for slot in flow_step_config.get("set_slots", [])
            for k, v in slot.items()
        ]
        return SetSlotsFlowStep(
            slots=slots,
            **base.__dict__,
        )

    def as_json(self) -> Dict[Text, Any]:
        """Returns the flow step as a dictionary.

        Returns:
            The flow step as a dictionary.
        """
        dump = super().as_json()
        dump["set_slots"] = [{slot["key"]: slot["value"]} for slot in self.slots]
        return dump

    def default_id_postfix(self) -> str:
        """Returns the default id postfix of the flow step."""
        return "set_slots"


@dataclass
class FlowLinks:
    """Represents the configuration of a list of flow links."""

    links: List[FlowLink]

    @staticmethod
    def from_json(flow_links_config: Union[str, List[Dict[Text, Any]]]) -> FlowLinks:
        """Used to read flow links from parsed YAML.

        Args:
            flow_links_config: The parsed YAML as a dictionary.

        Returns:
            The parsed flow links.
        """
        if not flow_links_config:
            return FlowLinks(links=[])

        if isinstance(flow_links_config, str):
            return FlowLinks(links=[StaticFlowLink.from_json(flow_links_config)])

        return FlowLinks(
            links=[
                BranchBasedLink.from_json(link_config)
                for link_config in flow_links_config
                if link_config
            ]
        )

    def as_json(self) -> Optional[Union[str, List[Dict[str, Any]]]]:
        """Returns the flow links as a dictionary.

        Returns:
            The flow links as a dictionary.
        """
        if not self.links:
            return None

        if len(self.links) == 1 and isinstance(self.links[0], StaticFlowLink):
            return self.links[0].as_json()

        return [link.as_json() for link in self.links]

    def no_link_available(self) -> bool:
        """Returns whether no link is available."""
        return len(self.links) == 0

    def steps_in_tree(self) -> Generator[FlowStep, None, None]:
        """Returns the steps in the tree of the flow links."""
        for link in self.links:
            yield from link.steps_in_tree()


class FlowLink:
    """Represents a flow link."""

    @property
    def target(self) -> Optional[Text]:
        """Returns the target of the flow link.

        Returns:
            The target of the flow link.
        """
        raise NotImplementedError()

    def as_json(self) -> Any:
        """Returns the flow link as a dictionary.

        Returns:
            The flow link as a dictionary.
        """
        raise NotImplementedError()

    @staticmethod
    def from_json(link_config: Any) -> FlowLink:
        """Used to read flow links from parsed YAML.

        Args:
            link_config: The parsed YAML as a dictionary.

        Returns:
            The parsed flow link.
        """
        raise NotImplementedError()

    def steps_in_tree(self) -> Generator[FlowStep, None, None]:
        """Returns the steps in the tree of the flow link."""
        raise NotImplementedError()

    def child_steps(self) -> List[FlowStep]:
        """Returns the child steps of the flow link."""
        raise NotImplementedError()


@dataclass
class BranchBasedLink(FlowLink):
    target_reference: Union[Text, StepSequence]
    """The id of the linked flow."""

    def steps_in_tree(self) -> Generator[FlowStep, None, None]:
        """Returns the steps in the tree of the flow link."""
        if isinstance(self.target_reference, StepSequence):
            yield from self.target_reference.steps

    def child_steps(self) -> List[FlowStep]:
        """Returns the child steps of the flow link."""
        if isinstance(self.target_reference, StepSequence):
            return self.target_reference.child_steps
        else:
            return []

    @property
    def target(self) -> Optional[Text]:
        """Returns the target of the flow link."""
        if isinstance(self.target_reference, StepSequence):
            if first := self.target_reference.first():
                return first.id
            else:
                return None
        else:
            return self.target_reference

    @staticmethod
    def from_json(link_config: Dict[Text, Any]) -> BranchBasedLink:
        """Used to read a single flow links from parsed YAML.

        Args:
            link_config: The parsed YAML as a dictionary.

        Returns:
            The parsed flow link.
        """
        if "if" in link_config:
            return IfFlowLink.from_json(link_config)
        else:
            return ElseFlowLink.from_json(link_config)


@dataclass
class IfFlowLink(BranchBasedLink):
    """Represents the configuration of an if flow link."""

    condition: Optional[Text]
    """The condition of the linked flow."""

    @staticmethod
    def from_json(link_config: Dict[Text, Any]) -> IfFlowLink:
        """Used to read flow links from parsed YAML.

        Args:
            link_config: The parsed YAML as a dictionary.

        Returns:
            The parsed flow link.
        """
        if isinstance(link_config["then"], str):
            return IfFlowLink(
                target_reference=link_config["then"], condition=link_config.get("if")
            )
        else:
            return IfFlowLink(
                target_reference=StepSequence.from_json(link_config["then"]),
                condition=link_config.get("if"),
            )

    def as_json(self) -> Dict[Text, Any]:
        """Returns the flow link as a dictionary.

        Returns:
            The flow link as a dictionary.
        """
        return {
            "if": self.condition,
            "then": self.target_reference.as_json()
            if isinstance(self.target_reference, StepSequence)
            else self.target_reference,
        }


@dataclass
class ElseFlowLink(BranchBasedLink):
    """Represents the configuration of an else flow link."""

    @staticmethod
    def from_json(link_config: Dict[Text, Any]) -> ElseFlowLink:
        """Used to read flow links from parsed YAML.

        Args:
            link_config: The parsed YAML as a dictionary.

        Returns:
            The parsed flow link.
        """
        if isinstance(link_config["else"], str):
            return ElseFlowLink(target_reference=link_config["else"])
        else:
            return ElseFlowLink(
                target_reference=StepSequence.from_json(link_config["else"])
            )

    def as_json(self) -> Dict[Text, Any]:
        """Returns the flow link as a dictionary.

        Returns:
            The flow link as a dictionary.
        """
        return {
            "else": self.target_reference.as_json()
            if isinstance(self.target_reference, StepSequence)
            else self.target_reference
        }


@dataclass
class StaticFlowLink(FlowLink):
    """Represents the configuration of a static flow link."""

    target_id: Text
    """The id of the linked flow."""

    @staticmethod
    def from_json(link_config: Text) -> StaticFlowLink:
        """Used to read flow links from parsed YAML.

        Args:
            link_config: The parsed YAML as a dictionary.

        Returns:
            The parsed flow link.
        """
        return StaticFlowLink(link_config)

    def as_json(self) -> Text:
        """Returns the flow link as a dictionary.

        Returns:
            The flow link as a dictionary.
        """
        return self.target

    def steps_in_tree(self) -> Generator[FlowStep, None, None]:
        """Returns the steps in the tree of the flow link."""
        # static links do not have any child steps
        yield from []

    def child_steps(self) -> List[FlowStep]:
        """Returns the child steps of the flow link."""
        return []

    @property
    def target(self) -> Optional[Text]:
        """Returns the target of the flow link."""
        return self.target_id
