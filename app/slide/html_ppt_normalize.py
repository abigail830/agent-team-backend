"""Normalize html-ppt source before bundling (Inspire branding, meta text cleanup)."""

from __future__ import annotations

import re

_INSPIRE_OPT_IN_RE = re.compile(
    r"""(?:class=["'][^"']*\btpl-inspire-brand\b|data-inspire-brand\s*=\s*["']true["'])""",
    re.IGNORECASE,
)

_ASC_OPT_IN_RE = re.compile(
    r"""(?:class=["'][^"']*\btpl-asc-brand\b|data-asc-brand\s*=\s*["']true["'])""",
    re.IGNORECASE,
)

# Agent meta / prompt text that must not appear on slides (→ removed).
_META_TEXT_RES = (
    re.compile(
        r"Inspire Theme\s*"
        r"(?:封面页|内容页|章节页|结束页)?\s*"
        r"(?:，|,?\s*)?"
        r"(?:基于\s*inspire-brand\s*主题)?"
        r"(?:，|,?\s*)?"
        r"(?:保留深蓝品牌底色与蓝色高光)?"
        r"[。\.]?",
        re.IGNORECASE,
    ),
    re.compile(r"基于\s*inspire-brand\s*主题[，,]?[^<\n]{0,80}", re.IGNORECASE),
    re.compile(r"保留深蓝品牌底色与蓝色高光[。\.]?", re.IGNORECASE),
    re.compile(r"[：:]\s*当前对外沟通可聚焦的[^<\"\n]{0,48}", re.IGNORECASE),
    re.compile(r"(?:本页|此页)(?:沟通|汇报|演讲)?重点[：:][^<\"\n]{0,80}", re.IGNORECASE),
    re.compile(r"(?:一期|本页|此页)?沟通建议[：:][^<\"\n]{0,120}", re.IGNORECASE),
    re.compile(r"(?:汇报|演讲|口播)建议[：:][^<\"\n]{0,120}", re.IGNORECASE),
    re.compile(r"[：:]\s*把[^<\"\n]{0,24}讲成[^<\"\n]{0,48}", re.IGNORECASE),
)

_META_LABELS = (
    "本页沟通重点",
    "沟通重点",
    "沟通建议",
    "一期沟通建议",
    "演讲提示",
    "口播提示",
    "对内沟通",
    "对内说明",
    "对外沟通可聚焦",
    "本页说明",
    "设计说明",
    "布局说明",
    "Agent说明",
    "Agent 说明",
)

_META_INSTRUCTION_BLOCK_RE = re.compile(
    r"<(?:div|section|footer|aside)\b(?![^>]*\b(?:notes|deck-footer)\b)[^>]*>"
    r"(?:(?!</(?:div|section|footer|aside)>).)*?"
    r"(?:沟通建议|沟通重点|汇报建议|演讲建议|对内说明|把[^<]{0,24}讲成|对外沟通可聚焦)"
    r"(?:(?!</(?:div|section|footer|aside)>).)*?"
    r"</(?:div|section|footer|aside)>",
    re.IGNORECASE | re.DOTALL,
)

_PRESENTER_BLOCK_RE = re.compile(
    r"<aside\b[^>]*>"
    r"(?:(?!</aside>).)*?"
    r"<h[1-4][^>]*>\s*(?:本页沟通重点|沟通重点|沟通建议|(?:一期|本页)?沟通建议|演讲提示|口播提示|对内沟通|Speaker\s*Notes|Presenter\s*Notes)\s*</h[1-4]>"
    r"(?:(?!</aside>).)*?"
    r"</aside>",
    re.IGNORECASE | re.DOTALL,
)

_PRESENTER_INLINE_BLOCK_RE = re.compile(
    r"<h[1-4][^>]*>\s*(?:本页沟通重点|沟通重点|沟通建议|(?:一期|本页)?沟通建议|演讲提示|口播提示|对内沟通|Speaker\s*Notes|Presenter\s*Notes)\s*</h[1-4]>"
    r"(?:\s*<(?:ul|ol|p|div|blockquote)\b[^>]*>.*?</(?:ul|ol|p|div|blockquote)>)?",
    re.IGNORECASE | re.DOTALL,
)

_PRESENTER_DIV_SIDEBAR_RE = re.compile(
    r"<div\b(?![^>]*\b(?:deck|slide)\b)[^>]*>"
    r"(?:(?!</div>).)*?"
    r"<h[1-4][^>]*>\s*(?:本页沟通重点|沟通重点|沟通建议|(?:一期|本页)?沟通建议|演讲提示|口播提示|对内沟通|Speaker\s*Notes|Presenter\s*Notes)\s*</h[1-4]>"
    r"(?:(?!</div>).)*?"
    r"</div>",
    re.IGNORECASE | re.DOTALL,
)

