import pytest

from builders import make_snapshot, star_history
from github_anti_ai.domain.exclusion import MIN_STARS_GAINED, ExclusionPolicy
from github_anti_ai.domain.model import StarHistory

ENGLISH = (
    "This is a small terminal text editor written in Rust. It starts in a few milliseconds "
    "and has no dependencies. The editor supports syntax highlighting for the most common "
    "languages, and it can be configured with a single file. You can install it with cargo "
    "or download a binary from the releases page."
)
GERMAN = (
    "Dies ist ein kleiner Texteditor für das Terminal, geschrieben in Rust. Er startet in "
    "wenigen Millisekunden und hat keine Abhängigkeiten. Der Editor unterstützt "
    "Syntaxhervorhebung für die gängigsten Sprachen und lässt sich mit einer einzigen Datei "
    "konfigurieren. Du kannst ihn mit cargo installieren oder eine fertige Datei von der "
    "Seite mit den Veröffentlichungen herunterladen."
)
SPANISH = (
    "Este es un pequeño editor de texto para la terminal, escrito en Rust. Arranca en pocos "
    "milisegundos y carece de dependencias. El editor ofrece resaltado de sintaxis para los "
    "lenguajes más comunes y se puede configurar con un solo archivo. Puedes instalarlo con "
    "cargo o descargar un binario desde la página de versiones del proyecto."
)
PORTUGUESE = (
    "Este é um pequeno editor de texto para o terminal, escrito em Rust. Ele inicia em "
    "poucos milissegundos e não tem dependências. O editor oferece realce de sintaxe para as "
    "linguagens mais comuns e pode ser configurado com um único arquivo. Você pode instalar "
    "com o cargo ou baixar um binário na página de versões do projeto."
)
# seen live: English READMEs that are mostly lists and tables have few function words
ENGLISH_LISTS = (
    "# tiny-editor\n\n## Features\n\n"
    "- Syntax highlighting for Rust, Go, Python, TOML, YAML, JSON, Markdown\n"
    "- Multiple cursors, rectangular selection and incremental search\n"
    "- Mouse support, true color, ligatures, Unicode width handling\n"
    "- Zero dependencies, single static binary, instant startup\n\n"
    "## Supported platforms\n\n"
    "| Platform | Architecture | Status |\n|---|---|---|\n"
    "| Linux | x86_64, aarch64, riscv64 | stable |\n"
    "| macOS | Apple silicon, Intel | stable |\n"
    "| Windows | x86_64 | experimental |\n\n"
    "## Build\n\nRequires Rust stable. Clone the repo, build it and run the tests.\n"
)
CHINESE = (
    "这是一个用 Rust 编写的小型终端文本编辑器。它启动只需几毫秒，没有任何依赖。"
    "编辑器支持最常见语言的语法高亮，并且可以用一个文件进行配置。"
    "你可以使用 cargo 安装它，也可以从发布页面下载二进制文件。"
)


def exclusion(repo="alice/tiny-editor", **overrides):
    return ExclusionPolicy().check(make_snapshot(repo, **overrides))


def kind(repo="alice/tiny-editor", **overrides):
    result = exclusion(repo, **overrides)
    return result.kind if result else None


def test_ordinary_repo_is_not_excluded():
    assert exclusion() is None


@pytest.mark.parametrize(
    ("flag", "expected"),
    [("is_fork", "fork"), ("is_archived", "archived"), ("is_mirror", "mirror")],
)
def test_forks_archived_repos_and_mirrors_are_excluded(flag, expected):
    assert kind(**{flag: True}) == expected


def test_exclusion_states_its_reason_in_words():
    assert exclusion(is_fork=True).reason == "Fork"


def test_repo_without_any_recognized_code_is_excluded():
    assert kind(primary_language=None) == "no_code"


