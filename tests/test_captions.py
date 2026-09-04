"""Caption rendering tests."""
from memes_shared.services.captions import (
    build_caption,
    format_hashtags,
    pick_template,
    render_template,
)


def test_render_template():
    out = render_template("🔥 {title}\n{hashtags}", {"title": "Cat meme", "hashtags": "#a #b"})
    assert out == "🔥 Cat meme\n#a #b"


def test_unknown_placeholder_removed():
    assert render_template("hi {nope}", {}) == "hi"


def test_hashtag_formatting():
    assert format_hashtags(["memes", "#funny", ""]) == "#memes #funny"


def test_build_caption_custom_with_hashtags():
    out = build_caption(mode="custom", custom_text="😂 {title}", hashtags=["memes"],
                        context={"title": "dog"})
    assert "😂 dog" in out and "#memes" in out


def test_build_caption_default_appends_hashtags():
    class Row:
        text = "Follow for more!"
        hashtags = ["viral"]

    out = build_caption(mode="default", caption_row=Row())
    assert out.startswith("Follow for more!")
    assert "#viral" in out


def test_pick_template_weighted():
    class T:
        def __init__(self, w, en=True):
            self.weight = w
            self.enabled = en

    assert pick_template([]) is None
    assert pick_template([T(1, False)]) is None
    t = pick_template([T(1), T(5)])
    assert t is not None
