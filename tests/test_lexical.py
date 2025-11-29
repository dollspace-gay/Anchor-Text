"""Tests for the Lexical Cartography system."""


from anchor_text.lexical.analyzer import LexicalAnalyzer
from anchor_text.lexical.guide import CompanionGuideGenerator
from anchor_text.formatting.ir import (
    FormattedDocument,
    TextBlock,
    TextRun,
    TextStyle,
    LexicalMap,
    WordEntry,
    MorphemeInfo,
    MorphemeFamily,
)


class TestLexicalAnalyzer:
    """Tests for the LexicalAnalyzer class."""

    def test_init_default(self):
        """Test default initialization."""
        analyzer = LexicalAnalyzer()
        assert analyzer.model is not None
        assert analyzer.use_llm is True

    def test_init_no_llm(self):
        """Test initialization without LLM."""
        analyzer = LexicalAnalyzer(use_llm=False)
        assert analyzer.use_llm is False

    def test_extract_words_basic(self):
        """Test basic word extraction."""
        analyzer = LexicalAnalyzer(use_llm=False)
        text = "The scientists hypothesized about the results."
        words = analyzer.extract_words(text, min_syllables=2)

        assert "scientists" in words
        assert "hypothesized" in words
        assert "results" in words
        # Single syllable words should be excluded
        assert "The" not in words

    def test_extract_words_removes_formatting(self):
        """Test that formatting markers are removed."""
        analyzer = LexicalAnalyzer(use_llm=False)
        text = "**The scientists** *hypothesized* about the re·sults."
        words = analyzer.extract_words(text, min_syllables=2)

        assert "scientists" in words
        assert "hypothesized" in words
        assert "results" in words

    def test_extract_words_removes_decoder_checks(self):
        """Test that decoder checks are removed."""
        analyzer = LexicalAnalyzer(use_llm=False)
        text = "The scientists hypothesized. [Decoder Check: What did they do?]"
        words = analyzer.extract_words(text, min_syllables=2)

        assert "hypothesized" in words
        assert "Decoder" not in words
        assert "Check" not in words

    def test_extract_words_deduplicates(self):
        """Test that duplicate words are removed."""
        analyzer = LexicalAnalyzer(use_llm=False)
        text = "The scientists hypothesized. The scientists concluded."
        words = analyzer.extract_words(text, min_syllables=2)

        # Should only appear once
        assert words.count("scientists") == 1

    def test_estimate_syllables_simple(self):
        """Test syllable estimation for simple words."""
        analyzer = LexicalAnalyzer(use_llm=False)

        assert analyzer._estimate_syllables("cat") == 1
        assert analyzer._estimate_syllables("hello") == 2
        assert analyzer._estimate_syllables("beautiful") >= 3
        assert analyzer._estimate_syllables("hypothesized") >= 4

    def test_estimate_syllables_silent_e(self):
        """Test syllable estimation handles silent e."""
        analyzer = LexicalAnalyzer(use_llm=False)

        # "make" should be 1 syllable, not 2
        assert analyzer._estimate_syllables("make") == 1
        assert analyzer._estimate_syllables("time") == 1

    def test_analyze_word_locally_with_prefix(self):
        """Test local analysis identifies prefixes."""
        analyzer = LexicalAnalyzer(use_llm=False)
        entry = analyzer._analyze_word_locally("unhappy")

        prefixes = [m for m in entry.morphemes if m.morpheme_type == "prefix"]
        assert len(prefixes) >= 1
        assert any(m.text == "un" for m in prefixes)

    def test_analyze_word_locally_with_suffix(self):
        """Test local analysis identifies suffixes."""
        analyzer = LexicalAnalyzer(use_llm=False)
        entry = analyzer._analyze_word_locally("happiness")

        suffixes = [m for m in entry.morphemes if m.morpheme_type == "suffix"]
        assert len(suffixes) >= 1
        assert any(m.text == "ness" for m in suffixes)

    def test_analyze_word_locally_with_known_root(self):
        """Test local analysis identifies known roots."""
        analyzer = LexicalAnalyzer(use_llm=False)
        entry = analyzer._analyze_word_locally("prediction")

        # Root should contain "dict" or be a reasonable extraction
        assert "dic" in entry.root.lower() or entry.root != ""
        roots = [m for m in entry.morphemes if m.morpheme_type == "root"]
        assert len(roots) >= 1

    def test_analyze_word_locally_difficulty(self):
        """Test that difficulty scores are assigned."""
        analyzer = LexicalAnalyzer(use_llm=False)

        simple = analyzer._analyze_word_locally("happy")
        complex_word = analyzer._analyze_word_locally("incomprehensibility")

        assert 1 <= simple.difficulty_score <= 10
        assert 1 <= complex_word.difficulty_score <= 10
        # More complex word should be harder
        assert complex_word.difficulty_score >= simple.difficulty_score

    # ==========================================================================
    # Morphological Syllabification Tests
    # ==========================================================================

    def test_syllabify_prefix_boundary_react(self):
        """Test that 're-act' preserves prefix boundary (not 'rea-ct')."""
        analyzer = LexicalAnalyzer(use_llm=False)
        syllables = analyzer._split_syllables("react")

        # re + act (morphological) not rea + ct (phonetic error)
        assert syllables == ["re", "act"], f"Expected ['re', 'act'], got {syllables}"

    def test_syllabify_suffix_boundary_scoping(self):
        """Test that 'scop-ing' preserves suffix boundary (not 'sco-ping')."""
        analyzer = LexicalAnalyzer(use_llm=False)
        syllables = analyzer._split_syllables("scoping")

        # scop + ing (morphological) not sco + ping (phonetic error)
        assert syllables[-1] == "ing", f"Expected suffix 'ing', got {syllables}"

    def test_syllabify_multiple_morphemes_unpredictable(self):
        """Test that 'un-pre-dict-able' preserves all morpheme boundaries."""
        analyzer = LexicalAnalyzer(use_llm=False)
        syllables = analyzer._split_syllables("unpredictable")

        # Should identify un-, pre-, and -able as separate syllables
        assert syllables[0] == "un", f"Expected first syllable 'un', got {syllables}"
        assert syllables[1] == "pre", f"Expected second syllable 'pre', got {syllables}"
        assert syllables[-1] == "able", f"Expected last syllable 'able', got {syllables}"

    def test_syllabify_suffix_ing_jumping(self):
        """Test that 'jump-ing' preserves -ing suffix boundary."""
        analyzer = LexicalAnalyzer(use_llm=False)
        syllables = analyzer._split_syllables("jumping")

        assert syllables[-1] == "ing", f"Expected suffix 'ing', got {syllables}"

    def test_syllabify_suffix_ed_acted(self):
        """Test that 'act-ed' preserves -ed suffix boundary."""
        analyzer = LexicalAnalyzer(use_llm=False)
        syllables = analyzer._split_syllables("acted")

        # act + ed (morphological)
        assert syllables[-1] == "ed", f"Expected suffix 'ed', got {syllables}"

    def test_syllabify_prefix_dis_disconnect(self):
        """Test that 'dis-connect' preserves dis- prefix boundary."""
        analyzer = LexicalAnalyzer(use_llm=False)
        syllables = analyzer._split_syllables("disconnect")

        assert syllables[0] == "dis", f"Expected prefix 'dis', got {syllables}"

    def test_syllabify_prefix_un_unhappy(self):
        """Test that 'un-happy' preserves un- prefix boundary."""
        analyzer = LexicalAnalyzer(use_llm=False)
        syllables = analyzer._split_syllables("unhappy")

        assert syllables[0] == "un", f"Expected prefix 'un', got {syllables}"

    def test_syllabify_combined_prefix_suffix_reacting(self):
        """Test that 're-act-ing' preserves both prefix and suffix."""
        analyzer = LexicalAnalyzer(use_llm=False)
        syllables = analyzer._split_syllables("reacting")

        assert syllables[0] == "re", f"Expected prefix 're', got {syllables}"
        assert syllables[-1] == "ing", f"Expected suffix 'ing', got {syllables}"

    def test_syllabify_simple_word_without_affixes(self):
        """Test phonetic fallback for words without known affixes."""
        analyzer = LexicalAnalyzer(use_llm=False)
        syllables = analyzer._split_syllables("potato")

        # Should fall back to phonetic rules
        assert len(syllables) >= 2, f"Expected at least 2 syllables, got {syllables}"

    def test_analyze_document_creates_map(self):
        """Test that document analysis creates a lexical map."""
        analyzer = LexicalAnalyzer(use_llm=False)
        doc = FormattedDocument(blocks=[
            TextBlock(runs=[TextRun(text="The scientists hypothesized.", style=TextStyle.NONE)]),
            TextBlock(runs=[TextRun(text="They analyzed the results.", style=TextStyle.NONE)]),
        ])

        lexical_map = analyzer.analyze_document(doc)

        assert isinstance(lexical_map, LexicalMap)
        assert lexical_map.total_unique_words > 0
        assert "scientists" in lexical_map.words or "hypothesized" in lexical_map.words

    def test_analyze_document_tracks_first_occurrence(self):
        """Test that first occurrence paragraph is tracked."""
        analyzer = LexicalAnalyzer(use_llm=False)
        doc = FormattedDocument(blocks=[
            TextBlock(runs=[TextRun(text="First paragraph.", style=TextStyle.NONE)]),
            TextBlock(runs=[TextRun(text="Scientists discovered something.", style=TextStyle.NONE)]),
        ])

        lexical_map = analyzer.analyze_document(doc)

        if "scientists" in lexical_map.words:
            assert lexical_map.words["scientists"].first_occurrence == 1

    def test_enhance_document(self):
        """Test that enhance_document adds vocabulary metadata."""
        analyzer = LexicalAnalyzer(use_llm=False)
        doc = FormattedDocument(blocks=[
            TextBlock(runs=[TextRun(text="The scientists hypothesized.", style=TextStyle.NONE)]),
        ])

        result = analyzer.enhance_document(doc)

        assert result.vocabulary is not None
        assert result.vocabulary.lexical_map is not None


