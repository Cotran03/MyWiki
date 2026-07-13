from mywiki.services.markdown import render_markdown


def test_markdown_removes_executable_html():
    rendered = str(
        render_markdown("# 안전한 제목\n<script>alert(1)</script>\n[위험](javascript:alert(1))")
    )

    assert "<h1>안전한 제목</h1>" in rendered
    assert "<script>" not in rendered
    assert 'href="javascript:' not in rendered
    assert "&lt;script&gt;" in rendered
