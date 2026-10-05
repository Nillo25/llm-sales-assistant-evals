from sales_assistant.marker import split_no_answer_marker


def test_plain_answer_is_left_untouched():
    assert split_no_answer_marker("The case fits iPhone 16.") == ("The case fits iPhone 16.", False)


def test_marker_on_its_own_line_is_removed_and_flagged():
    raw = "NO_ANSWER\nSorry, I can only help with Ampwise products."
    assert split_no_answer_marker(raw) == ("Sorry, I can only help with Ampwise products.", True)


def test_marker_is_case_insensitive_and_may_have_a_colon():
    raw = "no_answer: Sorry, that is outside what I can help with."
    assert split_no_answer_marker(raw) == ("Sorry, that is outside what I can help with.", True)


def test_marker_is_removed_from_anywhere_in_the_text():
    # The customer must never see the service word, wherever the model put it.
    raw = "Sorry, I can't help with the weather. NO_ANSWER"
    text, flagged = split_no_answer_marker(raw)
    assert flagged is True
    assert "NO_ANSWER" not in text
    assert text == "Sorry, I can't help with the weather."


def test_empty_or_missing_output_is_not_flagged():
    assert split_no_answer_marker("") == ("", False)
    assert split_no_answer_marker(None) == ("", False)
    assert split_no_answer_marker("   \n ") == ("", False)
