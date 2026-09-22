"""Phase 3: text cleaning and chunking. Pure functions: no database, no Ollama."""
import pytest

from app.services.chunking import chunk_text
from app.services.text_cleaning import normalize_text

# What Phase 2 extracts from Customer_Support_Knowledge_Base_Test.pdf, exactly.
KB_TEXT = (
    "Customer Support Knowledge Base\nRefund Policy\n"
    "Customers can request a refund within 30 days of purchase. Refund requests must include the order\n"
    "number and the reason for the request.\nShipping Policy\n"
    "Standard delivery usually takes 3 to 5 business days. Customers receive a tracking number after their\n"
    "order has been dispatched.\nSupport Hours\n"
    "Customer support is available Monday to Friday from 9:00 AM to 6:00 PM. Customers can submit\n"
    "complaints outside these hours and an agent can respond during support hours."
)


def sentences(count, words=10):
    """Distinct sentences of `words` words each: 's0w1 s0w2 ... s0w10.'"""
    return [" ".join(f"s{i}w{j}" for j in range(1, words + 1)) + "." for i in range(count)]


# ---------------------------------------------------------- cleaning

def test_cleaning_removes_extraction_artefacts():
    raw = "Re\ufb01nd\u00a0policy\u200b:\x00 \u00adnone\x07 here"
    assert normalize_text(raw) == "Refind policy: none here"


def test_cleaning_tidies_whitespace_and_blank_lines():
    raw = "  Refund\t\tpolicy   \r\n\r\n\r\n\r\n   Customers   can  request  \n"
    assert normalize_text(raw) == "Refund policy\n\nCustomers can request"


def test_cleaning_keeps_wording_punctuation_and_unicode():
    text = "Price: ₹499 – delivery in 3–5 days (approx.)!\nग्राहक रिफंड माँग सकते हैं। Café “quoted”"
    assert normalize_text(text) == text  # nothing to fix, so nothing changes


def test_cleaning_is_idempotent():
    once = normalize_text("A\u00a0 b\r\n\r\n\r\nc\ufb01")
    assert normalize_text(once) == once


# ---------------------------------------------------------- chunking

def test_normal_text_packs_whole_sentences():
    s = sentences(6)  # 60 words
    chunks = chunk_text(" ".join(s), max_words=25, overlap_words=0)
    # Two 10-word sentences fit in 25 words; a third would not.
    assert [c.text for c in chunks] == [" ".join(s[0:2]), " ".join(s[2:4]), " ".join(s[4:6])]
    assert [c.word_count for c in chunks] == [20, 20, 20]


def test_short_text_is_one_chunk():
    [chunk] = chunk_text("Refunds within 30 days.", max_words=500, overlap_words=75)
    assert (chunk.index, chunk.text, chunk.word_count) == (0, "Refunds within 30 days.", 4)


def test_long_text_with_default_sizes():
    s = sentences(120)  # 1,200 words
    chunks = chunk_text(" ".join(s), max_words=500, overlap_words=75)
    assert len(chunks) == 3
    for chunk in chunks:
        assert chunk.word_count <= 500
        assert chunk.text.startswith("s") and chunk.text.endswith("w10.")  # whole sentences only
    # Nothing lost: every sentence appears, and the last chunk ends the text.
    joined = " ".join(c.text for c in chunks)
    assert all(sentence in joined for sentence in s)
    assert chunks[-1].text.endswith(s[-1])


def test_overlap_repeats_the_last_sentences():
    s = sentences(10)
    chunks = chunk_text(" ".join(s), max_words=40, overlap_words=20)
    assert chunks[0].text == " ".join(s[0:4])
    # The next chunk starts by repeating the last 20 words (two sentences) of the previous one.
    assert chunks[1].text == " ".join(s[2:6])
    assert chunks[2].text == " ".join(s[4:8])
    assert chunks[3].text == " ".join(s[6:10])
    assert len(chunks) == 4


def test_zero_overlap_shares_nothing():
    s = sentences(6)
    chunks = chunk_text(" ".join(s), max_words=20, overlap_words=0)
    assert [c.text for c in chunks] == [" ".join(s[i:i + 2]) for i in (0, 2, 4)]


def test_sentence_longer_than_a_chunk_is_split_by_words():
    words = [f"w{i}" for i in range(30)]  # no punctuation: one 30-word "sentence"
    chunks = chunk_text(" ".join(words), max_words=10, overlap_words=3)
    assert [c.text.split() for c in chunks] == [words[0:10], words[7:17], words[14:24], words[21:30]]


def test_line_breaks_inside_a_sentence_do_not_split_it():
    text = "Refund requests must include the order\nnumber and the reason. Shipping takes 3 days."
    chunks = chunk_text(text, max_words=10, overlap_words=0)
    assert chunks[0].text == "Refund requests must include the order\nnumber and the reason."


def test_real_document_splits_at_its_sections():
    assert len(chunk_text(KB_TEXT, 500, 75)) == 1  # 81 words: one chunk at the default size
    chunks = chunk_text(KB_TEXT, max_words=30, overlap_words=0)
    # Headings have no full stop, so each one stays attached to its section's first sentence.
    assert [c.text.split("\n")[0] for c in chunks] == [
        "Customer Support Knowledge Base", "Shipping Policy", "Support Hours"]


@pytest.mark.parametrize("text", ["", "   ", "\n\n\t  \n"])
def test_empty_text_gives_no_chunks(text):
    assert chunk_text(text, 500, 75) == []
    assert chunk_text(normalize_text(text), 500, 75) == []


def test_whitespace_heavy_text():
    raw = "\n\n   Refund    policy.\t\t\n\n\n\n\n   Customers\u00a0\u00a0can   request   refunds.   \n\n"
    [chunk] = chunk_text(normalize_text(raw), 500, 75)
    assert chunk.text == "Refund policy.\n\nCustomers can request refunds."
    assert chunk.word_count == 6


def test_unicode_text_is_preserved():
    text = "ग्राहक 30 दिनों के भीतर रिफंड माँग सकते हैं। Kundendienst: Rückerstattung möglich. 退款政策。"
    [chunk] = chunk_text(normalize_text(text), 500, 75)
    assert chunk.text == text


def test_rupee_and_en_dash_are_preserved():
    text = "Delivery takes 3–5 days. Orders under ₹499 pay ₹49 – see the table."
    chunks = chunk_text(normalize_text(text), max_words=6, overlap_words=0)
    joined = " ".join(c.text for c in chunks)
    assert "3–5" in joined and "₹499" in joined and "₹49 –" in joined


def test_chunk_indexes_are_sequential_and_in_reading_order():
    s = sentences(30)
    chunks = chunk_text(" ".join(s), max_words=50, overlap_words=10)
    assert [c.index for c in chunks] == list(range(len(chunks)))
    first_sentence = [s.index(c.text.split(". ")[0] + ".") for c in chunks]
    assert first_sentence == sorted(first_sentence)  # each chunk starts later in the text


def test_word_count_matches_the_text():
    for chunk in chunk_text(KB_TEXT, max_words=30, overlap_words=15):
        assert chunk.word_count == len(chunk.text.split())


def test_chunking_is_deterministic():
    text = " ".join(sentences(200, words=7))
    assert chunk_text(text, 100, 20) == chunk_text(text, 100, 20)


@pytest.mark.parametrize("max_words, overlap_words", [(0, 0), (10, 10), (10, 12), (10, -1)])
def test_invalid_settings_are_refused(max_words, overlap_words):
    with pytest.raises(ValueError):
        chunk_text("Some text.", max_words, overlap_words)
