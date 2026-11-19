from collections import defaultdict

import babelfish
import plexapi.media


def get_title(stream: plexapi.media.MediaPartStream) -> str | None:
    """Return the title fields, longest first, without a field that is part of a longer one."""
    fields: list[str | None] = [stream.extendedDisplayTitle, stream.displayTitle, stream.title]
    titles: list[str] = []
    for field in sorted(filter(None, fields), key=len, reverse=True):
        if not any(field in title for title in titles):
            titles.append(field)
    return " ".join(titles) or None


def get_expected_languages(stream: plexapi.media.MediaPartStream) -> list[babelfish.Language]:
    languages: set[babelfish.Language] = set()
    for code in {stream.languageCode, stream.language, stream.languageTag}:
        if not code:
            continue

        for conv in (
            babelfish.Language.fromietf,
            babelfish.Language.fromname,
            babelfish.Language,
            babelfish.Language.fromalpha2,
        ):
            try:
                lang = conv(code)
                languages.add(lang)
                break
            except (ValueError, babelfish.LanguageReverseError):
                pass

    max_num_tags = 0
    more_specific = defaultdict(list)
    for lang in languages:
        num_tags = str(lang).count("-")
        max_num_tags = max(max_num_tags, num_tags)
        more_specific[num_tags].append(lang)

    if more_specific[max_num_tags]:
        return more_specific[max_num_tags]

    return []
