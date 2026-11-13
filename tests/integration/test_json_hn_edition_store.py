import json
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from github_anti_ai.adapters.json_hn_edition_store import JsonHnEditionStore
from github_anti_ai.application.ports import AlreadyPublished
from github_anti_ai.domain.hn import HnEdition, HnProjectCandidate, HnStory


def sample_edition():
    story = HnStory(
        id="123",
        title="A project",
        url="https://project.example",
        points=42,
        comments=9,
        created_at=datetime(2026, 11, 13, tzinfo=UTC),
    )
    return HnEdition(
        day=story.created_at.date(),
        projects=(
            HnProjectCandidate(
                story=story,
                repository_url="https://codeberg.org/owner/project",
                project_url=story.url,
                description="A useful open source project",
                language="Rust",
                license_id="MIT",
                is_fork=False,
                is_archived=False,
                has_code=True,
            ),
        ),
    )


def test_hn_edition_is_saved_and_loaded_with_its_story_and_project_facts(tmp_path):
    store = JsonHnEditionStore(tmp_path / "hn-editions")
    edition = sample_edition()

    store.save(edition)

    assert store.load(edition.day) == edition
    assert store.since(edition.day) == [edition]


def test_hn_edition_cannot_be_replaced_after_publication(tmp_path):
    store = JsonHnEditionStore(tmp_path / "hn-editions")
    edition = sample_edition()
    store.save(edition)

    with pytest.raises(AlreadyPublished):
        store.save(edition)

def test_hn_edition_keeps_its_ai_section_and_topics_but_not_the_readme(tmp_path):
    store = JsonHnEditionStore(tmp_path / "editions")
    main = sample_edition().projects[0]
    agent = replace(
        main,
        repository_url="https://codeberg.org/owner/agent",
        topics=("llm", "mcp"),
        readme="# Agent\n\nAn LLM agent.",
    )
    edition = HnEdition(day=sample_edition().day, projects=(main,), ai_projects=(agent,))

    store.save(edition)

    loaded = store.load(edition.day)
    assert loaded == edition
    assert loaded.ai_projects[0].topics == ("llm", "mcp")
    assert loaded.ai_projects[0].readme == ""
    assert "An LLM agent." not in (tmp_path / "editions" / f"{edition.day}.json").read_text()


def test_hn_edition_from_before_the_ai_section_loads_with_an_empty_one(tmp_path):
    store = JsonHnEditionStore(tmp_path / "editions")
    store.save(sample_edition())
    path = tmp_path / "editions" / f"{sample_edition().day}.json"
    data = json.loads(path.read_text())
    del data["ai_projects"]
    for project in data["projects"]:
        del project["topics"]
    path.write_text(json.dumps(data))

    loaded = store.load(sample_edition().day)

    assert loaded.ai_projects == ()
    assert loaded.projects[0].topics == ()