@pytest.mark.parametrize(
    "overrides",
    [
        {"repo": "alice/awesome-rust"},
        {"description": "A curated list of terminal tools"},
        {"topics": ("interview", "algorithms")},
        {"repo": "alice/dotfiles"},
        {"description": "Rust tutorial for beginners"},
        {"description": "System prompts of popular coding assistants"},
        {"repo": "alice/developer-roadmap"},
        {"topics": ("cheat-sheet",)},
        {"description": "My LeetCode solutions"},
    ],
)
def test_collections_and_learning_material_are_excluded(overrides):
    repo = overrides.pop("repo", "alice/tiny-editor")

    assert kind(repo, **overrides) == "collection"


def test_collection_terms_only_count_as_whole_words():
    assert kind(description="An interviewer scheduling service, awesomely fast") is None


def test_repo_without_readme_is_excluded():
    assert kind(readme="") == "no_readme"


@pytest.mark.parametrize("readme", [ENGLISH, GERMAN])
def test_english_and_german_readmes_are_accepted(readme):
    assert kind(readme=readme) is None


def test_readme_in_another_script_is_excluded():
    assert kind(readme=CHINESE) == "language"


def test_readme_in_another_latin_language_is_excluded():
    assert kind(description="Un pequeño editor de texto", readme=SPANISH) == "language"


def test_portuguese_readme_is_excluded_although_it_shares_short_words_with_english():
    # "do", "a", "as" and "no" are frequent Portuguese words
    assert kind(description="Um pequeno editor de texto", readme=PORTUGUESE) == "language"


def test_english_readme_made_of_lists_and_tables_is_accepted():
    assert kind(readme=ENGLISH_LISTS) is None


def test_mostly_foreign_bilingual_readme_is_excluded():
    assert kind(readme=ENGLISH + "\n\n" + CHINESE * 3) == "language"


def test_description_in_another_script_counts_too():
    assert kind(description=CHINESE, readme="# tool\n") == "language"


def test_code_blocks_are_not_judged_as_language():
    readme = "# tool\n\n```\n" + "let está = función(para, los, más, con);\n" * 30 + "```\n"

    assert kind(readme=readme) is None


def test_too_little_prose_gives_the_benefit_of_the_doubt():
    assert kind(description="Editor de texto", readme="# editor\n\nPequeño y rápido.\n") is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"description": "Solana trading bot with copy trading"},
        {"topics": ("web3", "rust")},
        {"repo": "alice/nft-minter"},
        {"description": "Track your crypto portfolio"},
        {"description": "Smart contracts for a new stablecoin"},
    ],
)
def test_cryptocurrency_projects_are_excluded(overrides):
    repo = overrides.pop("repo", "alice/tiny-editor")

    assert kind(repo, **overrides) == "crypto"


@pytest.mark.parametrize(
    "description",
    [
        "A modern cryptography library",
        "Validates JWT tokens and API tokens",
        "A wallet for your loyalty cards",
    ],
)
def test_words_that_only_sound_like_crypto_are_no_reason(description):
    assert kind(description=description) is None


def test_repo_below_the_momentum_threshold_is_excluded():
    assert kind(star_history=star_history(MIN_STARS_GAINED - 1)) == "low_momentum"


def test_repo_at_the_momentum_threshold_stays():
    assert kind(star_history=star_history(MIN_STARS_GAINED)) is None


def test_stars_gained_before_the_growth_window_do_not_count_for_the_threshold():
    burst_ten_days_ago = StarHistory(daily=(0,) * 25 + (500,) + (0,) * 9)

    assert kind(star_history=burst_ten_days_ago) == "low_momentum"


def test_first_matching_rule_gives_the_reason():
    assert kind(is_fork=True, primary_language=None, star_history=star_history(0)) == "fork"
    assert kind(primary_language=None, description="Solana trading bot") == "no_code"


def test_description_in_another_script_is_excluded_even_with_an_english_readme():
    # seen live: a Chinese one-line description above a long English README
    assert kind(description="开发时端口被占，一行命令释放。零依赖", readme=ENGLISH * 3) == "language"


