from git_machete.annotation import Annotation


def test_parse_qualifier_needs_whitespace_separation() -> None:
    # Per docs, a qualifier "needs to be separated by a whitespace from any other character",
    # so hyphen- or comma-glued lookalikes must be kept as plain annotation text.
    anno = Annotation.parse("my push=no-frills note")
    assert anno.qualifiers.push is True
    assert anno.text_without_qualifiers == "my push=no-frills note"

    anno = Annotation.parse("note,rebase=no,more")
    assert anno.qualifiers.rebase is True
    assert anno.text_without_qualifiers == "note,rebase=no,more"

    anno = Annotation.parse("my push=no-frills note push=no")
    assert anno.qualifiers.push is False
    assert anno.text_without_qualifiers == "my push=no-frills note"

    anno = Annotation.parse("note,rebase=no,more rebase=no")
    assert anno.qualifiers.rebase is False
    assert anno.text_without_qualifiers == "note,rebase=no,more"


def test_parse_space_separated_qualifiers_still_detected() -> None:
    anno = Annotation.parse("annotation rebase=no push=no")
    assert anno.qualifiers.rebase is False
    assert anno.qualifiers.push is False
    assert anno.text_without_qualifiers == "annotation"
