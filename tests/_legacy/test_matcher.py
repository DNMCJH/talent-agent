"""Tests for the matcher agent."""


from talent_agent.agents.matcher import _compute_scores, _normalize_skill
from talent_agent.models import ParsedJD, ProjectDoc, Skill


def test_normalize_skill():
    assert _normalize_skill("LangChain") == "langchain"
    assert _normalize_skill("lang-chain") == "langchain"
    assert _normalize_skill("Lang Chain") == "langchain"


def test_compute_coverage_full_match():
    project = ProjectDoc(
        name="test-project",
        path="/tmp/test",
        readme="",
        stack=["Python", "LangChain", "Docker"],
    )
    jd = ParsedJD(
        raw="",
        language="en",
        company="Test",
        role="Engineer",
        must_skills=[
            Skill(name="Python", level="intermediate"),
            Skill(name="LangChain", level="basic"),
        ],
        plus_skills=[],
        responsibilities=[],
        implicit_signals={"team_style": "", "production_vs_research": "production", "seniority_expectation": "intern"},
        keywords_for_search=[],
        jd_hash="test",
    )
    must_cov, plus_cov, weighted, matched, missing, matched_plus = _compute_scores(project, jd)
    assert must_cov == 1.0
    assert plus_cov == 0.0
    assert weighted == 1.0  # no plus skills → weighted == must
    assert set(matched) == {"Python", "LangChain"}
    assert missing == []
    assert matched_plus == []


def test_compute_coverage_partial():
    project = ProjectDoc(
        name="test-project",
        path="/tmp/test",
        readme="",
        stack=["Python"],
    )
    jd = ParsedJD(
        raw="",
        language="en",
        company="Test",
        role="Engineer",
        must_skills=[
            Skill(name="Python", level="intermediate"),
            Skill(name="Kubernetes", level="basic"),
        ],
        plus_skills=[],
        responsibilities=[],
        implicit_signals={"team_style": "", "production_vs_research": "production", "seniority_expectation": "intern"},
        keywords_for_search=[],
        jd_hash="test",
    )
    must_cov, plus_cov, weighted, matched, missing, matched_plus = _compute_scores(project, jd)
    assert must_cov == 0.5
    assert plus_cov == 0.0
    assert weighted == 0.5
    assert matched == ["Python"]
    assert missing == ["Kubernetes"]


def test_compute_coverage_with_plus_skills():
    """When plus_skills exist, weighted score blends must (0.7) and plus (0.3)."""
    project = ProjectDoc(
        name="test-project",
        path="/tmp/test",
        readme="",
        stack=["Python", "Docker"],
    )
    jd = ParsedJD(
        raw="",
        language="en",
        company="Test",
        role="Engineer",
        must_skills=[Skill(name="Python", level="intermediate")],
        plus_skills=[
            Skill(name="Docker", level="basic"),
            Skill(name="Kubernetes", level="basic"),
        ],
        responsibilities=[],
        implicit_signals={"team_style": "", "production_vs_research": "production", "seniority_expectation": "intern"},
        keywords_for_search=[],
        jd_hash="test",
    )
    must_cov, plus_cov, weighted, _, _, matched_plus = _compute_scores(project, jd)
    assert must_cov == 1.0
    assert plus_cov == 0.5  # Docker matched, Kubernetes missing
    assert weighted == 0.7 * 1.0 + 0.3 * 0.5
    assert matched_plus == ["Docker"]
