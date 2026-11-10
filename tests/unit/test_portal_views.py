from terramind.api.app import demo_plan
from terramind.incidents.search import IncidentSearcher
from terramind.llm.service import explain
from terramind.portal.store import PortalAnalysis, Session
from terramind.portal.views import analysis_page
from tests.knowledge_helpers import RecordingSynthesizer, local_system


def test_portal_shows_grounded_advice_without_rendering_untrusted_markup():
    _, _, _, retriever = local_system()
    report = explain(demo_plan(), retriever, RecordingSynthesizer())
    original = report.findings
    report = report.model_copy(update={"explanation": '<img src="x" onerror="alert(1)">'})
    bundle = PortalAnalysis(report=report, incident_memory=IncidentSearcher().search(report))
    html = analysis_page(Session("synthetic-token", "synthetic-csrf", "owner", "Analyst"), bundle)
    assert "AI advisory" in html and "Validated advisory sources" in html
    assert "&lt;img" in html and '<img src="x"' not in html
    assert report.findings == original