_PRESENTER_CLASS_BLOCK_RE = re.compile(
    r'<(?:aside|div|section)\b[^>]*class="[^"]*(?:presenter-hint|speaker-sidebar|comm-focus|page-hint|presenter-notes-visible)[^"]*"[^>]*>.*?</(?:aside|div|section)>',
    re.IGNORECASE | re.DOTALL,
)

_SLIDE_RE = re.compile(
    r"(<section\b[^>]*class=\"[^\"]*\bslide\b[^\"]*\"[^>]*>)(.*?)(</section>)",
    re.IGNORECASE | re.DOTALL,
)

_LOGO_WHITE = "../../assets/inspire/logo-white.png"
_LOGO_COLOR = "../../assets/inspire/logo.png"
_COPYRIGHT = "© Inspire Group"

_CORE_HEAD_LINKS = (
    ('href="../../assets/fonts.css"', '<link rel="stylesheet" href="../../assets/fonts.css">'),
    ('href="../../assets/base.css"', '<link rel="stylesheet" href="../../assets/base.css">'),
    (
        "unpkg.com/lucide",
        '<script src="https://unpkg.com/lucide@0.469.0/dist/umd/lucide.min.js"></script>',
    ),
    ('src="../../assets/runtime.js"', '<script src="../../assets/runtime.js"></script>'),
)


def is_inspire_branding_enabled(html: str) -> bool:
    """True only when the deck explicitly opts into Inspire (user-requested template)."""
    return bool(_INSPIRE_OPT_IN_RE.search(html or ""))


def uses_inspire_layout_classes(html: str) -> bool:
    text = html or ""
    return bool(
        re.search(
            r"\binspire-(?:cover|content|section|agenda|end|case|interaction|footer)\b",
            text,
            re.IGNORECASE,
        )
    )


def has_inspire_scoped_css_link(html: str) -> bool:
    text = html or ""
    if "inspire-deck-scoped.css" in text:
        return True
    return bool(
        re.search(
            r"(?:full-decks|templates/full-decks)/inspire-brand/style\.css",
            text,
            re.IGNORECASE,
        )
    )


def is_asc_branding_enabled(html: str) -> bool:
    """True only when the deck explicitly opts into Ascentium branding."""
    return bool(_ASC_OPT_IN_RE.search(html or ""))


def has_asc_scoped_css_link(html: str) -> bool:
    return "asc-deck-scoped.css" in (html or "")


_INSPIRE_STAGE_PAGE_RE = re.compile(
    r"\binspire-(?:content|agenda|case|interaction)\b",
    re.IGNORECASE,
)


def _strip_meta_fragments(text: str) -> str:
    out = text
    for pattern in _META_TEXT_RES:
        out = pattern.sub("", out)
    return out


def _strip_meta_badges(text: str) -> str:
    out = text
    for label in _META_LABELS:
        out = re.sub(
            rf"<(?:span|div|p|label|small|strong|em|b|mark|button)\b[^>]*>\s*{re.escape(label)}\s*</(?:span|div|p|label|small|strong|em|b|mark|button)>",
            "",
            out,
            flags=re.IGNORECASE,
        )
    return out


def _strip_meta_instruction_blocks(text: str) -> str:
    out = text
    prev = None
    while prev != out:
        prev = out
        out = _META_INSTRUCTION_BLOCK_RE.sub("", out)
    return out


def _strip_presenter_blocks(text: str) -> str:
    out = text
    prev = None
    while prev != out:
        prev = out
        out = _PRESENTER_BLOCK_RE.sub("", out)
        out = _PRESENTER_DIV_SIDEBAR_RE.sub("", out)
        out = _PRESENTER_INLINE_BLOCK_RE.sub("", out)
        out = _PRESENTER_CLASS_BLOCK_RE.sub("", out)
        out = _strip_meta_instruction_blocks(out)
    return out


