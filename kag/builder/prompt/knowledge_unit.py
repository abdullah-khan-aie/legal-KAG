import json

from kag.builder.prompt.util import load_knowIE_data
from kag.interface import PromptABC


@PromptABC.register("knowledge_unit")
class KnowledgeUnitPrompt(PromptABC):
    template_en = """You are an assistant for document analysis and knowledge unit extraction. Please extract substantial discussions, arguments, or analyses from the input document chunks. Ensure that the extracted knowledge units are strictly related to the document's theme and are the core content that the author directly introduces, analyzes, or argues within the chunk.

### Extraction Requirements:
- Identify the core argument in the chunk and extract content that makes a creative contribution to the document's theme.
- If the chunk contains numerous citations or mentions, only extract significant knowledge units involved when further analyzing, expanding, arguing, or applying these contents. Exclude auxiliary knowledge units or background information that are merely cited or mentioned.
- The names of knowledge units should be described using concise and clear language, fully reflecting the core theme of the knowledge unit.
- A knowledge unit is a complete and coherent whole, with clear arguments. Multiple knowledge units may be extracted from a chunk, but if further division would fail to preserve the context, argumentation process, etc., of the knowledge unit, the entire chunk should not be subdivided further. The content description of knowledge units should be clear and organized, avoiding superfluous or repetitive explanations.

### Knowledge Types
- Declarative Knowledge: Narratives explaining concepts, terms, theorems, clauses, etc., answering 'what' questions, including concept definitions, term explanations, arguments, formulas, legal provisions, etc.
- Case Knowledge: Demonstrating and explaining abstract concepts and theories through specific situations or examples, including judicial precedents, math problems, medical cases, etc., usually treated as a single complete knowledge unit.
- Factual Knowledge: Describing the state, attributes, characteristics, or background information of things, including historical events, news information, entity introductions, etc.
- Procedural Knowledge: Knowledge about how to perform tasks or operations, including program code, algorithms, operational steps, experimental processes, equation sets for problem-solving, etc.
- Analytical Knowledge: Knowledge derived through logical analysis, calculations, induction, deduction, etc., to support views or conclusions, answering 'why' and 'how to derive conclusions' questions.


### Output Format:
{
  "knowledge unit 1 Name":
  {
    "Content": "A text excerpt extracted or summarized from the chunk, must include critical information that unambiguously explains the knowledge unit's content and subject.",
    "Knowledge Type": "Declarative Knowledge / Case Knowledge / Factual Knowledge / Procedural Knowledge / Analytical Knowledge",
    "Structural Content": "Structured content associated with the knowledge unit, such as charts, formulas, code, rules, first-order logic representation, equation sets, data structure definitions, etc.",
    "Domain Ontology": "The hierarchical classification system of disciplines or professional fields to which knowledge units belong. It is important to note that the terms at each level are general concepts rather than specific instances (remove individual person, organizations, etc. for the ontology).",
    "Core Entities": "Keywords that represent the subject or characteristics of the knowledge unit, ensuring that each term is semantically complete and reflects the knowledge unit's distinctiveness in searches relative to other content, and the valid type of each core entity is listed in the `Entity Types`",
    "Related Query": "The three most relevant query questions based on the knowledge unit's subject and content",
    "Extended Knowledge Points": "Other highly related but divergent knowledge points not included in the current knowledge point"
 },
  "knowledge unit 2 Name": {},
  ...
}

### Example:
input:"No Mediocre" is a song by American rapper T.I., released on June 17, 2014, through Grand Hustle and Columbia Records, as the lead single from his ninth studio album "Paperwork" (2014). The song, produced by DJ Mustard, features a guest appearance from Grand Hustle protégé, Australian rapper Iggy Azalea.
output:
{
  "No Mediocre Song Details":{
    "Content": "\"No Mediocre\" is a song by American rapper T.I., released as the lead single from his ninth studio album \"Paperwork\" (2014). The track, produced by DJ Mustard, includes a guest appearance by Australian rapper Iggy Azalea. It peaked at number 69 on the US Billboard Hot 100 and was met with positive reviews for its production and Azalea's contribution.",
    "Knowledge Type": "Factual Knowledge",
    "Structural Content": "",
    "Domain Ontology": "Music -> Hip Hop -> T.I. Discography -> No Mediocre",
    "Core Entities": {"T.I.": "Person", "No Mediocre" : "Culture and Entertainment", "Paperwork" : "Culture and Entertainment", "DJ Mustard" : "Person", "Iggy Azalea": "Person", "US Billboard Hot 100": "Culture and Entertainment" },
    "Related Query": ["What is the lead single from T.I.'s ninth studio album?", "Who produced the song 'No Mediocre'?", "What was the peak position of 'No Mediocre' on the US Billboard Hot 100?"],
    "Extended Knowledge Points": ["T.I.'s discography", "DJ Mustard's production work", "Iggy Azalea's collaborations", "US Billboard Hot 100 chart", "Critical reception of 'No Mediocre'", "Soundtrack for 'Think Like a Man Too'"]
  }
}
### Input:
input: $input
"""

    @property
    def template_variables(self) -> list[str]:
        return ["input", "named_entities"]

    def process_data(self, response: str, **kwargs):
        rsp = response
        if isinstance(rsp, str):
            rsp = json.loads(rsp)
        if isinstance(rsp, dict) and "output" in rsp:
            rsp = rsp["output"]
        return rsp

    def process_en(self, response: dict, **kwargs):
        """ "No Mediocre Song Details":{
          "Content": "\"No Mediocre\" is a song by American rapper T.I., released as the lead single from his ninth studio album \"Paperwork\" (2014). The track, produced by DJ Mustard, includes a guest appearance by Australian rapper Iggy Azalea. It peaked at number 69 on the US Billboard Hot 100 and was met with positive reviews for its production and Azalea's contribution.",
          "Knowledge Type": "Factual Knowledge",
          "Structural Content": "",
          "Domain Ontology": "Music -> Hip Hop -> T.I. Discography -> No Mediocre",
          "Core Entities": "T.I., No Mediocre, Paperwork, DJ Mustard, Iggy Azalea, US Billboard Hot 100",
          "Related Query": ["What is the lead single from T.I.'s ninth studio album?", "Who produced the song 'No Mediocre'?", "What was the peak position of 'No Mediocre' on the US Billboard Hot 100?"],
          "Extended Knowledge Points": ["T.I.'s discography", "DJ Mustard's production work", "Iggy Azalea's collaborations", "US Billboard Hot 100 chart", "Critical reception of 'No Mediocre'", "Soundtrack for 'Think Like a Man Too'"]
        }"""
        ret = {}
        if "Content" in response.keys():
            ret["content"] = response["Content"]
        if "Knowledge Type" in response.keys():
            ret["knowledgetype"] = response["Knowledge Type"]
        if "Domain Ontology" in response.keys():
            ret["ontology"] = response["Domain Ontology"]
        if "Core Entities" in response.keys():
            ret["core_entities"] = response["Core Entities"]
        if "Related Query" in response.keys():
            ret["relatedQuery"] = response["Related Query"]
        if "Extended Knowledge Points" in response.keys():
            ret["extendedKnowledge"] = response["Extended Knowledge Points"]
        return ret

    def parse_response(self, response: str, **kwargs):
        rsp = load_knowIE_data(response)
        ret = {}
        for k, v in rsp.items():
            ret[k] = self.process_en(v, **kwargs)
        return ret
