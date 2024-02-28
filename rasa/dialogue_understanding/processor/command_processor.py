from typing import List, Optional, Type, Set, Dict

import structlog
from rasa.dialogue_understanding.commands import (
    CancelFlowCommand,
    ClarifyCommand,
    Command,
    CorrectSlotsCommand,
    CorrectedSlot,
    SetSlotCommand,
    StartFlowCommand,
    FreeFormAnswerCommand,
)
from rasa.dialogue_understanding.commands.handle_code_change_command import (
    HandleCodeChangeCommand,
)
from rasa.dialogue_understanding.patterns.collect_information import (
    CollectInformationPatternFlowStackFrame,
)
from rasa.dialogue_understanding.patterns.correction import (
    CorrectionPatternFlowStackFrame,
)
from rasa.dialogue_understanding.stack.dialogue_stack import DialogueStack
from rasa.dialogue_understanding.stack.frames import (
    BaseFlowStackFrame,
)
from rasa.dialogue_understanding.stack.utils import (
    filled_slots_for_active_flow,
    top_flow_frame,
)
from rasa.shared.core.constants import FLOW_HASHES_SLOT
from rasa.shared.core.events import Event, SlotSet
from rasa.shared.core.flows.steps.collect import CollectInformationFlowStep
from rasa.shared.core.flows import FlowsList
from rasa.shared.core.trackers import DialogueStateTracker
from rasa.shared.nlu.constants import COMMANDS


structlogger = structlog.get_logger()


def contains_command(commands: List[Command], typ: Type[Command]) -> bool:
    """Check if a list of commands contains a command of a given type.

    Example:
        >>> contains_command([SetSlotCommand("foo", "bar")], SetSlotCommand)
        True

    Args:
        commands: The commands to check.
        typ: The type of command to check for.

    Returns:
    `True` if the list of commands contains a command of the given type.
    """
    return any(isinstance(command, typ) for command in commands)


def get_commands_from_tracker(tracker: DialogueStateTracker) -> List[Command]:
    """Extracts the commands from the tracker.

    Args:
        tracker: The tracker containing the conversation history up to now.

    Returns:
    The commands.
    """
    if tracker.latest_message:
        dumped_commands = tracker.latest_message.parse_data.get(COMMANDS) or []
        assert isinstance(dumped_commands, list)
        return [Command.command_from_json(command) for command in dumped_commands]
    else:
        return []


def filter_start_flow_commands(commands: List[Command]) -> List[str]:
    """Filters the start flow commands from a list of commands."""
    return [
        command.flow for command in commands if isinstance(command, StartFlowCommand)
    ]


def validate_state_of_commands(commands: List[Command]) -> None:
    """Validates the state of the commands.

    We have some invariants that should always hold true. This function
    checks if they do. Executing the commands relies on these invariants.

    We cleanup the commands before executing them, so the cleanup should
    always make sure that these invariants hold true - no matter the commands
    that are provided.

    Args:
        commands: The commands to validate.

    Raises:
        ValueError: If the state of the commands is invalid.
    """
    # check that there is only at max one cancel flow command
    if sum(isinstance(c, CancelFlowCommand) for c in commands) > 1:
        structlogger.error(
            "command_processor.validate_state_of_commands.multiple_cancel_flow_commands",
            commands=commands,
        )
        raise ValueError("There can only be one cancel flow command.")

    # check that free form answer commands are only at the beginning of the list
    free_form_answer_commands = [
        c for c in commands if isinstance(c, FreeFormAnswerCommand)
    ]
    if free_form_answer_commands != commands[: len(free_form_answer_commands)]:
        structlogger.error(
            "command_processor.validate_state_of_commands.free_form_answer_commands_not_at_beginning",  # noqa: E501
            commands=commands,
        )
        raise ValueError(
            "Free form answer commands must be at start of the predicted command list."
        )

    # check that there is at max only one correctslots command
    if sum(isinstance(c, CorrectSlotsCommand) for c in commands) > 1:
        structlogger.error(
            "command_processor.validate_state_of_commands.multiple_correct_slots_commands",
            commands=commands,
        )
        raise ValueError("There can only be one correct slots command.")


