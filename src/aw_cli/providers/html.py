from html.parser import HTMLParser


class Tags(HTMLParser):
    """Attributi e testo dei tag, indipendenti da ordine, spazi e apici."""

    def __init__(self, html: str, tag: str):
        super().__init__(convert_charrefs=True)
        self.tag = tag
        self.items: list[tuple[dict[str, str], str]] = []
        self.current = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == self.tag:
            self.current = (dict((key, value or "") for key, value in attrs), [])
            if tag in {"meta", "input", "link", "img"}:
                self.items.append((self.current[0], ""))
                self.current = None

    def handle_data(self, data):
        if self.current is not None:
            self.current[1].append(data)

    def handle_endtag(self, tag):
        if tag == self.tag and self.current is not None:
            attrs, chunks = self.current
            self.items.append((attrs, "".join(chunks).strip()))
            self.current = None
