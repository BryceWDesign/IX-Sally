from ix_sally.cognition.cognitive_recovery import RecoveryStage
from ix_sally.cuc8 import run_cuc8


def test_cuc8_recovery_is_explicit_and_returns_to_normal() -> None:
    report = run_cuc8()
    assert report.entered_hold
    assert report.stages == (
        RecoveryStage.COMMITMENT_HOLD,
        RecoveryStage.RETRACT,
        RecoveryStage.REASSESS,
        RecoveryStage.REVALIDATE,
        RecoveryStage.NORMAL,
    )
    assert report.recovered_to_normal
