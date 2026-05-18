"""Tests for the JD parser agent."""


from talent_agent.models import ParsedJD, Skill


def test_parsed_jd_model():
    """Verify ParsedJD model validates correctly."""
    jd = ParsedJD(
        raw="test jd",
        language="en",
        company="SAP",
        role="AI Engineer Intern",
        must_skills=[
            Skill(name="Python", level="intermediate"),
            Skill(name="LangChain", level="basic"),
        ],
        plus_skills=[Skill(name="React", level="basic")],
        responsibilities=["Develop AI features"],
        implicit_signals={"team_style": "enterprise", "production_vs_research": "production", "seniority_expectation": "intern"},
        keywords_for_search=["AI", "LangChain", "RAG", "Python"],
        jd_hash="abc123def456",
    )
    assert jd.company == "SAP"
    assert len(jd.must_skills) == 2
    assert jd.must_skills[0].name == "Python"


def test_skill_aliases():
    """Verify Skill model handles aliases."""
    skill = Skill(name="LangChain", level="intermediate", aliases=["LC", "langchain"])
    assert "LC" in skill.aliases
    assert skill.level == "intermediate"
