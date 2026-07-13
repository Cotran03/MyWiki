import nh3
from markdown_it import MarkdownIt
from markupsafe import Markup

_renderer = MarkdownIt(
    "commonmark",
    {
        "html": False,
        "breaks": True,
        "typographer": False,
    },
)


def render_markdown(source: str) -> Markup:
    rendered = _renderer.render(source or "")
    cleaned = nh3.clean(rendered, link_rel="noopener noreferrer")
    return Markup(cleaned)