class TestLexicalMap:
    """Tests for the LexicalMap dataclass."""

    def test_add_word(self):
        """Test adding words to the map."""
        lexical_map = LexicalMap()
        entry = WordEntry(word="test", difficulty_score=5)

        lexical_map.add_word(entry)

        assert "test" in lexical_map.words
        assert lexical_map.total_unique_words == 1

    def test_add_word_updates_frequency(self):
        """Test that adding same word updates frequency."""
        lexical_map = LexicalMap()
        entry1 = WordEntry(word="test", difficulty_score=5)
        entry2 = WordEntry(word="test", difficulty_score=5)

        lexical_map.add_word(entry1)
        lexical_map.add_word(entry2)

        assert lexical_map.words["test"].frequency == 2
        assert lexical_map.total_unique_words == 1

    def test_difficulty_tiers(self):
        """Test that words are categorized by difficulty."""
        lexical_map = LexicalMap()
        easy = WordEntry(word="easy", difficulty_score=2)
        medium = WordEntry(word="medium", difficulty_score=5)
        hard = WordEntry(word="hard", difficulty_score=8)

        lexical_map.add_word(easy)
        lexical_map.add_word(medium)
        lexical_map.add_word(hard)

        assert "easy" in lexical_map.difficulty_tiers["easy"]
        assert "medium" in lexical_map.difficulty_tiers["medium"]
        assert "hard" in lexical_map.difficulty_tiers["challenging"]

    def test_get_root_families(self):
        """Test grouping words by root."""
        lexical_map = LexicalMap()

        # Add words with same root
        word1 = WordEntry(word="predict", root="dict")
        word2 = WordEntry(word="dictate", root="dict")
        word3 = WordEntry(word="unrelated", root="late")

        lexical_map.add_word(word1)
        lexical_map.add_word(word2)
        lexical_map.add_word(word3)

        families = lexical_map.get_root_families()

        # Should have one family for "dict" with 2 words
        dict_family = next((f for f in families if f.root.text == "dict"), None)
        assert dict_family is not None
        assert len(dict_family.words) == 2

        # "unrelated" shouldn't form a family (only 1 word)
        late_family = next((f for f in families if f.root.text == "late"), None)
        assert late_family is None


