import pytest

from app.models.ta import Ta
from app.services.capacity_guard import CapacityGuard
from app.services.ranking.candidate import Candidate
from app.services.ranking.experience_first import ExperienceFirstStrategy
from app.services.ranking.least_loaded import LeastLoadedStrategy
from app.services.ranking.registry import StrategyRegistry
from app.services.ranking.round_robin import RoundRobinStrategy


def make(ta_id, experience=False, used=0):
    ta = Ta(id=ta_id, name="TA " + str(ta_id), email="ta" + str(ta_id) + "@example.com")
    return Candidate(ta, experience, used)


def ids(candidates):
    return [c.ta_id for c in candidates]


def test_candidate_hours_left():
    assert make(1, used=0).hours_left() == 20
    assert make(1, used=18).hours_left() == 2


def test_experience_first_puts_experienced_first():
    ranked = ExperienceFirstStrategy().rank(None, [make(1), make(2, experience=True, used=10)])
    assert ids(ranked) == [2, 1]


def test_experience_first_keeps_tas_without_experience():
    ranked = ExperienceFirstStrategy().rank(None, [make(1), make(2)])
    assert ids(ranked) == [1, 2]


def test_experience_first_tie_goes_to_most_hours_left():
    ranked = ExperienceFirstStrategy().rank(
        None, [make(1, experience=True, used=12), make(2, experience=True, used=4)]
    )
    assert ids(ranked) == [2, 1]


def test_least_loaded_puts_most_hours_left_first():
    ranked = LeastLoadedStrategy().rank(None, [make(1, used=15), make(2, used=5), make(3, used=10)])
    assert ids(ranked) == [2, 3, 1]


def test_least_loaded_tie_goes_to_experience():
    ranked = LeastLoadedStrategy().rank(None, [make(1, used=5), make(2, experience=True, used=5)])
    assert ids(ranked) == [2, 1]


def test_round_robin_takes_turns():
    rr = RoundRobinStrategy()
    tas = [make(1), make(2), make(3)]
    assert rr.rank(None, tas)[0].ta_id == 1
    assert rr.rank(None, tas)[0].ta_id == 2
    assert rr.rank(None, tas)[0].ta_id == 3
    assert rr.rank(None, tas)[0].ta_id == 1


def test_round_robin_empty_list():
    assert RoundRobinStrategy().rank(None, []) == []


@pytest.mark.parametrize(
    "strategy", [ExperienceFirstStrategy(), LeastLoadedStrategy(), RoundRobinStrategy()]
)
def test_strategies_never_drop_candidates(strategy):
    tas = [make(1, used=19), make(2, experience=True, used=3), make(3, used=10)]
    ranked = strategy.rank(None, tas)
    assert sorted(ids(ranked)) == [1, 2, 3]
    assert ids(tas) == [1, 2, 3]


def test_registry_finds_strategy_by_name():
    registry = StrategyRegistry()
    registry.register(LeastLoadedStrategy())
    assert isinstance(registry.get("least_loaded"), LeastLoadedStrategy)


def test_registry_rejects_unknown_mode():
    registry = StrategyRegistry()
    registry.register(LeastLoadedStrategy())
    with pytest.raises(ValueError):
        registry.get("cheapest")


def test_new_mode_can_be_added():
    class SkillsStrategy(LeastLoadedStrategy):
        name = "skills"

    registry = StrategyRegistry()
    registry.register(LeastLoadedStrategy())
    registry.register(SkillsStrategy())
    assert registry.names() == ["least_loaded", "skills"]


def test_guard_allows_exactly_twenty_hours():
    assert CapacityGuard().feasible(make(1, used=16), 4, 100)


def test_guard_blocks_over_twenty_hours():
    assert not CapacityGuard().feasible(make(1, used=16), 5, 100)


def test_guard_blocks_when_budget_too_small():
    assert not CapacityGuard().feasible(make(1), 6, 5)


def test_guard_filter_keeps_tas_who_fit():
    tas = [make(1, used=18), make(2, used=10)]
    assert ids(CapacityGuard().filter(tas, 3, 100)) == [2]
