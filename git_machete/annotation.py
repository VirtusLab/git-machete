import re

from git_machete import utils


class Qualifiers:
    def __init__(self, annotation: str):
        self.__annotation_without_qualifiers: str = annotation
        self.__push_text: str = ''
        self.__rebase_text: str = ''
        self.__slide_out_text: str = ''
        self.__update_with_merge_text: str = ""
        self.rebase: bool = True
        self.push: bool = True
        self.slide_out: bool = True
        self.update_with_merge: bool = False

        def match_pattern(pattern: str) -> str:
            return f".*\\b{pattern}\\b.*"

        def sub_pattern(pattern: str) -> str:
            return f"[ ]?{pattern}[ ]?"

        rebase_anno = 'rebase=no'
        rebase_match = re.match(match_pattern(rebase_anno), annotation)
        if rebase_match:
            self.rebase = False
            self.__rebase_text = rebase_anno
            self.__annotation_without_qualifiers = re.sub(sub_pattern(rebase_anno), ' ', self.__annotation_without_qualifiers)

        push_anno = 'push=no'
        push_match = re.match(match_pattern(push_anno), annotation)
        if push_match:
            self.push = False
            self.__push_text = push_anno
            self.__annotation_without_qualifiers = re.sub(sub_pattern(push_anno), ' ', self.__annotation_without_qualifiers)

        slide_out_anno = 'slide-out=no'
        slide_out_match = re.match(match_pattern(slide_out_anno), annotation)
        if slide_out_match:
            self.slide_out = False
            self.__slide_out_text = slide_out_anno
            self.__annotation_without_qualifiers = re.sub(sub_pattern(slide_out_anno), ' ', self.__annotation_without_qualifiers)

        update_with_merge_anno = 'update=merge'
        update_with_merge_match = re.match(match_pattern(update_with_merge_anno), annotation)
        if update_with_merge_match:
            self.update_with_merge = True
            self.__update_with_merge_text = update_with_merge_anno
            self.__annotation_without_qualifiers = re.sub(sub_pattern(update_with_merge_anno), ' ', self.__annotation_without_qualifiers)

    def get_annotation_text_without_qualifiers(self) -> str:
        return self.__annotation_without_qualifiers.strip()

    def get_qualifiers_text(self) -> str:
        text = f'{self.__rebase_text} {self.__push_text} {self.__slide_out_text} {self.__update_with_merge_text}'
        return re.sub(' +', ' ', text).strip()


class Annotation:
    def __init__(self, text: str):
        self.text = text.strip()
        self.qualifiers = Qualifiers(text)
        self.text_without_qualifiers = self.qualifiers.get_annotation_text_without_qualifiers()
        self.qualifiers_text = self.qualifiers.get_qualifiers_text()

    def get_unformatted_text(self) -> str:
        if not (self.text_without_qualifiers or self.qualifiers_text):
            return ''
        annotation_text = ' '
        if self.text_without_qualifiers:
            annotation_text += self.text_without_qualifiers
        if self.qualifiers_text:
            annotation_text += ' ' if self.text_without_qualifiers else ''
            annotation_text += self.qualifiers_text
        return annotation_text

    def get_formatted_text(self) -> str:
        if not (self.text_without_qualifiers or self.qualifiers_text):
            return ''
        annotation_text = "  "
        if self.text_without_qualifiers:
            annotation_text += utils.dim(self.text_without_qualifiers)
        if self.qualifiers_text:
            annotation_text += ' ' if self.text_without_qualifiers else ''
            annotation_text += utils.dim(utils.underline(s=self.qualifiers_text))
        return annotation_text
