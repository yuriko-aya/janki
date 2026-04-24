import markdown
from django.conf import settings
from django.views.generic import TemplateView


class BotInfoView(TemplateView):
    template_name = "bot_info.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        bot_md_path = settings.BASE_DIR / "BOT.md"
        md_text = bot_md_path.read_text(encoding="utf-8")
        context["bot_info_html"] = markdown.markdown(
            md_text,
            extensions=["tables", "fenced_code"],
        )
        return context
