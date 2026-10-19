"""HTML sanitising for admin-authored lesson text (allow-list, via nh3)."""
import nh3

TAGS = {"p", "br", "strong", "b", "em", "i", "u", "s", "h2", "h3", "h4", "ul", "ol", "li", "blockquote", "a", "img",
        "table", "thead", "tbody", "tr", "th", "td", "hr", "code", "pre", "span", "div", "sup", "sub"}
ATTRIBUTES = {"a": {"href", "title", "target"}, "img": {"src", "alt", "title", "width", "height"},
              "td": {"colspan", "rowspan"}, "th": {"colspan", "rowspan"}}


def sanitize(html: str) -> str:
    return nh3.clean(html or "", tags=TAGS, attributes=ATTRIBUTES, url_schemes={"http", "https", "mailto"},
                     link_rel="noopener noreferrer nofollow")