def test_description_with_a_few_foreign_names_is_no_reason():
    assert kind(description="A tiny client for 微信 (WeChat) on the terminal", readme=ENGLISH) is None


@pytest.mark.parametrize(
    "description",
    [
        "Adobe Acrobat Pro 2026: Secure Standalone PDF Document Processor for Desktop",
        "Aida 64 Extreme 2026: Complete Standalone Desktop Setup with Full Feature Configuration",
        "Adobe Substance 3D Creative Studio 2026 - Secure Asset Pipeline Desktop Installer",
        "Archicad 2026 complete standalone desktop setup with pre-configured ready-to-run build",
        "Easy-Worship 2026: Complete Standalone Desktop Setup with All Features Enabled",
        "Photo suite 2026, full version, pre-activated",
    ],
)
def test_lures_for_malware_are_excluded(description):
    assert kind(description=description) == "lure"


def test_lure_is_recognized_by_its_name_too():
    assert kind("mallory/archicad-desktop-setup", description="Archicad 2026") == "lure"


def test_lure_names_the_wording_that_gave_it_away():
    result = exclusion(description="Cubase Studio 2026 desktop setup with full plugin suite")

    assert "Köder" in result.reason
    assert "desktop setup" in result.reason


@pytest.mark.parametrize(
    "description",
    [
        "A standalone binary without dependencies",
        "Desktop app with a secure setup wizard",
        "An installer for the Arch desktop",
        "Complete rewrite of the configuration loader",
    ],
)
def test_ordinary_wording_about_setup_and_desktop_is_no_lure(description):
    assert kind(description=description) is None


LURE_README = (
    '<div align="center">\n\n# Xshell: Advanced SSH/SFTP Terminal Emulator for Windows 11\n\n'
    "![](files/preview.png)\n\n### 💻 PowerShell Installer\n\n"
    "[![](files/button.png)](https://mallory.github.io/xshell-terminal-emulator/)\n\n</div>\n\n"
    "Xshell is a Windows terminal emulator engineered for reliable remote access.\n\n"
    "## ✅ Requirements\n\n- Windows 10 or Windows 11\n"
    "- PowerShell 5.1 or newer (already available on Windows)\n"
    "- Active network connection\n- No admin rights needed\n"
)


def test_lure_is_recognized_by_the_template_of_its_readme():
    # seen live: a second kind of lure has a harmless description, but always this README
    result = exclusion(
        "mallory/xshell-terminal-emulator",
        description="Xshell: Advanced SSH/SFTP Terminal Emulator for Windows",
        readme=LURE_README,
    )

    assert result.kind == "lure"
    assert "README" in result.reason


def test_powershell_instructions_without_the_button_are_no_lure():
    honest = "# tool\n\n" + ENGLISH + "\n\n### PowerShell Installer\n\nRun `install.ps1`.\n"

    assert kind(readme=honest) is None


def test_a_button_to_a_project_page_without_powershell_is_no_lure():
    readme = "# tool\n\n[![](files/button.png)](https://alice.github.io/tiny-editor/)\n\n" + ENGLISH

    assert kind(readme=readme) is None


def test_lure_button_written_in_html_is_recognized_too():
    # seen live: Pereira001/dlss5-manager
    readme = (
        '<h3 align="center">⚡ PowerShell Setup Button</h3>\n\n<p align="center">\n'
        '  <a href="https://Mallory.github.io/dlss5-manager/">\n'
        '    <img src="button.svg" alt="DLSS5 PowerShell Installer" width="400">\n  </a>\n</p>\n\n'
        + ENGLISH
    )

    assert kind("mallory/dlss5-manager", description="", readme=readme) == "lure"


def test_a_logo_that_links_to_the_project_page_is_no_lure():
    readme = (
        '<a href="https://alice.github.io/tiny-editor/"><img src="logo.svg" alt="tiny-editor"></a>'
        "\n\nInstall with PowerShell: `winget install tiny-editor`.\n\n" + ENGLISH
    )

    assert kind(readme=readme) is None