def find_updated_flows(tracker: DialogueStateTracker, all_flows: FlowsList) -> Set[str]:
    """Find the set of updated flows.

    Run through the current dialogue stack and compare the flow hashes of the
    flows on the stack with those stored in the tracker.

    Args:
        tracker: The tracker.
        all_flows: All flows.

    Returns:
    A set of flow ids of those flows that have changed
    """
    stored_fingerprints: Dict[str, str] = tracker.get_slot(FLOW_HASHES_SLOT) or {}
    stack = tracker.stack

    changed_flows = set()
    for frame in stack.frames:
        if isinstance(frame, BaseFlowStackFrame):
            flow = all_flows.flow_by_id(frame.flow_id)
            if flow is None or (
                flow.id in stored_fingerprints
                and flow.fingerprint != stored_fingerprints[flow.id]
            ):
                changed_flows.add(frame.flow_id)
    return changed_flows


def calculate_flow_fingerprints(all_flows: FlowsList) -> Dict[str, str]:
    """Calculate fingerprints for all flows."""
    return {flow.id: flow.fingerprint for flow in all_flows.underlying_flows}


def execute_commands(
    tracker: DialogueStateTracker, all_flows: FlowsList
) -> List[Event]:
    """Executes a list of commands.

    Args:
        commands: The commands to execute.
        tracker: The tracker to execute the commands on.
        all_flows: All flows.

    Returns:
        A list of the events that were created.
    """
    commands: List[Command] = get_commands_from_tracker(tracker)
    original_tracker = tracker.copy()

    commands = clean_up_commands(commands, tracker, all_flows)

    updated_flows = find_updated_flows(tracker, all_flows)
    if updated_flows:
        # Override commands
        structlogger.debug(
            "command_processor.execute_commands.running_flows_were_updated",
            updated_flow_ids=updated_flows,
        )
        commands = [HandleCodeChangeCommand()]

    # store current flow hashes if they changed
    new_hashes = calculate_flow_fingerprints(all_flows)
    flow_hash_events: List[Event] = []
    if new_hashes != (tracker.get_slot(FLOW_HASHES_SLOT) or {}):
        flow_hash_events.append(SlotSet(FLOW_HASHES_SLOT, new_hashes))
        tracker.update_with_events(flow_hash_events)

    events: List[Event] = flow_hash_events

    # commands need to be reversed to make sure they end up in the right order
    # on the stack. e.g. if there multiple start flow commands, the first one
    # should be on top of the stack. this is achieved by reversing the list
    # and then pushing the commands onto the stack in the reversed order.
    reversed_commands = list(reversed(commands))

    validate_state_of_commands(commands)

    for command in reversed_commands:
        new_events = command.run_command_on_tracker(
            tracker, all_flows, original_tracker
        )
        events.extend(new_events)
        tracker.update_with_events(new_events)

    return remove_duplicated_set_slots(events)


def remove_duplicated_set_slots(events: List[Event]) -> List[Event]:
    """Removes duplicated set slot events.

    This can happen if a slot is set multiple times in a row. We only want to
    keep the last one.

    Args:
        events: The events to optimize.

    Returns:
    The optimized events.
    """
    slots_so_far = set()

    optimized_events: List[Event] = []

    for event in reversed(events):
        if isinstance(event, SlotSet) and event.key in slots_so_far:
            # slot will be overwritten, no need to set it
            continue
        elif isinstance(event, SlotSet):
            slots_so_far.add(event.key)

        optimized_events.append(event)

    # since we reversed the original events, we need to reverse the optimized
    # events again to get them in the right order
    return list(reversed(optimized_events))


def get_current_collect_step(
    dialogue_stack: DialogueStack, all_flows: FlowsList
) -> Optional[CollectInformationFlowStep]:
    """Get the current collect information if the conversation is currently in one.

    If we are currently in a collect information step, the stack should have at least
    two frames. The top frame is the collect information pattern and the frame below
    is the flow that triggered the collect information pattern. We can use the flow
    id to get the collect information step from the flow.

    Args:
        dialogue_stack: The dialogue stack.
        all_flows: All flows.

    Returns:
    The current collect information if the conversation is currently in one,
    `None` otherwise.
    """
    if not (top_frame := dialogue_stack.top()):
        # we are currently not in a flow
        return None

    if not isinstance(top_frame, CollectInformationPatternFlowStackFrame):
        # we are currently not in a collect information
        return None

    if len(dialogue_stack.frames) <= 1:
        # for some reason only the collect information pattern step is on the stack
        # but no flow that triggered it. this should never happen.
        structlogger.warning(
            "command_processor.get_current_collect_step.no_flow_on_stack",
            stack=dialogue_stack,
        )
        return None

    frame_that_triggered_collect_infos = dialogue_stack.frames[-2]
    if not isinstance(frame_that_triggered_collect_infos, BaseFlowStackFrame):
        # this is a failure, if there is a frame, we should be able to get the
        # step from it
        structlogger.warning(
            "command_processor.get_current_collect_step.no_step_for_frame",
            frame=frame_that_triggered_collect_infos,
        )
        return None

    step = frame_that_triggered_collect_infos.step(all_flows)
    if isinstance(step, CollectInformationFlowStep):
        # we found it!
        return step
    else:
        # this should never happen as we only push collect information patterns
        # onto the stack if there is a collect information step
        structlogger.warning(
            "command_processor.get_current_collect_step.step_not_collect",
            step=step,
        )
        return None


