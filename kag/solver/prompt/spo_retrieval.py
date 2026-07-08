import logging

from pydantic import BaseModel, Field

from kag.interface import PromptABC

logger = logging.getLogger(__name__)


class SpoSelection(BaseModel):
    indices: list[str] = Field(
        default_factory=list,
        description="0-based indices (as strings) of the SPO candidates that match; empty if none match.",
    )


@PromptABC.register("default_spo_retrieval")
class SpoRetrieval(PromptABC):
    template_en = """{
      "instruction": "You are a language expert. Your task is to select the correct SPO candidate indices to answer the question, based on the SPO mention.",
      "requirements": [
        "Output must be string array of SPO candidate indices (0-based numbering)",
        "Indices correspond strictly to the original candidate order (1st=0, 2nd=1, etc.)",
        "Return all matching indices if multiple candidates match",
        "Return empty list if no candidates match"
      ],
      "examples": [
        {
          "question": "Is the Woman's Viewpoint a British publication?",
          "spo_mention": "Publication[Woman's Viewpoint] Nationality Country",
          "spo_candidates": [
            "the woman s viewpoint ranFrom 1923 to 1927",
            "the woman s viewpoint publishedBy florence m sterling",
            "the woman s viewpoint foundedIn 1923",
            "the woman s viewpoint foundedIn texas",  // index 3
            "the woman s viewpoint was a woman s magazine"
          ],
          "output": ["3"]
        },
        {
          "question": "Who is the German musician whose hand the manuscript for Flute Sonata in C major, BWV 1033 is in?",
          "spo_mention": "Entity[Flute Sonata in C major, BWV 1033] InHandOf Entity",
          "spo_candidates": [
            "flute sonata in c major bwv 1033 isAttributedTo johann sebastian bach",  // index 0
            "flute sonata in c major bwv 1033 isFor flute or recorder and basso continuo"
          ],
          "output": ["0"]
        }
      ],
      "task": {
        "question": "$question",
        "spo_mention": "$mention",
        "spo_candidates": "$candis"
      },
      "output": "Return a JSON string array containing matching candidate indices"
    }
    """

    @property
    def template_variables(self) -> list[str]:
        return ["question", "mention", "candis"]

    def output_schema(self):
        return SpoSelection

    def parse_response(self, response, **kwargs):
        if isinstance(response, SpoSelection):
            return response.indices
        logger.debug(
            f"SpoRetrieval {response} mention:{self.template_variables_value.get('mention', '')} "
            f"candis:{self.template_variables_value.get('candis', '')}"
        )
        if isinstance(response, list):
            return response
        if not isinstance(response, dict):
            return response
        if "output" in response:
            return response["output"]
        if "Output" in response:
            return response["Output"]
        return response
