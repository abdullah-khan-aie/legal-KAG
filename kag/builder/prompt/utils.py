import logging

from kag.interface import PromptABC

logger = logging.getLogger(__name__)


def init_prompt_with_fallback(prompt_name, biz_scene):
    try:
        return PromptABC.from_config({"type": f"{biz_scene}_{prompt_name}"})
    except Exception as e:
        logger.debug(
            f"fail to initialize prompts with biz scene {biz_scene}, fallback to default biz scene, info: {e}"
        )

        return PromptABC.from_config({"type": f"default_{prompt_name}"})
