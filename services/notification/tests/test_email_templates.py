from services.notification.app.email_templates import (
    render_password_reset_email,
    render_verification_email,
)


def test_verification_email_uses_soft_rouge_branded_html_without_visible_raw_urls():
    html, text = render_verification_email(
        "123456", "https://class-sync-bhiv.vercel.app"
    )

    assert "ClassSync" in html and "Colegio de Montalban" in html
    assert "123456" in html and "expires in <strong>5 minutes</strong>" in html
    assert "click here to continue" in html
    assert "https://class-sync-bhiv.vercel.app/auth/login" in html
    assert "123456" in text and "click here to continue" in text
    assert "classsync_identity" not in html.lower() + text.lower()
    assert "https://class-sync-bhiv.vercel.app" not in text


def test_verification_email_escapes_untrusted_values():
    html, text = render_verification_email("<1234", "https://example.invalid/?x=\"<script>")

    assert "&lt;1234" in html
    assert "<script>" not in html + text


def test_password_reset_email_uses_clean_branded_action_link_without_visible_url():
    reset_url = "https://class-sync-bhiv.vercel.app/auth/reset-password?oobCode=opaque-code"
    html, text = render_password_reset_email(reset_url)

    assert "ClassSync" in html and "Colegio de Montalban" in html
    reset_link = "https://class-sync-bhiv.vercel.app/auth/reset-password?oobCode=opaque-code"
    assert f'href="{reset_link}"' in html
    assert ">Reset Password</a>" in html
    assert "click here to continue" in html
    assert "classsync-f444c" not in html.lower() + text.lower()
    assert "https://class-sync-bhiv.vercel.app" not in text
