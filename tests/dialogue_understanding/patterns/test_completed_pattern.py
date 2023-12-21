from rasa.dialogue_understanding.patterns.completed import (
    CompletedPatternFlowStackFrame,
)


async def test_pattern_completed_error_pattern_flow_stack_frame_type() -> None:
    frame = CompletedPatternFlowStackFrame()
    assert frame.type() == "pattern_completed"


async def test_pattern_completed_pattern_flow_stack_frame_from_dict() -> None:
    frame = CompletedPatternFlowStackFrame.from_dict(
        {
            "frame_id": "test_id",
            "step_id": "test_step_id",
            "previous_flow_name": "test_flow",
        }
    )
    assert frame.frame_id == "test_id"
    assert frame.step_id == "test_step_id"
    assert frame.previous_flow_name == "test_flow"
    assert frame.flow_id == "pattern_completed"
    assert frame.type() == "pattern_completed"