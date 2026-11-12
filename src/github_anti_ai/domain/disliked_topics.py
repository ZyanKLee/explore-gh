"""The owner's taste: topics that are rated down wherever they appear."""

from github_anti_ai.domain.model import Signal, Snapshot
from github_anti_ai.domain.text import TermList

# term -> points taken off. A new line here is all a new topic needs.
DISLIKED_TOPICS = {
    "roblox": 50.0,
}


class DislikedTopics:
    def __init__(self):
        self._terms = {term: TermList([term]) for term in DISLIKED_TOPICS}

    def signals(self, snapshot: Snapshot) -> tuple[Signal, ...]:
        """Looks at name, description and topics. One signal per topic."""
        text = " . ".join([snapshot.repo.name, snapshot.description, *snapshot.topics])
        return tuple(
            Signal("disliked_topic", -DISLIKED_TOPICS[term], f"Unerwünschtes Thema: „{term}“")
            for term, terms in self._terms.items()
            if terms.find(text)
        )
