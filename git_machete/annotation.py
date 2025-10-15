import re
from typing import Callable, NamedTuple

from git_machete import utils


class Qualifiers(NamedTuple):
    rebase: bool = True
    push: bool = True
    slide_out: bool = True
    update_with_merge: bool = False

    def is_default(self) -> bool:
        return self.rebase and self.push and self.slide_out and not self.update_with_merge

    def is_non_default(self) -> bool:
        return not self.is_default()

    def __str__(self) -> str:
        segments = ["rebase=no" if not self.rebase else None,
                    "push=no" if not self.push else None,
                    "slide-out=no" if not self.slide_out else None,
                    "update=merge" if self.update_with_merge else None]
        return ' '.join(filter(None, segments))


class Annotation(NamedTuple):
    text_without_qualifiers: str
    qualifiers: Qualifiers

    @property
    def unformatted_full_text(self) -> str:
        if not (self.text_without_qualifiers or self.qualifiers.is_non_default()):
            return ''
        result = ''
        if self.text_without_qualifiers:
            result += self.text_without_qualifiers
        if self.text_without_qualifiers and self.qualifiers.is_non_default():
            result += ' '
        if self.qualifiers.is_non_default():
            result += str(self.qualifiers)
        return result

    @property
    def formatted_full_text(self) -> str:
        if not (self.text_without_qualifiers or self.qualifiers.is_non_default()):
            return ''
        result = ''
        if self.text_without_qualifiers:
            result += utils.dim(self.text_without_qualifiers)
        if self.text_without_qualifiers and self.qualifiers.is_non_default():
            result += ' '
        if self.qualifiers.is_non_default():
            result += utils.dim(utils.underline(s=str(self.qualifiers)))
        return result

    @staticmethod
    def parse(text_with_qualifiers: str) -> "Annotation":
        text_without_qualifiers = text_with_qualifiers
        qualifiers = Qualifiers()

        def parse_one(pattern: str, qf: Callable[[Qualifiers], Qualifiers]) -> None:
            nonlocal qualifiers, text_without_qualifiers
            match = re.match(f".*\\b{pattern}\\b.*", text_without_qualifiers)
            if match:
                qualifiers = qf(qualifiers)
                text_without_qualifiers = re.sub(f"[ ]?{pattern}[ ]?", ' ', text_without_qualifiers)

        parse_one('rebase=no', lambda q: q._replace(rebase=False))
        parse_one('push=no', lambda q: q._replace(push=False))
        parse_one('slide-out=no', lambda q: q._replace(slide_out=False))
        parse_one('update=merge', lambda q: q._replace(update_with_merge=True))
        return Annotation(text_without_qualifiers.strip(), qualifiers)
