import logging

from kag.interface import PromptABC

logger = logging.getLogger(__name__)


@PromptABC.register("default_rewrite_sub_query")
class DefaultRewriteSubQuery(PromptABC):
    template_en = """"{
    instruction": "Please rewrite the current question based on historical Q&A information and complete the entities referred to in the question.",
    "cases": [
        {
            "history_qa": "Who is the director of God'S Gift To Women?  \nanswer: Michael Curtiz\nWho is the director of Aldri Annet Enn Bråk?  \nanswer: Edith Carlmar",
            "question": "What is the birth year of the director of God'S Gift To Women? "
            "answer": "What is the birth year of Michael Curtiz"
        },
        {
            "history_qa": "Who is the director of God'S Gift To Women?  \nanswer: Michael Curtiz\nWhat is the birth year of the director of God'S Gift To Women?  \nanswer: 1886\nWho is the director of Aldri Annet Enn Bråk?  \nanswer: Edith Carlmar",
            "question": "What is the birth year of the director of Aldri Annet Enn Bråk? "
            "answer": "What is the birth year of Edith Carlmar"
        }
    ],
    "output_format": "only output re-writed question",
    "history_qa": "$history_qa",
    "question": "$question"
}
"""

    @property
    def template_variables(self) -> list[str]:
        return ["history_qa", "question"]

    def parse_response(self, response: str, **kwargs):
        logger.debug(f"rewrite sub query:{response}")
        return response