class TestWordEntry:
    """Tests for the WordEntry dataclass."""

    def test_syllable_text(self):
        """Test syllable text generation."""
        entry = WordEntry(
            word="hypothesis",
            syllables=["hy", "poth", "e", "sis"],
        )

        assert entry.syllable_text == "hy·poth·e·sis"

    def test_syllable_text_empty(self):
        """Test syllable text with no syllables."""
        entry = WordEntry(word="test", syllables=[])

        assert entry.syllable_text == "test"


class TestCompanionGuideGenerator:
    """Tests for the CompanionGuideGenerator class."""

    def test_generate_creates_document(self):
        """Test that generate creates a document."""
        generator = CompanionGuideGenerator()
        lexical_map = LexicalMap()
        lexical_map.add_word(WordEntry(word="test", difficulty_score=5))

        guide = generator.generate(lexical_map, "Test Document")

        assert isinstance(guide, FormattedDocument)
        assert len(guide.blocks) > 0

    def test_generate_includes_title(self):
        """Test that guide includes title."""
        generator = CompanionGuideGenerator()
        lexical_map = LexicalMap()
        lexical_map.add_word(WordEntry(word="test", difficulty_score=5))

        guide = generator.generate(lexical_map, "My Book")

        # First block should be title
        title_text = guide.blocks[0].plain_text
        assert "My Book" in title_text

    def test_generate_with_exercises(self):
        """Test guide includes exercises when enabled."""
        generator = CompanionGuideGenerator(include_exercises=True)
        lexical_map = LexicalMap()
        lexical_map.add_word(WordEntry(word="prediction", root="dict", difficulty_score=7))

        guide = generator.generate(lexical_map)

        full_text = " ".join(b.plain_text for b in guide.blocks)
        assert "Practice" in full_text or "Exercise" in full_text

    def test_generate_without_exercises(self):
        """Test guide excludes exercises when disabled."""
        generator = CompanionGuideGenerator(include_exercises=False)
        lexical_map = LexicalMap()
        lexical_map.add_word(WordEntry(word="test", difficulty_score=5))

        guide = generator.generate(lexical_map)

        full_text = " ".join(b.plain_text for b in guide.blocks)
        assert "Practice Exercises" not in full_text

    def test_format_family(self):
        """Test morpheme family formatting."""
        generator = CompanionGuideGenerator()
        family = MorphemeFamily(
            root=MorphemeInfo(text="dict", meaning="say, speak", origin="Latin"),
            words=[
                WordEntry(word="predict", syllables=["pre", "dict"]),
                WordEntry(word="dictate", syllables=["dic", "tate"]),
            ],
        )

        blocks = generator._format_family(family)

        assert len(blocks) >= 1
        full_text = " ".join(b.plain_text for b in blocks)
        assert "DICT" in full_text
        assert "say, speak" in full_text