def _strip_unrequested_inspire(html: str) -> str:
    if is_inspire_branding_enabled(html):
        return html
    out = html
    out = re.sub(
        r'<link\b[^>]*href="[^"]*inspire-brand\.css"[^>]*/?\s*>',
        "",
        out,
        flags=re.IGNORECASE,
    )
    out = re.sub(r'<img\b[^>]*\binspire-logo\b[^>]*>', "", out, flags=re.IGNORECASE)
    out = re.sub(
        r'<span\b[^>]*\binspire-copyright\b[^>]*>.*?</span>',
        "",
        out,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return out


def _ensure_core_head_links(html: str) -> str:
    if not re.search(r"""class=["'][^"']*\bdeck\b""", html or "", re.IGNORECASE):
        return html
    if "</head>" not in html:
        return html
    injections: list[str] = []
    if 'name="viewport"' not in html.lower():
        injections.append('<meta name="viewport" content="width=device-width, initial-scale=1">')
    for marker, tag in _CORE_HEAD_LINKS:
        if marker not in html:
            injections.append(tag)
    if not injections:
        return html
    block = "\n".join(injections)
    return html.replace("</head>", f"{block}\n</head>", 1)


def _ensure_deck_host_body(html: str) -> str:
    if not re.search(r"""class=["'][^"']*\bdeck\b""", html or "", re.IGNORECASE):
        return html
    if re.search(r"<body\b[^>]*\bdeck-host\b", html or "", re.IGNORECASE):
        return html

    def _add_host(match: re.Match[str]) -> str:
        tag = match.group(0)
        if re.search(r'\bclass="', tag):
            return re.sub(r'\bclass="', 'class="deck-host ', tag, count=1)
        if re.search(r"\bclass='", tag):
            return re.sub(r"\bclass='", "class='deck-host ", tag, count=1)
        return tag[:-1] + ' class="deck-host">'

    return re.sub(r"<body\b[^>]*>", _add_host, html, count=1, flags=re.IGNORECASE)


def _slide_needs_white_logo(section_html: str) -> bool:
    classes = section_html.lower()
    return any(
        token in classes
        for token in ("inspire-cover", "inspire-section", "inspire-end", " cover-slide")
    ) or "background:linear-gradient" in section_html.replace(" ", "")


def _inject_logo(open_tag: str, body: str, close_tag: str) -> str:
    if re.search(r"assets/inspire/logo", body, re.IGNORECASE):
        return open_tag + body + close_tag
    src = _LOGO_WHITE if _slide_needs_white_logo(open_tag + body) else _LOGO_COLOR
    logo = f'<img class="inspire-logo" src="{src}" alt="Inspire">'
    return open_tag + logo + body + close_tag


def _inject_copyright(body: str) -> str:
    if "inspire-copyright" in body.lower() or _COPYRIGHT.lower() in body.lower():
        return body
    footer_match = re.search(
        r'(<div\b[^>]*class="[^"]*\bdeck-footer\b[^"]*"[^>]*>)(.*?)(</div>)',
        body,
        re.IGNORECASE | re.DOTALL,
    )
    if footer_match:
        prefix, inner, suffix = footer_match.groups()
        inner = inner.strip()
        copy_span = f'<span class="inspire-copyright">{_COPYRIGHT}</span>'
        inner = f"{copy_span}\n    {inner}" if inner else copy_span
        new_footer = f"{prefix}{inner}{suffix}"
        return body[: footer_match.start()] + new_footer + body[footer_match.end() :]

    return body + f'\n    <div class="deck-footer inspire-footer"><span class="inspire-copyright">{_COPYRIGHT}</span></div>'


_IFRAME_BOOT_SCRIPT = (
    '<script>(function(){if(window.self!==window.top){'
    'document.documentElement.classList.add("in-iframe");})();</script>'
)


def _inject_iframe_boot_script(html: str) -> str:
    if "</head>" not in html:
        return html
    if "classList.add(\"in-iframe\")" in html:
        return html
    return html.replace("</head>", f"{_IFRAME_BOOT_SCRIPT}\n</head>", 1)


def _ensure_default_theme(html: str) -> str:
    if is_inspire_branding_enabled(html) or is_asc_branding_enabled(html):
        return html
    if re.search(r"assets/themes/", html or "", re.IGNORECASE):
        return html
    if "</head>" not in html:
        return html
    link = '<link rel="stylesheet" id="theme-link" href="../../assets/themes/corporate-clean.css">'
    return html.replace("</head>", f"{link}\n</head>", 1)


def _ensure_asc_theme_link(html: str) -> str:
    """Inject asc-brand token CSS when Ascentium is explicitly opted in."""
    if not is_asc_branding_enabled(html):
        return html
    if re.search(r"assets/themes/asc-brand\.css", html or "", re.IGNORECASE):
        return html
    if "</head>" not in html:
        return html
    link = '<link rel="stylesheet" id="theme-link" href="../../assets/themes/asc-brand.css">'
    return html.replace("</head>", f"{link}\n</head>", 1)


def inject_inspire_scoped_css_link(html: str) -> str:
    """Ensure full-deck scoped CSS is linked only when Inspire is explicitly opted in."""
    if not is_inspire_branding_enabled(html):
        return html
    if "inspire-deck-scoped.css" in html:
        return html
    if "</head>" not in html:
        return html
    link = '<link rel="stylesheet" href="../../assets/inspire-deck-scoped.css">'
    return html.replace("</head>", f"{link}\n</head>", 1)


def inject_asc_scoped_css_link(html: str) -> str:
    """Ensure Ascentium scoped CSS is linked only when explicitly opted in."""
    if not is_asc_branding_enabled(html):
        return html
    if "asc-deck-scoped.css" in html:
        return html
    if "</head>" not in html:
        return html
    link = '<link rel="stylesheet" href="../../assets/asc-deck-scoped.css">'
    return html.replace("</head>", f"{link}\n</head>", 1)


def normalize_html_ppt_source(html: str) -> str:
    """Clean agent meta text; strip unrequested Inspire; enforce branding only when opted in."""
    text = (html or "").strip()
    if not text:
        return text

    text = _strip_meta_fragments(text)
    text = _strip_meta_badges(text)
    text = _strip_presenter_blocks(text)
    text = _strip_unrequested_inspire(text)
    text = _ensure_core_head_links(text)
    text = _inject_iframe_boot_script(text)
    text = _ensure_default_theme(text)
    text = _ensure_asc_theme_link(text)
    text = _ensure_deck_host_body(text)
    text = inject_inspire_scoped_css_link(text)
    text = inject_asc_scoped_css_link(text)

    if not is_inspire_branding_enabled(text):
        return text

    def _fix_slide(match: re.Match[str]) -> str:
        open_tag, body, close_tag = match.group(1), match.group(2), match.group(3)
        body = _strip_meta_fragments(body)
        body = _strip_meta_badges(body)
        body = _strip_presenter_blocks(body)
        body = _inject_copyright(body)
        return _inject_logo(open_tag, body, close_tag)

    return _SLIDE_RE.sub(_fix_slide, text)


_EMOJI_RE = re.compile(
    r"[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U000024C2-\U0001F251]"
)


_META_WARNING_PHRASES = (
    "沟通建议",
    "沟通重点",
    "对外沟通可聚焦",
    "讲成",
    "本页说明",
    "布局说明",
)


def collect_html_ppt_warnings(*, source: str, normalized: str) -> list[str]:
    """Return human-readable warnings for agent follow-up after render."""
    warnings: list[str] = []
    src = source or ""
    out = normalized or ""

    if uses_inspire_layout_classes(src) and not is_inspire_branding_enabled(src):
        warnings.append(
            "Avoid inspire-* layout classes unless the user explicitly requested Inspire; "
            "use corporate-clean + templates/single-page/roadmap.html instead."
        )

    if is_inspire_branding_enabled(src) and not has_inspire_scoped_css_link(src):
        warnings.append(
            "Inspire deck must link ../../assets/inspire-deck-scoped.css in <head> "
            "(or copy templates/full-decks/inspire-brand/). "
            "inspire-brand.css is tokens only — scoped CSS defines fixed logo/copyright chrome."
        )
        for match in _SLIDE_RE.finditer(out):
            open_tag, body, _close = match.group(1), match.group(2), match.group(3)
            if not _INSPIRE_STAGE_PAGE_RE.search(open_tag):
                continue
            if "slide-main" in body:
                continue
            warnings.append(
                "Inspire content slides need <div class=\"slide-main\"> wrapping title + "
                "main visual (keeps body vertically centered between logo and copyright). "
                "See references/inspire-brand.md § Chrome 契约."
            )
            break

    if is_asc_branding_enabled(src) and not has_asc_scoped_css_link(src):
        warnings.append(
            "Ascentium deck must link ../../assets/asc-deck-scoped.css in <head> "
            "(along with ../../assets/themes/asc-brand.css). "
            "asc-brand.css is tokens only — scoped CSS defines slide variants and tables."
        )

    for match in _SLIDE_RE.finditer(out):
        if _EMOJI_RE.search(match.group(2)):
            warnings.append(
                "Avoid emoji on visible slides — use Lucide icons: "
                "<span class=\"slide-icon-box\"><i data-lucide=\"target\"></i></span> "
                "(see references/icons.md)."
            )
            break

    if src.lower().count("position:absolute") > 10:
        warnings.append(
            "Too many position:absolute elements — copy templates/single-page/roadmap.html "
            "or split into multiple slides (one message per slide)."
        )

    for phrase in _META_WARNING_PHRASES:
        if phrase in out:
            warnings.append(
                f"Visible slide still contains internal meta text «{phrase}» — "
                "remove from HTML or move to <div class=\"notes\">."
            )

    slide_count = len(_SLIDE_RE.findall(out))
    if slide_count == 1 and out.lower().count("<li") > 8:
        warnings.append(
            "Single slide has too many list items; split the roadmap into 2–3 executive slides."
        )

    return warnings
