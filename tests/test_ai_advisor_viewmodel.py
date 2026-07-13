from app.ui.viewmodels.ai_advisor_viewmodel import AiAdvisorViewModel


def test_empty_state():
    vm = AiAdvisorViewModel()
    assert vm.state.status == "online"
    assert vm.state.action.key == "find_tenders"


def test_normalization():
    vm = AiAdvisorViewModel()
    vm.set_metrics(new_tenders=-1, recommended=8, attention=3)
    vm.set_focus(title="Тендер", score=140)
    assert vm.state.metrics.new_tenders == 0
    assert vm.state.focus.score == 100


def test_reason_limit():
    vm = AiAdvisorViewModel()
    vm.set_reasons(["1", "2", "3", "4", "5"])
    assert vm.state.reasons == ("1", "2", "3", "4")
