from github_anti_ai.domain.language import foreign_language, prose

ENGLISH = (
    "This is a small tool for the terminal. It reads your files and shows them in a list. "
    "You can sort the list by name or by size, and you can also filter it. "
    "The tool is fast because it only reads what it needs. "
)
GERMAN = (
    "Das ist ein kleines Werkzeug für das Terminal. Es liest die Dateien und zeigt sie in "
    "einer Liste an. Man kann die Liste nach Namen oder nach Größe sortieren und auch "
    "filtern. Das Werkzeug ist schnell, weil es nur liest, was es braucht. "
)
SPANISH = (
    "Esta es una pequeña herramienta para la terminal. Lee los archivos y los muestra en "
    "una lista. Se puede ordenar la lista por el nombre o por el tamaño, y también se "
    "puede filtrar. La herramienta es rápida porque solo lee lo que necesita. "
)


def test_english_and_german_pass():
    assert foreign_language("A tool", ENGLISH) is None
    assert foreign_language("Ein Werkzeug", GERMAN) is None


def test_another_script_in_the_text_is_foreign():
    reason = foreign_language("A tool", "这是一个用于终端的小工具。" * 10)

    assert reason.startswith("Weder deutsch noch englisch:")
    assert "anderer Schrift" in reason


def test_another_script_in_the_description_alone_is_foreign():
    reason = foreign_language("终端的小工具", ENGLISH)

    assert (
        reason
        == "Weder deutsch noch englisch: 100% der Buchstaben der Beschreibung in anderer Schrift"
    )


def test_another_language_in_latin_script_is_foreign():
    reason = foreign_language("Herramienta", SPANISH)

    assert reason == "Weder deutsch noch englisch: häufige Wörter einer anderen Sprache überwiegen"


def test_too_little_text_gives_no_verdict():
    assert foreign_language("Herramienta", "Una herramienta pequeña para la terminal") is None


def test_text_without_common_words_is_foreign():
    words = " ".join(f"wort{chr(97 + i % 26)}x" for i in range(60))

    assert "nur 0% der Wörter" in foreign_language("", words)


def test_a_readme_of_lists_and_tables_stays_english():
    readme = ENGLISH + "\n| Key | Action |\n|---|---|\n" + "| ctrl-s | save the file |\n" * 30

    assert foreign_language("Editor", readme) is None


def test_prose_leaves_out_code_links_images_and_html():
    markdown = (
        "Read [the guide](https://example.org/guide) first.\n"
        "```\nfoo bar baz\n```\n"
        "Run `make` and <b>enjoy</b> ![logo](logo.png) https://example.org"
    )

    text = prose(markdown)

    assert "the guide" in text
    for gone in ("example.org", "foo bar", "make", "<b>", "logo"):
        assert gone not in text
