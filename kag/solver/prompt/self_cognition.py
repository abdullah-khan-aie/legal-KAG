from kag.interface import PromptABC


@PromptABC.register("default_self_cognition")
class SelfCognitionPrompt(PromptABC):
    template_en = """You are KAG(KAG is a logical reasoning and Q&A framework based on the OpenSPG engine and large language models). Your task is to determine whether the input question “$question” is a self-awareness question.
Extended Requirements: Questions related to self-recognition are also considered, such as "What is your website?"
Requirements:
Directly answer “Yes” or “No”."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @property
    def template_variables(self) -> list[str]:
        return ["question"]

    @staticmethod
    def parse_response_en(response: str, **kwargs):
        if "yes" in response.lower():
            return True
        return False

    @staticmethod
    def parse_response_zh(response: str, **kwargs):
        if "是" in response:
            return True
        return False

    def parse_response(self, response: str, **kwargs):
        try:
            response = response.strip()
            if self.kag_project_config.language == "en":
                return self.parse_response_en(response)
            return self.parse_response_zh(response)
        except Exception as e:
            print(e)
            return False