def clean_up_commands(
    commands: List[Command], tracker: DialogueStateTracker, all_flows: FlowsList
) -> List[Command]:
    """Clean up a list of commands.

    This will clean commands that are not necessary anymore. e.g. removing commands
    where the slot they correct was previously corrected to the same value, grouping
    all slot corrections into one command, removing duplicate cancel flow commands
    and moving free form answer commands to the beginning of the list (to be last when
    reversed.)

    Args:
        commands: The commands to clean up.
        tracker: The tracker to clean up the commands for.
        all_flows: All flows.

    Returns:
    The cleaned up commands.
    """
    stack = tracker.stack
    slots_so_far = filled_slots_for_active_flow(tracker, all_flows)

    clean_commands: List[Command] = []

    for command in commands:
        if isinstance(command, SetSlotCommand):
            clean_commands = clean_up_slot_command(
                clean_commands, command, stack, all_flows, slots_so_far
            )
        elif isinstance(command, CancelFlowCommand) and contains_command(
            clean_commands, CancelFlowCommand
        ):
            structlogger.debug(
                "command_processor.clean_up_commands.skip_command_already_cancelled_flow",
                command=command,
            )
        elif isinstance(command, FreeFormAnswerCommand):
            structlogger.debug(
                "command_processor.clean_up_commands.prepend_command_free_form_answer",
                command=command,
            )
            clean_commands.insert(0, command)
        # drop all clarify commands if there are more commands. Otherwise, we might
        # get a situation where two questions are asked at once.
        elif isinstance(command, ClarifyCommand) and len(commands) > 1:
            # if there are multiple clarify commands, do add the first one
            if (
                all([isinstance(c, ClarifyCommand) for c in commands])
                and len(clean_commands) == 0
            ):
                clean_commands.append(command)
            structlogger.debug(
                "command_processor.clean_up_commands.drop_clarify_given_other_commands",
                command=command,
            )
        else:
            clean_commands.append(command)
    return clean_commands


def clean_up_slot_command(
    commands_so_far: List[Command],
    command: SetSlotCommand,
    stack: DialogueStack,
    all_flows: FlowsList,
    slots_so_far: Set[str],
) -> List[Command]:
    """Clean up a slot command.

    This will remove commands that are not necessary anymore, e.g. because the slot
    they correct was previously corrected to the same value. It will group all slot
    corrections into one command.

    Args:
        commands_so_far: The commands cleaned up so far.
        command: The command to clean up.
        stack: The dialogue stack.
        all_flows: All flows.
        slots_so_far: The slots that have been filled so far.

    Returns:
        The cleaned up commands.
    """
    resulting_commands = commands_so_far[:]
    if command.name in slots_so_far:
        current_collect_info = get_current_collect_step(stack, all_flows)

        if current_collect_info and current_collect_info.collect == command.name:
            # not a correction but rather an answer to the current collect info
            resulting_commands.append(command)
            return resulting_commands

        structlogger.debug(
            "command_processor.clean_up_slot_command.convert_command_to_correction",
            command=command,
        )
        top = top_flow_frame(stack)
        if isinstance(top, CorrectionPatternFlowStackFrame):
            already_corrected_slots = top.corrected_slots
        else:
            already_corrected_slots = {}

        if (
            command.name in already_corrected_slots
            and already_corrected_slots[command.name] == command.value
        ):
            structlogger.debug(
                "command_processor.clean_up_slot_command.skip_command_slot_already_corrected",
                command=command,
            )
            return resulting_commands

        # Group all corrections into one command
        corrected_slot = CorrectedSlot(command.name, command.value)
        for c in resulting_commands:
            if isinstance(c, CorrectSlotsCommand):
                c.corrected_slots.append(corrected_slot)
                break
        else:
            resulting_commands.append(
                CorrectSlotsCommand(corrected_slots=[corrected_slot])
            )
    else:
        resulting_commands.append(command)

    return resulting_commands