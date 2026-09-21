import pytest

from eval import run_eval


def test_retrieval_regression_fails_even_with_perfect_policy():
    policy = {"overall_accuracy": 1, "halt_detection": {"fn": 0}}
    rag = {"modes": {"lexical": {"recall_at_k": {"recall@4": 0.2}}}}
    assert "lexical recall@4 below floor" in run_eval.failures(policy, rag, None, .97, .8, False)


def test_live_failure_is_not_a_successful_offline_run():
    policy = {"overall_accuracy": 1}
    rag = {"modes": {"lexical": {"recall_at_k": {"recall@4": 1}}}}
    assert run_eval.failures(policy, rag, {"error": "provider down"}, .97, .8, True)
    assert not run_eval.failures(policy, rag, None, .97, .8, False)


@pytest.mark.parametrize("args", [["--limit", "0"], ["--limit", "-1"],
                                 ["--fail-under", "1.1"], ["--fail-under", "nan"]])
def test_invalid_limits_rejected_before_work(args):
    with pytest.raises(SystemExit) as exc:
        run_eval.main(args)
    assert exc.value.code == 2


def test_tagged_plan_actions_preserve_tier_and_description():
    from eval.live_eval import plan_tiers
    assert plan_tiers("- [AUTO] Log incident\n- [APPROVE] Purchase bearing\n[MONITOR] Vibration") == [
        ("AUTO", "Log incident"), ("APPROVE", "Purchase bearing")]
