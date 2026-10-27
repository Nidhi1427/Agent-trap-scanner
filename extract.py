"""Extract visible and non-visible text channels from HTML without third-party packages."""
import re
from html.parser import HTMLParser

HIDDEN_STYLE = re.compile(r"display\s*:\s*none|visibility\s*:\s*hidden|font-size\s*:\s*0|opacity\s*:\s*0|"
                          r"color\s*:\s*(#fff(fff)?|white)\b|left\s*:\s*-\d{3,}px", re.I)
ATTRS = ("aria-label", "alt", "title", "placeholder", "data-description")
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.segments = []
        self.stack = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ("script", "style"):
            hidden = self.stack[-1] if self.stack else False
            self.stack.append((tag, hidden, True))
            return
        for name in ATTRS:
            value = attrs.get(name)
            if value and value.strip():
                self.segments.append(("attr", value.strip()))
        parent_hidden = self.stack[-1][1] if self.stack else False
        hidden = parent_hidden or bool(HIDDEN_STYLE.search(attrs.get("style", ""))) or "hidden" in attrs
        if tag not in VOID_TAGS:
            self.stack.append((tag, hidden, False))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        if self.stack and self.stack[-1][2]:
            return
        text = " ".join(data.split())
        if text:
            hidden = self.stack[-1][1] if self.stack else False
            self.segments.append(("css_hidden" if hidden else "visible", text))

    def handle_comment(self, data):
        text = data.strip()
        if text:
            self.segments.append(("comment", text))


def extract_segments(html: str):
    """Return (channel, text) pairs in document order."""
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    return parser.segments


def extract_text(raw: str, kind: str) -> str:
    """Return all candidate text, including hidden text and selected attributes."""
    return raw if kind != "web" else "\n".join(text for _, text in extract_segments(raw))
